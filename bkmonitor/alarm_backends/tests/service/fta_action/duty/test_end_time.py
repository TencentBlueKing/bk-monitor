from datetime import datetime

import pytest

from bkmonitor.action.duty_manage import GroupDutyRuleManager
from bkmonitor.action.serializers import DutyRuleDetailSlz
from bkmonitor.models import DutyPlan, DutyRuleSnap

pytestmark = pytest.mark.django_db(databases=["default", "monitor_api"])


@pytest.fixture(autouse=True)
def get_all_user(mocker):
    """mock 获取所有用户。"""
    return mocker.patch("core.drf_resource.api.bk_login.get_all_user", return_value={"results": []})


@pytest.fixture
def today_as_2024_06_01(mocker):
    """mock 用户组和规则保存时，datetime_today 返回 2024-06-01 而不是今天。"""
    return mocker.patch("bkmonitor.utils.time_tools.datetime_today", return_value=datetime(2024, 6, 1))


@pytest.fixture
def default_user_group(create_duty_rule, create_user_group):
    """默认轮值用户组，自动分组，每天排班。"""
    duty_rule = create_duty_rule()
    return create_user_group(rule_ids=[duty_rule.id])


class TestSnap:
    @pytest.mark.parametrize(
        "rule_end_time, expected_snap_count",
        [
            pytest.param("2024-06-15 00:00:00", 0, id="complete"),
            pytest.param("2024-07-15 00:00:00", 1, id="incomplete"),
            pytest.param("", 1, id="incomplete_without_end"),
        ],
    )
    def test_snap_deletion_after_schedule_completion(
        self, today_as_2024_06_01, rule_end_time, create_duty_rule, create_user_group, expected_snap_count
    ):
        """使用不同的结束时间，测试排班一次后，是否删除了用于排班的快照。"""
        duty_rule = create_duty_rule(end_time=rule_end_time)
        # 用户组保存会调用一次快照和计划管理
        create_user_group(rule_ids=[duty_rule.id])

        assert DutyRuleSnap.objects.count() == expected_snap_count

    @pytest.mark.parametrize(
        "rule_end_time, new_rule_effective_time, expected_snap_count",
        [
            pytest.param("", "2024-06-15 00:00:00", 1, id="overlap_and_complete"),
            pytest.param("", "2024-07-15 00:00:00", 2, id="overlap_and_incomplete"),
            pytest.param("2024-07-10 00:00:00", "2024-07-15 00:00:00", 2, id="non_overlap"),
        ],
    )
    def test_snap_count_after_rule_modification(
        self,
        today_as_2024_06_01,
        create_duty_rule,
        create_user_group,
        rule_end_time,
        new_rule_effective_time,
        expected_snap_count,
    ):
        """使用不同的生效时间修改规则，测试旧快照是否被删除。"""
        duty_rule = create_duty_rule(end_time=rule_end_time)
        create_user_group(rule_ids=[duty_rule.id])

        rule_data = DutyRuleDetailSlz(duty_rule).data
        rule_data["effective_time"] = new_rule_effective_time
        serializer = DutyRuleDetailSlz(duty_rule, data=rule_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        assert DutyRuleSnap.objects.count() == expected_snap_count


class TestDutyRuleManager:
    @pytest.mark.parametrize(
        "rule_end_time, expected_end",
        [
            pytest.param("", 30, id="no_rule_end"),
            pytest.param("2024-06-30 10:00:00", 30, id="rule_end"),
        ],
    )
    def test_rule_end(self, today_as_2024_06_01, create_duty_rule, create_user_group, rule_end_time, expected_end):
        """测试有规则结束时间和没有的情况下，生成的计划数量。"""
        duty_rule = create_duty_rule(end_time=rule_end_time)
        create_user_group(rule_ids=[duty_rule.id])

        assert DutyPlan.objects.count() == expected_end

    def test_snap_end(self, today_as_2024_06_01, create_duty_rule, create_user_group):
        """测试修改规则后旧快照的结束时间。"""
        duty_rule = create_duty_rule()
        user_group = create_user_group(rule_ids=[duty_rule.id])

        rule_data = DutyRuleDetailSlz(duty_rule).data
        rule_data["effective_time"] = "2024-07-15 00:00:00"
        serializer = DutyRuleDetailSlz(duty_rule, data=rule_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        old_snap: DutyRuleSnap = DutyRuleSnap.objects.first()
        assert old_snap.end_time == rule_data["effective_time"]
        assert DutyPlan.objects.count() == 30

        m = GroupDutyRuleManager(user_group, duty_rules=[serializer.data])
        m.manage_duty_rule_snap(old_snap.next_plan_time)

        # 不包括 2024-07-15
        assert DutyPlan.objects.count() == 30 + 14
