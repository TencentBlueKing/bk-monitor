from copy import deepcopy
from unittest.mock import Mock, patch

from alarm_backends.service.alert.enricher.rule_assign import AssignInfoEnricher


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
    ordinary.update_extra_info.assert_called_once_with("matched_rule_info", manager.matched_rule_info)
