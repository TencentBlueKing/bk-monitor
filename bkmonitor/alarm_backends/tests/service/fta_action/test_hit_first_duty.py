import pytest
from unittest import mock
from collections import defaultdict
from alarm_backends.service.fta_action.utils import AlertAssignee
from bkmonitor.models import UserGroup


@pytest.fixture
def mock_assignee():
    # 创建mock对象
    assignee = mock.MagicMock(spec=AlertAssignee)

    # 设置必要的属性
    assignee.all_group_users = defaultdict(list)
    assignee.biz_group_users = {"group1": ["user1", "user2"], "group2": ["user3"]}

    assignee.alert = mock.MagicMock()
    assignee.alert.id = "test_alert_1"

    original_method = AlertAssignee.get_group_duty_users.__get__(assignee)
    assignee.get_group_duty_users = original_method

    return assignee


def create_test_group(hit_first_duty=None):
    """创建测试用户组"""
    group = mock.MagicMock(spec=UserGroup)
    group.id = 1
    group.timezone = "Asia/Shanghai"
    group.duty_rules = [101, 102]

    # 设置duty_notice
    if hit_first_duty is None:
        group.duty_notice = {}
    else:
        group.duty_notice = {"hit_first_duty": hit_first_duty}

    return group


def create_duty_plan(users):
    """创建值班计划mock对象"""
    plan = mock.MagicMock()
    plan.user_group_id = 1
    plan.is_active_plan.return_value = True
    plan.users = users
    return plan


def test_hit_first_duty_true(mock_assignee):
    """测试hit_first_duty为True时匹配到第一个规则就返回"""
    group = create_test_group(hit_first_duty=True)

    # 创建两个值班计划
    duty_plan1 = create_duty_plan([{"type": "user", "id": "user1"}, {"type": "group", "id": "group1"}])

    duty_plan2 = create_duty_plan([{"type": "user", "id": "user2"}])

    group_duty_plans = {
        101: [duty_plan1],  # 第一个规则
        102: [duty_plan2],  # 第二个规则
    }

    # 执行测试
    mock_assignee.get_group_duty_users(group, group_duty_plans)

    # 验证结果 - 只处理了第一个规则
    assert sorted(mock_assignee.all_group_users[1]) == ["user1", "user2"]
    assert len(mock_assignee.all_group_users[1]) == 2


def test_hit_first_duty_false(mock_assignee):
    """测试hit_first_duty为False时处理所有匹配规则"""
    group = create_test_group(hit_first_duty=False)

    # 创建两个值班计划
    duty_plan1 = create_duty_plan([{"type": "user", "id": "user1"}, {"type": "group", "id": "group1"}])

    duty_plan2 = create_duty_plan([{"type": "user", "id": "user2"}, {"type": "group", "id": "group2"}])

    group_duty_plans = {
        101: [duty_plan1],  # 第一个规则
        102: [duty_plan2],  # 第二个规则
    }

    # 执行测试
    mock_assignee.get_group_duty_users(group, group_duty_plans)

    # 验证结果 - 处理了所有规则
    assert sorted(mock_assignee.all_group_users[1]) == ["user1", "user2", "user3"]
    assert len(mock_assignee.all_group_users[1]) == 3


def test_hit_first_duty_default_true(mock_assignee):
    """测试hit_first_duty未设置时默认为True"""
    group = create_test_group()  # 不设置hit_first_duty

    # 创建两个值班计划
    duty_plan1 = create_duty_plan([{"type": "user", "id": "user1"}, {"type": "group", "id": "group1"}])

    duty_plan2 = create_duty_plan([{"type": "user", "id": "user2"}])

    group_duty_plans = {
        101: [duty_plan1],  # 第一个规则
        102: [duty_plan2],  # 第二个规则
    }

    # 执行测试
    mock_assignee.get_group_duty_users(group, group_duty_plans)

    # 验证结果 - 只处理了第一个规则(默认行为)
    assert sorted(mock_assignee.all_group_users[1]) == ["user1", "user2"]
    assert len(mock_assignee.all_group_users[1]) == 2
