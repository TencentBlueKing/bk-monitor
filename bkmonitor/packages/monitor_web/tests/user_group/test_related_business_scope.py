from collections import defaultdict

import pytest

from bkmonitor.action.serializers.strategy import (
    DutyArrangeSlz,
    DutyBaseInfoSlz,
    DutyRuleDetailSlz,
    UserGroupDetailSlz,
)
from bkmonitor.models import DutyArrange, DutyRule, UserGroup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("parent_type", ["group", "rule"])
@pytest.mark.parametrize("target_biz", [0, 3])
def test_nested_arranges_cannot_set_either_owner(parent_type, target_biz):
    foreign_group = UserGroup.objects.create(bk_biz_id=target_biz, name="foreign-group")
    foreign_rule = DutyRule.objects.create(bk_biz_id=target_biz, name="foreign-rule")
    foreign_arrange = DutyArrange.objects.create(
        user_group_id=foreign_group.id,
        duty_rule_id=foreign_rule.id,
        users=[{"id": "original", "type": "user"}],
        hash="original",
    )
    model, serializer_class = (
        (UserGroup, UserGroupDetailSlz) if parent_type == "group" else (DutyRule, DutyRuleDetailSlz)
    )
    parent = model.objects.create(bk_biz_id=2, name="own")
    params = {
        "bk_biz_id": 2,
        "name": "own",
        "alert_notice": [],
        "action_notice": [],
        "effective_time": "2026-01-01 00:00:00",
        "duty_arranges": [
            {
                "user_group_id": foreign_group.id,
                "duty_rule_id": foreign_rule.id,
                "users": [{"id": "replacement", "type": "user"}],
            }
        ],
    }
    serializer = serializer_class(parent, data=params)
    assert serializer.is_valid(), serializer.errors
    arrange_data = serializer.validated_data["duty_arranges"]
    assert "user_group_id" not in arrange_data[0]
    assert "duty_rule_id" not in arrange_data[0]

    # Use the real persistence method called by both parent serializers.
    DutyArrange.bulk_create(arrange_data, parent)
    created = DutyArrange.objects.exclude(id=foreign_arrange.id).get()
    assert created.user_group_id == (parent.id if parent_type == "group" else None)
    assert created.duty_rule_id == (parent.id if parent_type == "rule" else None)
    foreign_arrange.refresh_from_db()
    assert foreign_arrange.users == [{"id": "original", "type": "user"}]


@pytest.mark.parametrize(
    "group_biz,rule_biz,valid",
    [(2, 0, True), (2, 2, True), (-2, 0, True), (-2, -2, True), (0, 0, True), (2, 3, False), (0, 2, False)],
)
def test_group_rule_references_stay_within_own_business_and_platform(group_biz, rule_biz, valid):
    rule = DutyRule.objects.create(bk_biz_id=rule_biz, name="rule")
    serializer = UserGroupDetailSlz(
        data={
            "bk_biz_id": group_biz,
            "name": "group",
            "need_duty": True,
            "duty_rules": [rule.id],
            "alert_notice": [],
            "action_notice": [],
        }
    )
    assert serializer.is_valid() is valid, serializer.errors
    if valid:
        assert serializer.validated_data["duty_rules"] == [rule.id]
    else:
        assert "duty_rules" in serializer.errors


def test_missing_rule_and_spoofed_platform_group_business_are_rejected():
    group = UserGroup.objects.create(bk_biz_id=0, name="platform")
    own_rule = DutyRule.objects.create(bk_biz_id=2, name="business-rule")
    for rule_id in [own_rule.id, own_rule.id + 1]:
        serializer = UserGroupDetailSlz(
            group,
            data={
                "bk_biz_id": 2,
                "name": "platform",
                "duty_rules": [rule_id],
                "alert_notice": [],
                "action_notice": [],
            },
        )
        assert not serializer.is_valid()
        assert "duty_rules" in serializer.errors
    group.refresh_from_db()
    assert group.bk_biz_id == 0 and group.duty_rules == []


def test_migrated_same_business_arrange_keeps_server_owned_relations(monkeypatch):
    group = UserGroup.objects.create(bk_biz_id=2, name="group")
    rule = DutyRule.objects.create(bk_biz_id=2, name="rule")
    serializer = DutyArrangeSlz(data={"users": []})
    assert serializer.is_valid(), serializer.errors
    arrange = DutyArrange.objects.create(user_group_id=group.id, duty_rule_id=rule.id, **serializer.validated_data)
    DutyArrange.bulk_create([serializer.validated_data], rule)
    arrange.refresh_from_db()
    assert arrange.user_group_id == group.id and arrange.duty_rule_id == rule.id

    monkeypatch.setattr(DutyBaseInfoSlz, "get_all_recievers", staticmethod(lambda: defaultdict(dict)))
    represented = DutyArrangeSlz(arrange).data
    assert represented["user_group_id"] == group.id and represented["duty_rule_id"] == rule.id
