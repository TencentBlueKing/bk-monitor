"""积压回放使用现有匹配器，且不影响窗外新异常和非通知动作。"""

from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import Mock

import arrow
import pytest
from django.utils import timezone

from alarm_backends.core.alert.alert import Alert
from alarm_backends.core.alert import alert as alert_module
from alarm_backends.core.cache.shield import ShieldCacheManager
from alarm_backends.service.alert.manager.checker import action as action_checker
from alarm_backends.service.alert.manager.checker import shield as shield_checker
from alarm_backends.service.alert.manager import processor as manager_processor
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield.shielder import saas_config
from alarm_backends.service.fta_action import utils
from alarm_backends.service.fta_action.tasks import create_action
from bkmonitor.utils import extended_json
from bkmonitor.utils.range.period import TimeMatchByDay, TimeMatchBySingle
from constants.action import ActionNoticeType, ActionPluginType, ActionSignal
from constants.alert import EventStatus

NOW = arrow.get("2026-10-08T11:30:00Z").timestamp
INSIDE = arrow.get("2026-10-08T06:10:00Z").timestamp
OUTSIDE = arrow.get("2026-10-08T07:10:00Z").timestamp
REPLAY_COUNT = 1000


@pytest.fixture(autouse=True)
def history_cache():
    saas_config.AlertShieldConfigShielder._load_history.cache_clear()
    with timezone.override("UTC"):
        yield
    saas_config.AlertShieldConfigShielder._load_history.cache_clear()


def make_alert(at=INSIDE, alert_id="old"):
    return Alert(
        {
            "id": alert_id,
            "create_time": NOW,
            "begin_time": INSIDE,
            "first_anomaly_time": INSIDE,
            "latest_time": at,
            "severity": 1,
            "status": EventStatus.ABNORMAL,
            "strategy_id": 1,
            "alert_name": "fixture",
            "is_shielded": False,
            "is_handled": True,
            "event": {"bk_biz_id": 2, "bk_tenant_id": "default", "time": INSIDE, "tags": []},
            "extra_info": {
                "latest_abnormal_event_time": at,
                "strategy": {"notice": {"id": 7, "config_id": 8}, "actions": []},
            },
        }
    )


def historical_rule(periodic=False):
    rule = object.__new__(AlertShieldObj)
    rule.id = 10
    rule.config = {
        "id": 10,
        "end_policy": "notify_once",
        "create_time": arrow.get("2026-10-07T00:00:00Z").datetime,
        "update_time": arrow.get("2026-10-07T00:00:00Z").datetime,
    }
    if periodic:
        rule.time_check = TimeMatchByDay(
            {"begin_time": "06:00:00", "end_time": "07:00:00"},
            arrow.get("2026-10-01T00:00:00Z"),
            arrow.get("2026-11-01T00:00:00Z"),
        )
    else:
        rule.time_check = TimeMatchBySingle({}, arrow.get("2026-10-08T06:00:00Z"), arrow.get("2026-10-08T07:00:00Z"))
    rule.dimension_check = Mock()
    rule.dimension_check.is_match.return_value = True
    rule.get_dimension = Mock(return_value={})
    return rule


def install_history(monkeypatch, rule, generated_at=NOW):
    rule.history_valid_since = max(arrow.get(rule.config[field]).timestamp for field in ("create_time", "update_time"))
    monkeypatch.setattr(saas_config, "time", SimpleNamespace(time=lambda: NOW))
    load = Mock(return_value=(generated_at, [rule]))
    monkeypatch.setattr(saas_config.AlertShieldConfigShielder, "_load_history", load)
    return load


@pytest.mark.parametrize("periodic", [False, True])
def test_replay_uses_existing_time_and_dimension_matcher(monkeypatch, periodic):
    rule = historical_rule(periodic)
    install_history(monkeypatch, rule)
    doc = make_alert().to_document()
    assert saas_config.AlertShieldConfigShielder.match_historical(doc, INSIDE) == ["10"]
    assert saas_config.AlertShieldConfigShielder.match_historical(doc, OUTSIDE) == []
    assert rule.dimension_check.is_match.call_count == 1
    rule.dimension_check.is_match.return_value = False
    assert saas_config.AlertShieldConfigShielder.match_historical(doc, INSIDE) == []


