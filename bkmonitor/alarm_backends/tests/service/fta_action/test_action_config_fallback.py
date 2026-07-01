"""
处理套餐缓存未传播兜底相关单测:

覆盖"新建/克隆策略秒级出告警, 套餐尚未刷入 action_config 缓存"被误判为已删除/停用的场景,
验证读路径按策略变更时效门控的 DB 兜底 + 写回 + 负缓存防穿透, 以及无效文案的区分。
"""

import time
from unittest.mock import MagicMock, patch

from django.test import override_settings

from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor
from constants.action import ActionNoticeType, ActionSignal


class _StubProcessor:
    """最小替身, 仅承载 resolve_missing_action_config 依赖的属性。"""

    def __init__(self, strategy, strategy_id=1):
        self.strategy = strategy
        self.strategy_id = strategy_id


def _resolve(strategy, config_id=100):
    stub = _StubProcessor(strategy)
    return CreateActionProcessor.resolve_missing_action_config(stub, config_id)


def _recent_ts():
    return int(time.time()) - 10


def _old_ts():
    return int(time.time()) - 100000


class _FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, timeout=None):
        self.store[key] = value


# ---------------- resolve_missing_action_config 门控 ----------------


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=False)
def test_resolve_disabled_skips_db():
    with patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db:
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_old_strategy_skips_db_no_penetration():
    # 稳定老策略缓存缺失 = 真删, 不回查 DB(防穿透), 也不写负缓存
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db,
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _old_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()
    m_neg.assert_not_called()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_recent_strategy_db_hit_writes_back():
    db_cfg = {"id": 100, "is_enabled": True, "plugin_id": "1", "name": "x"}
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", return_value=db_cfg) as m_db,
        patch.object(ActionConfigCacheManager, "set_action_config_cache") as m_set,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == db_cfg
    assert pending is False
    m_db.assert_called_once()
    m_set.assert_called_once()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True, ACTION_CONFIG_NEGATIVE_CACHE_TTL=60)
def test_resolve_recent_strategy_db_miss_negative_cache():
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", return_value={}) as m_db,
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_called_once()
    m_neg.assert_called_once()
    assert m_neg.call_args[0][1] == 60  # ttl 透传


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_recent_strategy_db_error_marks_pending():
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", side_effect=RuntimeError("boom")),
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is True  # 异常无法确认, 标记疑似尚未生效
    m_neg.assert_not_called()


def test_resolve_without_update_time_skips_db():
    with patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db:
        cfg, pending = _resolve({})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()


# ---------------- is_action_config_valid 文案分支 ----------------


def _run_valid(action_config, config_id, suspected_pending):
    alert = MagicMock()
    alert.id = "1"
    with patch("alarm_backends.service.fta_action.tasks.create_action.AlertLog") as m_log:
        ret = CreateActionProcessor.is_action_config_valid(alert, action_config, config_id, suspected_pending)
    return ret, m_log


def test_valid_enabled_config_no_log():
    ret, m_log = _run_valid({"is_enabled": True, "name": "x"}, 100, False)
    assert ret is True
    m_log.bulk_create.assert_not_called()


def test_invalid_deleted_message():
    ret, m_log = _run_valid({}, 100, False)
    assert ret is False
    assert "已经被删除或禁用" in m_log.call_args.kwargs["description"]


def test_invalid_pending_message():
    ret, m_log = _run_valid({}, 100, True)
    assert ret is False
    assert "配置尚未生效" in m_log.call_args.kwargs["description"]


def test_negative_sentinel_is_invalid_with_deleted_message():
    sentinel = {"id": 100, "is_enabled": False, ActionConfigCacheManager.NEGATIVE_CACHE_FLAG: True}
    ret, m_log = _run_valid(sentinel, 100, False)
    assert ret is False
    assert "已经被删除或禁用" in m_log.call_args.kwargs["description"]


# ---------------- 缓存管理方法 ----------------


def test_negative_cache_roundtrip_is_truthy_but_disabled():
    fake = _FakeCache()
    with patch.object(ActionConfigCacheManager, "cache", fake):
        ActionConfigCacheManager.set_negative_cache(100, 60)
        got = ActionConfigCacheManager.get_action_config_by_id(100)
    assert got  # 非空, 故不会再次触发 DB 兜底
    assert got.get("is_enabled") is False
    assert got.get(ActionConfigCacheManager.NEGATIVE_CACHE_FLAG) is True


