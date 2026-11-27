from copy import deepcopy
from unittest.mock import Mock

import pytest
from fta_web.assign.resources import BatchUpdateResource, MatchDebugResource

from bkmonitor.action.serializers.assign import AssignRuleSlz, BatchSaveAssignRulesSlz
from bkmonitor.action.utils import (
    get_action_config_rules,
    get_assign_rule_related_resource_dict,
    get_user_group_assign_rules,
)
from bkmonitor.models import AlertAssignGroup, AlertAssignRule


def make_rule(**kwargs):
    return {
        "conditions": [{"field": "labels", "value": ["test"], "method": "eq"}],
        "actions": [],
        "user_groups": [],
        "is_enabled": True,
        **kwargs,
    }


@pytest.mark.parametrize(
    ("options", "valid"),
    [
        ({"dispatch_config": {"ai_analysis": {"user_groups": []}}}, True),
        ({"dispatch_config": {"ai_analysis": {"user_groups": [0]}}}, False),
        ({"dispatch_config": {"noise": True}}, True),
        ({"dispatch_config": {"noise": True, "ai_analysis": {"user_groups": []}}}, False),
        ({"dispatch_config": {"noise": True}, "actions": [{"action_type": "notice"}], "user_groups": [2]}, False),
        ({"dispatch_config": {"noise": True}, "actions": [{"action_type": "itsm", "action_id": 1}]}, False),
        ({"dispatch_config": {"noise": True}, "actions": [{"action_type": "notice", "is_enabled": False}]}, True),
        ({"dispatch_config": {"ai_analysis": {"user_groups": [1]}}, "actions": [{"action_type": "notice"}]}, False),
        ({"actions": [{"action_type": "notice"}], "user_groups": [1]}, True),
        ({"actions": [{"action_type": "notice"}]}, False),
        ({"dispatch_config": {"noise": True}, "conditions": []}, False),
    ],
)
def test_dispatch_rule_validation(options, valid):
    rule = make_rule(**options)
    detail = AssignRuleSlz(data={"assign_group_id": 1, "bk_biz_id": 2, **rule})
    group = MatchDebugResource.RequestSerializer(data={"bk_biz_id": 2, "rules": [deepcopy(rule)]})
    for serializer in (detail, group):
        assert serializer.is_valid() is valid, serializer.errors


@pytest.mark.django_db
def test_dispatch_config_storage_and_legacy_edits():
    group = AlertAssignGroup.objects.create(name="test", bk_biz_id=2, priority=1)
    resource = BatchUpdateResource()
    common = {"bk_biz_id": 2, "assign_group_id": group.id}

    def update(rule):
        return resource.request(request_data={**common, "priority": 1, "rules": [rule]})["rules"][0]

    rule_id = update(make_rule(dispatch_config={"ai_analysis": {"user_groups": [7]}}))
    instance = AlertAssignRule.objects.get(pk=rule_id)
    assert instance.actions == [{"action_type": "ai_analysis", "user_groups": [7], "is_enabled": True}]
    assert AssignRuleSlz(instance).data["actions"] == []
    assert AssignRuleSlz(instance).data["dispatch_config"] == {"ai_analysis": {"user_groups": [7]}, "noise": False}
    assert AssignRuleSlz(instance, context={"for_match": True}).data["actions"] == instance.actions
    assert get_user_group_assign_rules([7], bk_biz_ids=[2]) == {7: [rule_id]}
    assert get_assign_rule_related_resource_dict([group.id]) == {"user_groups": [7], "action_ids": []}

    inherit = AssignRuleSlz(instance, data={"user_groups": [8], "dispatch_config": {"ai_analysis": {}}}, partial=True)
    inherit.is_valid(raise_exception=True)
    inherit.save()
    instance.refresh_from_db()
    assert AssignRuleSlz(instance).data["dispatch_config"] == {"ai_analysis": {}, "noise": False}
    assert instance.actions == [{"action_type": "ai_analysis", "is_enabled": True}]
    assert get_user_group_assign_rules([7, 8], bk_biz_ids=[2]) == {8: [rule_id]}
    assert get_assign_rule_related_resource_dict([group.id]) == {"user_groups": [8], "action_ids": []}

    # 旧客户端在新配置提交前已校验完成，真正保存时仍要保留最新的噪声备注。
    legacy_edit = resource.validate_request_data({**common, "priority": 1, "rules": [make_rule(id=rule_id)]})
    update(make_rule(id=rule_id, dispatch_config={"noise": True, "noise_remark": "  planned maintenance "}))
    resource.perform_request(legacy_edit)
    instance.refresh_from_db()
    assert instance.actions == [{"action_type": "noise", "is_enabled": True, "remark": "planned maintenance"}]
    assert AssignRuleSlz(instance).data["dispatch_config"] == {
        "ai_analysis": None,
        "noise": True,
        "noise_remark": "planned maintenance",
    }
    preview = MatchDebugResource.RequestSerializer(data={**common, "rules": [make_rule(id=rule_id)]})
    preview.is_valid(raise_exception=True)
    assert preview.validated_data["rules"][0]["actions"] == instance.actions

    # 单条 PATCH 切换启用状态、清除备注、换回普通通知。
    for patch, expected in [
        ({"is_enabled": False}, instance.actions),
        ({"dispatch_config": {"noise": True}}, [{"action_type": "noise", "is_enabled": True}]),
        (
            {"dispatch_config": {}, "user_groups": [2], "actions": [{"action_type": "notice"}]},
            [{"action_type": "notice", "is_enabled": True}],
        ),
    ]:
        serializer = AssignRuleSlz(instance, data=patch, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.refresh_from_db()
        assert instance.actions == expected

    # 后台和 AsCode 共用的批量写入口也支持清空普通接收组、单独开启无接收组的分析。
    batch = BatchSaveAssignRulesSlz(
        data={
            **common,
            "priority": 1,
            "name": "test",
            "rules": [make_rule(id=rule_id, dispatch_config={"ai_analysis": {"user_groups": []}})],
        }
    )
    batch.is_valid(raise_exception=True)
    batch.save(batch.validated_data)
    instance.refresh_from_db()
    assert instance.actions == [{"action_type": "ai_analysis", "user_groups": [], "is_enabled": True}]


def test_only_configured_packages_are_reported(monkeypatch):
    # JSON contains 查询由生产 MySQL 执行，返回的整行仍包含 AI/噪声动作。
    queryset = Mock()
    queryset.filter.return_value.values.return_value = [
        {
            "id": 4,
            "actions": [{"action_type": "itsm", "action_id": 1}, {"action_type": "ai_analysis", "user_groups": []}],
        }
    ]
    monkeypatch.setattr(AlertAssignRule.objects, "filter", Mock(return_value=queryset))
    assert get_action_config_rules([1], 2) == {1: [4]}