@pytest.mark.parametrize("case", ["edited", "created", "close", "stale", "too_old", "missing_time"])
def test_history_has_bounded_coverage(monkeypatch, case):
    rule = historical_rule()
    generated_at, source_time = NOW, INSIDE
    if case in {"edited", "created"}:
        rule.config["update_time" if case == "edited" else "create_time"] = arrow.get(OUTSIDE).datetime
    elif case == "close":
        rule.config["end_policy"] = "close"
    elif case == "stale":
        generated_at = NOW - 121
    elif case == "too_old":
        source_time = NOW - 86401
    else:
        source_time = 0
    install_history(monkeypatch, rule, generated_at)
    result = saas_config.AlertShieldConfigShielder.match_historical(make_alert().to_document(), source_time)
    assert result == ([] if case in {"edited", "created", "close"} else None)


@pytest.mark.parametrize("payload", [None, {"generated_at": NOW, "configs": []}])
def test_empty_and_missing_history_are_cached(monkeypatch, payload):
    load = Mock(return_value=payload)
    monkeypatch.setattr(ShieldCacheManager, "get_history_by_biz_id", load)
    monkeypatch.setattr(saas_config, "time", SimpleNamespace(time=lambda: NOW))
    doc = make_alert().to_document()
    for _ in range(1000):
        assert saas_config.AlertShieldConfigShielder.match_historical(doc, INSIDE) == ([] if payload else None)
    load.assert_called_once_with(2)


def test_cache_failure_is_not_retried_per_event(monkeypatch):
    load = Mock(side_effect=ConnectionError("fixture"))
    monkeypatch.setattr(ShieldCacheManager, "get_history_by_biz_id", load)
    monkeypatch.setattr(saas_config, "time", SimpleNamespace(time=lambda: NOW))
    doc = make_alert().to_document()
    for _ in range(1000):
        assert saas_config.AlertShieldConfigShielder.match_historical(doc, INSIDE) is None
    load.assert_called_once()


@pytest.mark.parametrize("tenant", ["tenant-a", "tenant-b", "tenant-c", "tenant-d"])
def test_compiled_history_reused_during_replay(monkeypatch, tenant):
    rule = historical_rule()
    rule.dimension_check = SimpleNamespace(is_match=lambda _: True)
    rule.get_dimension = lambda _: {}
    factory = Mock(return_value=rule)
    load = Mock(return_value={"generated_at": NOW, "configs": [rule.config]})
    monkeypatch.setattr(saas_config, "AlertShieldObj", factory)
    monkeypatch.setattr(ShieldCacheManager, "get_history_by_biz_id", load)
    monkeypatch.setattr(saas_config, "time", SimpleNamespace(time=lambda: NOW))
    doc = make_alert().to_document()
    doc.event.bk_tenant_id = tenant
    for _ in range(REPLAY_COUNT):
        assert saas_config.AlertShieldConfigShielder.match_historical(doc, INSIDE) == ["10"]
    load.assert_called_once()
    factory.assert_called_once()


def test_match_dependency_failure_falls_back_to_current(monkeypatch):
    rule = historical_rule()
    rule.get_dimension = Mock(side_effect=RuntimeError("missing strategy fixture"))
    install_history(monkeypatch, rule)
    assert saas_config.AlertShieldConfigShielder.match_historical(make_alert().to_document(), INSIDE) is None


def test_refresh_queries_once_and_separates_current_and_history(monkeypatch):
    from alarm_backends.core.cache import shield

    now = arrow.get(NOW).datetime
    active = {"id": 1, "bk_biz_id": 2, "end_time": now + timedelta(hours=1), "end_policy": "notify_once"}
    expired = {**active, "id": 2, "end_time": now - timedelta(hours=1)}
    closed = {**expired, "id": 3, "end_policy": "close"}
    query = Mock()
    query.filter.return_value.values.return_value = [active, expired, closed]
    cache = Mock()
    monkeypatch.setattr(shield, "Shield", SimpleNamespace(objects=query))
    monkeypatch.setattr(
        shield.BusinessManager, "all", lambda: [SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=3)]
    )
    monkeypatch.setattr(shield.time_tools, "now", lambda: now)
    monkeypatch.setattr(ShieldCacheManager, "cache", cache)
    ShieldCacheManager.refresh()
    query.filter.assert_called_once()
    assert query.filter.call_args.kwargs["end_time__gte"] == now - timedelta(hours=24)
    published = {c.args[0]: extended_json.loads(c.args[1]) for c in cache.pipeline.return_value.set.call_args_list}
    assert [c["id"] for c in published[ShieldCacheManager.CACHE_KEY_TEMPLATE.format(2)]] == [1]
    history = published[ShieldCacheManager.HISTORY_KEY_TEMPLATE.format(2)]
    assert history["generated_at"] == NOW
    assert [c["id"] for c in history["configs"]] == [1, 2]
    assert published[ShieldCacheManager.HISTORY_KEY_TEMPLATE.format(3)]["configs"] == []