def test_get_from_db_missing_returns_empty():
    with patch("alarm_backends.core.cache.action_config.ActionConfig") as m_ac:
        m_ac.objects.filter.return_value.first.return_value = None
        assert ActionConfigCacheManager.get_action_config_from_db(100) == {}


def test_get_from_db_found_serializes():
    with (
        patch("alarm_backends.core.cache.action_config.ActionConfig") as m_ac,
        patch("alarm_backends.core.cache.action_config.ActionConfigDetailSlz") as m_slz,
    ):
        m_ac.objects.filter.return_value.first.return_value = object()
        m_slz.return_value.data = {"id": 100, "is_enabled": True}
        out = ActionConfigCacheManager.get_action_config_from_db(100)
    assert out == {"id": 100, "is_enabled": True}


# ---------------- 批内去重: 同批多条告警引用同一缺失套餐, DB 只回查一次 ----------------

_CA = "alarm_backends.service.fta_action.tasks.create_action"


def _make_alert(alert_id):
    alert = MagicMock()
    alert.id = alert_id
    alert.to_dict.return_value = {}
    alert.is_no_data.return_value = False
    return alert


def _build_processor(missing_config_id, alert_ids):
    """绕过重量级 __init__, 仅注入 do_create_actions 走到处理套餐解析所需的最小属性与桩。"""
    proc = CreateActionProcessor.__new__(CreateActionProcessor)
    proc.strategy_id = 1
    proc.signal = ActionSignal.ABNORMAL
    proc.severity = 1
    proc.relation_id = None
    proc.execute_times = 0
    proc.notice_type = ActionNoticeType.NORMAL
    proc.is_alert_shielded = False
    proc.noise_reduce_result = False
    proc.generate_uuid = "uuid"
    proc.notice = {}
    # 策略近期变更 -> 命中兜底门控
    proc.strategy = {"update_time": int(time.time()) - 10}
    alerts = [_make_alert(aid) for aid in alert_ids]
    proc.alerts = alerts
    proc.alert_ids = list(alert_ids)
    proc.alert_objs = {a.id: a for a in alerts}

    action = {"config_id": missing_config_id, "id": 1, "options": {}, "signal": [ActionSignal.ABNORMAL]}
    assignee_manager = MagicMock()
    assignee_manager.is_matched = True
    assignee_manager.match_manager = None
    assignee_manager.get_assignees.return_value = []

    # 桩掉处理套餐解析之外的协作者, 让 do_create_actions 干净地走到 action 循环并在无效套餐处 continue
    proc.get_action_relations = MagicMock(return_value=[action])
    proc.get_alert_shield_result = MagicMock(return_value=(False, []))
    proc.create_message_queue_action = MagicMock()
    proc.is_alert_status_valid = MagicMock(return_value=True)
    proc.alert_assign_handle = MagicMock(return_value=assignee_manager)
    proc.get_alert_related_users = MagicMock(return_value=[])
    proc.update_alert_documents = MagicMock()
    proc._process_issue_aggregation = MagicMock()
    return proc


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_batch_missing_config_db_queried_once_across_alerts():
    missing_cid = 999001
    proc = _build_processor(missing_cid, alert_ids=["alert-1", "alert-2"])

    with (
        patch.object(ActionConfigCacheManager, "get_action_config_by_id", return_value={}),
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", return_value={}) as m_db,
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
        patch(f"{_CA}.ActionPlugin"),
        patch(f"{_CA}.ActionPluginSlz") as m_plugin_slz,
        patch(f"{_CA}.AssignCacheManager"),
        patch(f"{_CA}.SubscribeCacheManager"),
        patch(f"{_CA}.AlertLog") as m_alertlog,
    ):
        m_plugin_slz.return_value.data = []
        proc.do_create_actions()

    # 两条告警引用同一缺失套餐, 但 DB 只回查一次, 负缓存只写一次 -> 批内无穿透
    assert m_db.call_count == 1
    assert m_neg.call_count == 1
    # 两条告警各记录一条"已删除或禁用"的 AlertLog
    deleted_logs = [c for c in m_alertlog.call_args_list if "已经被删除或禁用" in (c.kwargs.get("description") or "")]
    assert len(deleted_logs) == 2
