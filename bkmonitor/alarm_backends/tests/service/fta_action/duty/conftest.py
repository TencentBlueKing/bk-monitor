import pytest

from bkmonitor.action.serializers import DutyRuleDetailSlz, UserGroupDetailSlz
from constants.common import DutyGroupType, RotationType


@pytest.fixture
def specified_duty_arrange():
    return {
        "duty_users": [
            [
                {"id": "user1", "type": "user"},
                {"id": "user2", "type": "user"},
            ],
            [
                {"id": "user3", "type": "user"},
                {"id": "user4", "type": "user"},
            ],
        ],
        "duty_time": [],
        "group_type": DutyGroupType.SPECIFIED,
        "group_number": 1,
    }


@pytest.fixture
def auto_duty_arrange():
    return {
        "duty_users": [
            [
                {"id": "user1", "type": "user"},
                {"id": "user2", "type": "user"},
                {"id": "user3", "type": "user"},
            ]
        ],
        "duty_time": [],
        "group_type": DutyGroupType.AUTO,
        "group_number": 2,
    }


@pytest.fixture
def daily_duty_time():
    return {
        "work_type": RotationType.DAILY,
        "work_days": [],
        "work_time_type": "time_range",
        "work_time": ["09:00--18:00"],
    }


@pytest.fixture
def weekly_duty_time():
    return {
        "work_type": RotationType.WEEKLY,
        "work_days": [1, 3, 5],
        "work_time_type": "time_range",
        "work_time": ["09:00--18:00"],
    }


@pytest.fixture
def create_duty_rule(auto_duty_arrange, specified_duty_arrange, daily_duty_time, weekly_duty_time):
    def _create_duty_rule(group_type=DutyGroupType.AUTO, work_type=RotationType.DAILY, end_time=""):
        rule_data = {
            "bk_biz_id": 2,
            "name": "rule_for_biz2",
            "category": "handoff",
            "duty_arranges": [],
            "effective_time": "2024-06-01 00:00:00",
            "end_time": end_time,
            "enabled": True,
        }
        arrange = auto_duty_arrange if group_type == DutyGroupType.AUTO else specified_duty_arrange
        arrange["duty_time"] = [daily_duty_time if work_type == RotationType.DAILY else weekly_duty_time]
        rule_data["duty_arranges"] = [arrange]

        rule_serializer = DutyRuleDetailSlz(data=rule_data)
        rule_serializer.is_valid(raise_exception=True)
        return rule_serializer.save()

    return _create_duty_rule


@pytest.fixture
def create_user_group():
    def _create_user_group(rule_ids):
        user_group_data = {
            "bk_biz_id": 2,
            "name": "user_group_for_biz_2",
            "desc": "",
            "need_duty": True,
            "duty_rules": rule_ids,
            "mention_list": [{"type": "group", "id": "all"}],
            "channels": [],
            "alert_notice": [],
            "action_notice": [],
        }
        group_serializer = UserGroupDetailSlz(data=user_group_data)
        group_serializer.is_valid(raise_exception=True)
        return group_serializer.save()

    return _create_user_group