def test_abnormal_time_ignores_recovery_and_old_representative_event():
    alert = make_alert()
    event = SimpleNamespace(
        id="fixture",
        description="fixture",
        time=OUTSIDE,
        anomaly_time=INSIDE,
        status=EventStatus.ABNORMAL,
        severity=2,
        to_dict=lambda: {},
    )
    alert.update(event)
    assert alert.latest_abnormal_event_time == OUTSIDE
    assert alert.top_event["time"] == INSIDE
    alert.RECOVER_WINDOW_SIZE = 60
    event.status, event.time = EventStatus.RECOVERED, OUTSIDE + 60
    alert.update(event)
    assert alert.latest_time == OUTSIDE + 60
    assert alert.latest_abnormal_event_time == OUTSIDE
    event.status, event.time = EventStatus.ABNORMAL, INSIDE
    alert.update(event)
    assert alert.latest_abnormal_event_time == OUTSIDE


@pytest.mark.parametrize("at", [INSIDE - 60, INSIDE, OUTSIDE])
def test_abnormal_progress_does_not_emit_extra_composite_signal(at):
    alert = make_alert()
    event = SimpleNamespace(
        id="fixture",
        description="fixture",
        time=at,
        anomaly_time=INSIDE,
        status=EventStatus.ABNORMAL,
        severity=1,
        to_dict=lambda: alert.top_event.copy(),
    )
    alert.update(event)
    assert not alert.should_send_signal()
    alert.preserve_notification_progress({"latest_abnormal_event_time": OUTSIDE + 60})
    assert not alert.should_send_signal()


def test_manager_uses_progress_read_after_acquiring_lock(monkeypatch):
    stale = make_alert()
    stale.data["dedupe_md5"] = "fixture"
    latest = make_alert(OUTSIDE)
    latest.data["dedupe_md5"] = "fixture"
    latest.extra_info["cycle_handle_record"] = {
        "7": {"latest_anomaly_time": OUTSIDE, "execute_times": 8, "is_shielded": False}
    }
    key = Mock()
    key.client.mget.return_value = [json.dumps(latest.data)]
    monkeypatch.setattr(manager_processor, "ALERT_DEDUPE_CONTENT_KEY", key)
    manager = manager_processor.AlertManager([])
    assert manager.filter_alerts([stale]) == [stale]
    assert stale.latest_abnormal_event_time == OUTSIDE
    assert not stale.cycle_handle_record["7"]["is_shielded"]


def test_old_snapshot_cannot_roll_back_notification_progress():
    alert = make_alert(OUTSIDE)
    alert.extra_info["cycle_handle_record"] = {
        "7": {"latest_anomaly_time": OUTSIDE, "execute_times": 2, "is_shielded": False}
    }
    alert.preserve_notification_progress(
        {
            "latest_abnormal_event_time": INSIDE,
            "cycle_handle_record": {"7": {"latest_anomaly_time": INSIDE, "execute_times": 8, "is_shielded": True}},
        }
    )
    assert alert.latest_abnormal_event_time == OUTSIDE
    assert alert.cycle_handle_record["7"] == {"latest_anomaly_time": OUTSIDE, "execute_times": 8, "is_shielded": False}
    assert not alert.is_valid_handle(0, 7)
    alert.update_extra_info("latest_abnormal_event_time", OUTSIDE + 60)
    assert alert.is_valid_handle(0, 7)
    assert not alert.is_valid_handle(0, 9)


@pytest.mark.parametrize("source_time", [0, OUTSIDE])
def test_database_record_falls_back_for_missing_source_time(monkeypatch, source_time):
    action = SimpleNamespace(
        end_time=None, execute_times=1, inputs={"shield_source_time": source_time, "alert_latest_time": INSIDE}
    )
    model = Mock()
    model.objects.filter.return_value.filter.return_value.only.return_value.order_by.return_value.first.return_value = (
        action
    )
    monkeypatch.setattr(alert_module, "ActionInstance", model)
    monkeypatch.setattr(
        alert_module.ActionInstanceDocument, "mget_by_alert", Mock(return_value=[SimpleNamespace(raw_id=1)])
    )
    assert make_alert().get_latest_interval_record(8, 7)["latest_anomaly_time"] == (source_time or INSIDE)


