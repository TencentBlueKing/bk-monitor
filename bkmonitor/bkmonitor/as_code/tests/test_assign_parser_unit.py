from copy import deepcopy

import pytest

from bkmonitor.as_code.parse_yaml import AssignGroupRuleParser


@pytest.mark.parametrize(
    ("dispatch", "exported_dispatch"),
    [
        (
            {"ai_analysis": None, "noise": True, "noise_remark": "例行维护"},
            {"ai_analysis": None, "noise": True, "noise_remark": "例行维护"},
        ),
        (
            {"ai_analysis": {"user_groups": [1]}, "noise": False},
            {"ai_analysis": {"user_groups": ["分析结果"]}, "noise": False},
        ),
        ({"ai_analysis": {"user_groups": []}, "noise": False}, {"ai_analysis": {"user_groups": []}, "noise": False}),
        ({"ai_analysis": {}, "noise": False}, {"ai_analysis": {}, "noise": False}),
    ],
)
def test_dispatch_config_as_code_roundtrip(dispatch, exported_dispatch):
    parser = AssignGroupRuleParser(2, notice_group_ids={"分析结果": 1}, action_ids={})
    config = {
        "name": "测试",
        "priority": 1,
        "rules": [
            {
                "user_groups": [],
                "actions": [],
                "is_enabled": True,
                "conditions": [{"field": "labels", "value": ["test"], "method": "eq"}],
                "dispatch_config": deepcopy(dispatch),
            }
        ],
    }
    exported = parser.unparse(config)
    assert exported["rules"][0]["dispatch_config"] == exported_dispatch
    restored = parser.parse(parser.check(exported))["rules"][0]
    assert not restored["actions"][0]["is_enabled"]
    assert restored["dispatch_config"] == dispatch


@pytest.mark.parametrize("rule_enabled", [True, False])
@pytest.mark.parametrize("notice_enabled", [True, False])
@pytest.mark.parametrize(
    "action_fields, upgrade_enabled, interval, user_groups",
    [
        pytest.param({}, False, 1440, [], id="missing"),
        pytest.param({"upgrade_config": None}, False, 1440, [], id="null"),
        pytest.param({"upgrade_config": {}}, False, 1440, [], id="empty"),
        pytest.param({"upgrade_config": {"is_enabled": False}}, False, 1440, [], id="disabled-without-groups"),
        pytest.param({"upgrade_config": {"user_groups": [2]}}, False, 1440, ["升级组"], id="default-options"),
        pytest.param(
            {"upgrade_config": {"is_enabled": False, "upgrade_interval": 0, "user_groups": []}},
            False,
            0,
            [],
            id="complete-disabled",
        ),
        pytest.param(
            {"upgrade_config": {"is_enabled": True, "upgrade_interval": 30, "user_groups": [2]}},
            True,
            30,
            ["升级组"],
            id="complete-enabled",
        ),
    ],
)
def test_assign_upgrade_config_export_roundtrip(
    action_fields, upgrade_enabled, interval, user_groups, rule_enabled, notice_enabled
):
    parser = AssignGroupRuleParser(2, notice_group_ids={"日常运维": 1, "升级组": 2}, action_ids={"test": 23})
    config = {
        "name": "分派测试",
        "priority": 1,
        "rules": [
            {
                "user_groups": [1],
                "is_enabled": rule_enabled,
                "conditions": [{"field": "bcs_cluster_id", "value": ["123"], "method": "eq", "condition": "and"}],
                "actions": [
                    {"action_type": "notice", "is_enabled": notice_enabled, **deepcopy(action_fields)},
                    {"action_type": "itsm", "is_enabled": True, "action_id": 23},
                ],
            }
        ],
    }

    exported = parser.unparse(config)
    rule = exported["rules"][0]
    assert rule["upgrade_config"] == {"enabled": upgrade_enabled, "interval": interval, "user_groups": user_groups}
    assert rule["enabled"] is rule_enabled
    assert rule.get("notice_enabled", True) is notice_enabled
    assert rule["actions"] == [{"enabled": True, "name": "test", "type": "itsm"}]

    restored = parser.parse(parser.check(exported))["rules"][0]
    assert restored["is_enabled"] is rule_enabled
    assert restored["user_groups"] == [1]
    assert restored["actions"][0] == {
        "action_type": "notice",
        "is_enabled": notice_enabled,
        "upgrade_config": {
            "is_enabled": upgrade_enabled,
            "upgrade_interval": interval,
            "user_groups": [2] if user_groups else [],
        },
    }
