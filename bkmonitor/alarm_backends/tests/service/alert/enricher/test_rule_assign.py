import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

import pytest

from alarm_backends.core.alert import Alert
from alarm_backends.core.context.alarm import Alarm
from alarm_backends.service.alert.enricher.rule_assign import AssignInfoEnricher
from bkmonitor.documents import AlertLog


def make_alert(shield_end_close=False):
    alert = Mock(shield_end_close=shield_end_close, bk_biz_id=2, top_event={"plugin_id": "bkmonitor"})
    alert.is_new.return_value = True
    alert.get_extra_info.return_value = None
    alert.data = {"severity": 3, "assign_tags": [{"key": "team", "value": "original"}]}
    alert.update_severity.side_effect = lambda severity: alert.data.update(severity=severity)
    alert.update_assign_tags.side_effect = lambda tags: alert.data.update(assign_tags=tags)
    return alert


def configure_assignment(manager_class):
    manager = manager_class.return_value.match_manager
    manager.matched_rule_info = {"severity": 1, "additional_tags": [{"key": "team", "value": "assigned"}]}
    manager.matched_group_info = {"group_id": 1}
    manager.severity_source = "rule"
    manager.get_alert_log.return_value = {"op_type": "ASSIGN"}
    return manager


@patch("alarm_backends.service.alert.enricher.rule_assign.AlertAssigneeManager")
def test_owned_alert_skips_assignment_and_keeps_severity_and_tags(manager_class):
    configure_assignment(manager_class)
    alert = make_alert(shield_end_close=True)
    original = deepcopy(alert.data)

    assert AssignInfoEnricher([alert]).enrich_alert(alert) is alert

    manager_class.assert_not_called()
    assert alert.data == original
    alert.update_severity_source.assert_not_called()
    alert.update_extra_info.assert_not_called()
    alert.add_log.assert_not_called()


@patch("alarm_backends.service.alert.enricher.rule_assign.AlertAssigneeManager")
def test_mixed_batch_keeps_ordinary_assignment(manager_class):
    manager = configure_assignment(manager_class)
    owned = make_alert(shield_end_close=True)
    ordinary = make_alert()
    original = deepcopy(owned.data)

    assert AssignInfoEnricher([owned, ordinary]).enrich() == [owned, ordinary]

    manager_class.assert_called_once_with(
        alert=ordinary.to_document.return_value,
        notice_user_groups=[],
        assign_mode=["by_rule"],
        new_alert=True,
    )
    assert owned.data == original
    assert ordinary.data == {"severity": 1, "assign_tags": manager.matched_rule_info["additional_tags"]}
    ordinary.update_severity_source.assert_called_once_with("rule")
    ordinary.update_extra_info.assert_has_calls(
        [
            call("dispatch_evaluation", {"status": "matched", "evaluated_at": ANY}),
            call("matched_rule_info", manager.matched_rule_info),
        ]
    )


@pytest.mark.parametrize("status", ["unmatched", "failed", "not_executed"])
@patch("alarm_backends.service.alert.enricher.rule_assign.time.time", return_value=1700000000)
@patch("alarm_backends.service.alert.enricher.rule_assign.AlertAssigneeManager")
def test_records_observed_dispatch_status(manager_class, clock, status):
    alert = make_alert()
    if status == "failed":
        manager_class.side_effect = RuntimeError("cache read failed")
    elif status == "not_executed":
        manager_class.return_value.match_manager = None
    else:
        manager = configure_assignment(manager_class)
        manager.matched_rules = []
        manager.matched_rule_info = {"severity": 0, "additional_tags": []}
    AssignInfoEnricher([alert]).enrich_alert(alert)
    expected_time = None if status == "not_executed" else 1700000000
    alert.update_extra_info.assert_any_call("dispatch_evaluation", {"status": status, "evaluated_at": expected_time})
    alert.add_log.assert_not_called()


@pytest.mark.parametrize(
    ("result", "tag", "noise"),
    [
        ({"noise": True, "ai_analysis": None}, "is_noise", True),
        ({"noise": False, "ai_analysis": {"user_groups": [37]}}, "is_ai_analyze", False),
    ],
)
@patch("alarm_backends.service.alert.enricher.rule_assign.AlertAssigneeManager")
def test_frozen_dispatch_result_reaches_document_and_full_queue_message(manager_class, result, tag, noise):
    manager = configure_assignment(manager_class)
    manager.matched_rule_info.update(severity=0, dispatch_result=result)
    alert = Alert(
        {
            "id": "alert-id",
            "begin_time": 10,
            "create_time": 10,
            "latest_time": 10,
            "first_anomaly_time": 10,
            "event": {"bk_biz_id": 2, "tags": [{"key": "is_ai_analyze", "value": "true"}] if noise else []},
            "assign_tags": [{"key": "is_ai_analyze", "value": "true"}] if noise else [],
            "extra_info": {"strategy": {"notice": {"user_groups": [], "options": {"assign_mode": ["by_rule"]}}}},
        }
    )
    alert._is_new = True
    AssignInfoEnricher([alert]).enrich()
    assert manager_class.call_args.kwargs["notice_user_groups"] == []
    assert manager_class.call_args.kwargs["assign_mode"] == ["by_rule"]
    doc = alert.to_document(include_all_fields=False)
    expected = [{"key": "team", "value": "assigned"}, {"key": tag, "value": "true"}]
    assert doc.to_dict()["assign_tags"] == expected
    assert doc.to_dict()["event"]["tags"] == expected
    assert doc.is_dispatch_noise is noise
    assert [log["op_type"] for log in alert.logs] == ([AlertLog.OpType.DISPATCH_NOISE] if noise else ["ASSIGN"])

    # 由快照重载的告警维持创建时的分类，不重复匹配或生成标噪流水。
    reloaded = Alert(doc.to_dict())
    AssignInfoEnricher([reloaded]).enrich()
    assert manager_class.call_count == 1
    assert reloaded.is_dispatch_noise is noise
    assert reloaded.logs == []
    alarm = Alarm(SimpleNamespace(alert=doc))
    alarm.__dict__.update(is_shielded=False, current_value=1, description="alert", log_related_info={}, related_info={})
    payload = json.loads(alarm.alert_info)
    assert payload["assign_tags"] == expected
    assert "extra_info" not in payload
    assert "dispatch_result" not in payload and "ai_analysis" not in payload
    assert doc.to_dict()["extra_info"]["matched_rule_info"]["dispatch_result"] == result