def make_parent(monkeypatch, alert, historical_ids, plugin=ActionPluginType.NOTICE):
    proc = object.__new__(create_action.CreateActionProcessor)
    for key, value in {
        "signal": ActionSignal.ABNORMAL,
        "strategy_id": 1,
        "severity": 1,
        "execute_times": 0,
        "is_alert_shielded": False,
        "shield_detail": "",
        "is_unshielded": False,
        "notice_type": ActionNoticeType.NORMAL,
        "historical_shield_ids": {alert.id: historical_ids},
        "generate_uuid": "fixture",
        "dimensions": [],
        "dimension_hash": "",
        "strategy": {},
    }.items():
        setattr(proc, key, value)
    proc.get_merged_notice_info = Mock(return_value=({}, {}))
    monkeypatch.setattr(create_action, "DoubleCheckHandler", Mock())
    assignees = Mock()
    assignees.get_appointees.return_value = []
    assignees.get_origin_notice_receivers.return_value = []
    return proc.do_create_action(
        {"id": 8, "bk_biz_id": 2},
        {"plugin_type": plugin},
        alert,
        action_relation={"id": 7, "options": {}},
        assignee_manager=assignees,
    )


def test_notice_freezes_history_and_preserves_counter(monkeypatch):
    alert = make_alert().to_document()
    alert.extra_info["cycle_handle_record"] = {
        "7": {"latest_anomaly_time": INSIDE - 60, "execute_times": 8, "is_shielded": False}
    }
    parent = make_parent(monkeypatch, alert, ["10"])
    assert parent.inputs["is_alert_shielded"]
    assert parent.inputs["shield_source_time"] == INSIDE
    assert not alert.is_shielded
    record = alert.cycle_handle_record["7"]
    assert record["is_shielded"] and record["execute_times"] == 8
    alert.extra_info["latest_abnormal_event_time"] = OUTSIDE
    assert parent.inputs["shield_source_time"] == INSIDE


def test_history_does_not_change_non_notice_action(monkeypatch):
    action = make_parent(monkeypatch, make_alert().to_document(), ["10"], plugin="webhook")
    assert not action.inputs["is_alert_shielded"]
    assert "historical_shield_ids" not in action.inputs


def test_parent_gate_is_per_alert_and_covers_all_channels(monkeypatch):
    blocked = Mock(inputs={"historical_shield_ids": ["10"]})
    allowed = Mock(inputs={})
    allowed.create_sub_actions.return_value = []
    model = Mock()
    model.objects.filter.side_effect = [[blocked, allowed], [blocked, allowed]]
    monkeypatch.setattr(utils, "ActionInstance", model)
    push = Mock()
    monkeypatch.setattr(utils.PushActionProcessor, "push_actions_to_converge_queue", push)
    utils.PushActionProcessor.push_actions_to_queue("fixture", alerts=[make_alert()])
    blocked.create_sub_actions.assert_not_called()
    allowed.create_sub_actions.assert_called_once()
    push.assert_called_once()


def test_manager_holds_old_notice_then_unshields_new_anomaly(monkeypatch):
    alert = make_alert()
    alert.extra_info["cycle_handle_record"] = {
        "7": {"latest_anomaly_time": INSIDE, "execute_times": 8, "is_shielded": True}
    }
    current = Mock()
    current.is_matched.return_value = False
    current.get_shield_left_time.return_value = 0
    current.list_shield_ids.return_value = []
    shielder = Mock(return_value=current)
    shielder.match_historical.return_value = ["10"]
    monkeypatch.setattr(shield_checker, "AlertShieldConfigShielder", shielder)
    checker = shield_checker.ShieldStatusChecker([alert])
    checker.check(alert)
    assert not checker.unshielded_actions and not alert.is_shielded
    alert.update_extra_info("latest_abnormal_event_time", OUTSIDE)
    shielder.match_historical.return_value = []
    checker.check(alert)
    assert len(checker.unshielded_actions) == 1
    assert not alert.cycle_handle_record["7"]["is_shielded"]
    checker.check(alert)
    assert len(checker.unshielded_actions) == 1


def test_cycle_prewrite_keeps_history_and_requires_new_abnormal_point(monkeypatch):
    alert = make_alert(OUTSIDE)
    alert.extra_info["cycle_handle_record"] = {"7": {"latest_anomaly_time": INSIDE, "execute_times": 8, "last_time": 0}}
    config = {"execute_config": {"template_detail": {"notify_interval": 1}}}
    monkeypatch.setattr(action_checker.ActionConfigCacheManager, "get_action_config_by_id", Mock(return_value=config))
    monkeypatch.setattr(action_checker.AlertShieldConfigShielder, "match_historical", Mock(return_value=["10"]))
    enqueue = Mock()
    monkeypatch.setattr(action_checker.create_interval_actions, "delay", enqueue)
    checker = action_checker.ActionHandleChecker([alert])
    checker.check(alert)
    assert alert.cycle_handle_record["7"]["is_shielded"]
    alert.data["latest_time"] = OUTSIDE + 60
    alert.cycle_handle_record["7"]["last_time"] = 0
    checker.check(alert)
    enqueue.assert_called_once()
