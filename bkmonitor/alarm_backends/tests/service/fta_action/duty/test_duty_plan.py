import datetime

import mock
import pytest

from alarm_backends.service.fta_action.tasks import (
    generate_duty_plan_task,
    manage_group_duty_snap,
)
from bkmonitor.action.duty_manage import DutyRuleManager, GroupDutyRuleManager
from bkmonitor.action.serializers import DutyRuleDetailSlz, UserGroupDetailSlz
from bkmonitor.models import (
    DutyArrange,
    DutyPlan,
    DutyRule,
    DutyRuleRelation,
    DutyRuleSnap,
    UserGroup,
)
from bkmonitor.models.strategy import DutyPlanSendRecord
from bkmonitor.utils import time_tools
from constants.action import NoticeChannel, NoticeWay
from constants.common import DutyGroupType, RotationType

pytestmark = pytest.mark.django_db


@pytest.fixture()
def regular_duty_rule():
    """
    常规排班
    """
    yield {
        "name": "duty rule",
        "bk_biz_id": 2,
        "effective_time": "2023-07-25 11:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "regular",
        "duty_arranges": [],
    }


@pytest.fixture()
def rotation_duty_rule():
    """
    轮值排班
    """
    yield {
        "name": "rotation duty rule",
        "bk_biz_id": 2,
        "effective_time": "2023-07-25 11:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "rotation",
        "duty_arranges": [],
    }


@pytest.fixture()
def manager_delay_mock(mocker):
    return mocker.patch(
        "alarm_backends.service.fta_action.tasks.action_tasks.manage_group_duty_snap.delay", return_value=True
    )


@pytest.fixture()
def send_mail_mock(mocker):
    return mocker.patch("bkmonitor.utils.send.Sender.send_mail", return_value={})


@pytest.fixture()
def send_wxbot_mock(mocker):
    return mocker.patch(
        "bkmonitor.utils.send.Sender.send_wxwork_content", return_value={"errcode": 0, "message": "succeed"}
    )


@pytest.fixture()
def duty_rule_data():
    yield {
        "name": "duty rule111",
        "bk_biz_id": 2,
        "effective_time": "2023-11-01 00:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "handoff",
        "duty_arranges": [
            {
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--23:59"],
                        "period_settings": {"window_unit": "day", "duration": 2},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "admin", "type": "user"},
                        {"id": "admin1", "type": "user"},
                        {"id": "admin2", "type": "user"},
                        {"id": "admin3", "type": "user"},
                        {"id": "admin4", "type": "user"},
                        {"id": "admin5", "type": "user"},
                    ]
                ],
                "group_type": DutyGroupType.AUTO,
                "group_number": 2,
            }
        ],
    }


@pytest.fixture()
def multi_duty_rule_data():
    """
    多个duty_arrange的排班
    """
    duty_arranges = [
        {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                ],
            ],
            "group_type": "auto",
            "group_number": 1,
        },
        {  # 一个人做垫底
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                }
            ],
            "duty_users": [[{"id": "admin", "type": "user"}]],
        },
    ]
    yield {
        "name": "duty rule111",
        "bk_biz_id": 2,
        "effective_time": "2023-11-01 00:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "handoff",
        "duty_arranges": duty_arranges,
    }


@pytest.fixture()
def weekly_duty_rule_data():
    yield {
        "name": "weekly duty rule111",
        "bk_biz_id": 2,
        "effective_time": "2023-11-01 00:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "handoff",
        "duty_arranges": [
            {
                "duty_time": [
                    {
                        "work_type": "weekly",
                        "work_days": [4, 5, 1, 3],
                        "work_time_type": "time_range",
                        "work_time": ["10:00--23:00"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ],
    }


def get_user_group_data():
    return {
        "name": "蓝鲸业务的告警组-新的数据格式告警组",
        "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
        "bk_biz_id": 2,
        "need_duty": True,
        "mention_list": [{"type": "group", "id": "all"}],
        "channels": [NoticeChannel.USER, NoticeChannel.WX_BOT, NoticeChannel.BK_CHAT],
        "duty_rules": [],
        "alert_notice": [  # 告警通知配置
            {
                "time_range": "00:00:00--23:59:59",  # 生效时间段
                "notify_config": [  # 通知方式配置
                    {
                        "level": 3,  # 级别
                        "notice_ways": [
                            {"name": NoticeWay.WEIXIN},
                            {"name": NoticeWay.BK_CHAT, "receivers": ["mail|1", "mini|2"]},
                            {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                        ],
                    },
                    {"level": 2, "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}]},
                    {
                        "level": 1,
                        "notice_ways": [
                            {"name": NoticeWay.WEIXIN},
                            {"name": NoticeWay.MAIL},
                            {"name": NoticeWay.BK_CHAT, "receivers": ["mail|1", "mail|2"]},
                            {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                        ],
                    },
                ],
            }
        ],
        "action_notice": [  # 执行通知配置
            {
                "time_range": "00:00:00--23:59:59",  # 生效时间段
                "notify_config": [  # 通知方式
                    {
                        "phase": 3,
                        "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}],
                    },  # 执行阶段，3-执行前，2-成功时，1-失败时
                    {"phase": 2, "notice_ways": [{"name": NoticeWay.MAIL}, {"name": NoticeWay.VOICE}]},
                    {
                        "phase": 1,
                        "notice_ways": [
                            {"name": NoticeWay.WEIXIN},
                            {"name": NoticeWay.BK_CHAT, "receivers": ["1", "2"]},
                            {"name": NoticeWay.WX_BOT, "receivers": ["hihihihihh", "hihihiashihi"]},
                        ],
                    },
                ],
            }
        ],
    }


@pytest.fixture()
def user_group_data():
    yield get_user_group_data()


@pytest.fixture()
def db_setup():
    """
    轮值排班
    """
    DutyRule.objects.all().delete()
    DutyArrange.objects.all().delete()
    DutyRuleSnap.objects.all().delete()
    DutyPlan.objects.all().delete()
    UserGroup.objects.all().delete()
    DutyRuleRelation.objects.all().delete()
    DutyPlanSendRecord.objects.all().delete()


@pytest.fixture()
def duty_group():
    duty_rule_data = {
        "name": "duty rule",
        "bk_biz_id": 2,
        "effective_time": "2023-11-01 00:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "handoff",
        "duty_arranges": [
            {
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--23:59"],
                        "period_settings": {"window_unit": "day", "duration": 2},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "admin", "type": "user"},
                        {"id": "admin1", "type": "user"},
                        {"id": "admin2", "type": "user"},
                        {"id": "admin3", "type": "user"},
                        {"id": "admin4", "type": "user"},
                        {"id": "admin5", "type": "user"},
                    ]
                ],
                "group_type": DutyGroupType.AUTO,
                "group_number": 2,
            }
        ],
    }
    slz = DutyRuleDetailSlz(data=duty_rule_data)
    slz.is_valid(raise_exception=True)
    duty_rule = slz.save()

    user_group_data_new = get_user_group_data()
    user_group_data_new["duty_rules"] = [duty_rule.id]
    g_slz = UserGroupDetailSlz(data=user_group_data_new)
    g_slz.is_valid(raise_exception=True)
    yield g_slz.save()


@pytest.fixture()
def duty_group_data():
    duty_rule_data = {
        "name": "duty rule",
        "bk_biz_id": 2,
        "effective_time": "2024-02-22 00:00:00",
        "end_time": "",
        "labels": ["mysql", "redis", "business"],
        "enabled": True,
        "category": "handoff",
        "duty_arranges": [
            {
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--23:59"],
                    }
                ],
                "duty_users": [
                    [{"id": "admin", "type": "user"}],
                    [{"id": "admin1", "type": "user"}],
                    [{"id": "admin2", "type": "user"}],
                    [{"id": "admin3", "type": "user"}],
                ],
                "group_type": DutyGroupType.SPECIFIED,
                "group_number": 0,
            }
        ],
    }
    slz = DutyRuleDetailSlz(data=duty_rule_data)
    slz.is_valid(raise_exception=True)
    duty_rule = slz.save()

    user_group_data_new = get_user_group_data()
    user_group_data_new["duty_rules"] = [duty_rule.id]

    yield user_group_data_new


@pytest.fixture()
def duty_plans():
    yield [
        DutyPlan(
            **{
                "duty_rule_id": 123,
                "is_effective": 1,
                "start_time": "2023-11-16 00:00:00",
                "finished_time": "2023-11-30 00:00:00",
                "duty_time": [{"work_type": "daily", "work_time": "00:00--23:59"}],
                "order": 1,
                "users": [
                    {"id": "admin", "display_name": "admin", "logo": "", "type": "user"},
                    {"id": "operator", "display_name": "主机负责人", "logo": "", "type": "group"},
                ],
            }
        ),
        DutyPlan(
            **{
                "duty_rule_id": 123,
                "is_effective": 1,
                "start_time": "2023-11-15 00:00:00",
                "finished_time": "2023-11-30 00:00:00",
                "duty_time": [{"work_type": "daily", "work_time": "00:00--23:59"}],
                "order": 2,
                "users": [{"id": "lisa", "display_name": "xxxxx", "logo": "", "type": "user"}],
            }
        ),
    ]


class TestDutyPreview:
    def test_regular_daily_duty_rule(self, regular_duty_rule):
        regular_duty_rule["duty_arranges"].append(
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "display_name": "运维人员",
                            "logo": "",
                            "type": "group",
                            "members": [],
                        }
                    ]
                ],
                "backups": [],
            }
        )
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=2)
        duty_plan = m.get_duty_plan()
        print(duty_plan)
        assert len(duty_plan) == 1
        assert duty_plan[0]["work_times"] == [
            {'start_time': '2023-07-25 00:00', 'end_time': '2023-07-25 23:59'},
            {'start_time': '2023-07-26 00:00', 'end_time': '2023-07-26 23:59'},
        ]
        regular_duty_rule["enabled"] = False
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=2)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan) == 0

    def test_regular_daily_cross_day_duty_rule(self, regular_duty_rule):
        regular_duty_rule["duty_arranges"].append(
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["22:00--06:00"]}],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "display_name": "运维人员",
                            "logo": "",
                            "type": "group",
                            "members": [],
                        }
                    ]
                ],
                "backups": [],
            }
        )
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=2)
        duty_plan = m.get_duty_plan()
        print(duty_plan)
        assert len(duty_plan) == 1
        assert duty_plan[0]["work_times"] == [
            {'start_time': '2023-07-25 22:00', 'end_time': '2023-07-26 06:00'},
            {'start_time': '2023-07-26 22:00', 'end_time': '2023-07-27 06:00'},
        ]

    def test_regular_weekly_duty_rule(self, regular_duty_rule):
        regular_duty_rule["effective_time"] = "2023-07-23 11:00:00"
        regular_duty_rule["duty_arranges"].append(
            {
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["00:00--23:59"]}],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "display_name": "运维人员",
                            "logo": "",
                            "type": "group",
                            "members": [],
                        }
                    ]
                ],
                "backups": [],
            }
        )
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=7)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan[0]["work_times"]) == 5

    def test_regular_monthly_duty_rule(self, regular_duty_rule):
        regular_duty_rule["duty_arranges"].append(
            {
                "duty_time": [
                    {"work_type": RotationType.MONTHLY, "work_days": [25, 28], "work_time": ["00:00--23:59"]}
                ],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "type": "group",
                        }
                    ]
                ],
                "backups": [],
            }
        )
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=7)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan[0]["work_times"]) == 2

    def test_regular_date_range_duty_rule(self, regular_duty_rule):
        """
        测试一定日期范围的模式
        """
        regular_duty_rule["duty_arranges"].append(
            {
                "duty_time": [
                    {
                        "work_type": RotationType.DATE_RANGE,
                        "work_date_range": ["2023-07-26--2023-07-29"],
                        "work_time": ["00:00--23:59"],
                    }
                ],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_maintainer",
                            "type": "group",
                        }
                    ]
                ],
                "backups": [],
            }
        )
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=7)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan[0]["work_times"]) == 4

    def test_weekly_handoff(self, rotation_duty_rule):
        rotation_duty_rule["duty_arranges"] = [
            {
                "duty_time": [
                    {
                        "work_type": "weekly",
                        "work_days": [4, 5, 1, 3],
                        "work_time_type": "time_range",
                        "work_time": ["10:00--23:00"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ]

        rotation_duty_rule["effective_time"] = "2023-11-08 00:00:00"

        m = DutyRuleManager(duty_rule=rotation_duty_rule, days=21)
        duty_plan = m.get_duty_plan()
        print(duty_plan)

        assert len(duty_plan) == 4
        assert len(duty_plan[0]["work_times"]) == 1
        assert duty_plan[0]["user_index"] == 0
        assert len(duty_plan[1]["work_times"]) == 4
        assert duty_plan[1]["user_index"] == 1
        assert len(duty_plan[2]["work_times"]) == 4
        assert duty_plan[2]["user_index"] == 2
        assert duty_plan[3]["user_index"] == 0

    def test_weekly_handoff_with_end(self, rotation_duty_rule):
        rotation_duty_rule["duty_arranges"] = [
            {
                "duty_time": [
                    {
                        "work_type": "weekly",
                        "work_days": [1, 2, 3, 4, 5],
                        "work_time_type": "time_range",
                        "work_time": ["10:00--23:00"],
                    },
                    {
                        "work_type": "weekly",
                        "work_days": [1, 2, 3, 4, 5],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--10:00"],
                    },
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ]

        rotation_duty_rule["effective_time"] = "2023-12-11 00:00:00"

        # 有一个结束时间，所以15号应该是没有数据的
        rotation_duty_rule["end_time"] = "2023-12-15 00:00:00"

        m = DutyRuleManager(duty_rule=rotation_duty_rule, days=21)
        duty_plan = m.get_duty_plan()
        print(duty_plan)

        assert len(duty_plan) == 2
        assert duty_plan[0]["user_index"] == 0
        assert len(duty_plan[0]["work_times"]) == 4

        assert duty_plan[1]["user_index"] == 1
        assert len(duty_plan[1]["work_times"]) == 4

    def test_weekly_datetime_range_handoff(self, rotation_duty_rule):
        """
        周一 至 可以工作周五
        """
        rotation_duty_rule["duty_arranges"] = [
            {
                "duty_time": [
                    {
                        "work_type": "weekly",
                        "work_days": [],
                        "work_time_type": "datetime_range",
                        "work_time": ["04 10:00--03 08:00"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ]

        rotation_duty_rule["effective_time"] = "2023-11-08 00:00:00"

        m = DutyRuleManager(duty_rule=rotation_duty_rule, days=21)
        duty_plan = m.get_duty_plan()
        print(duty_plan)

        assert len(duty_plan) == 4
        assert len(duty_plan[0]["work_times"]) == 1
        assert duty_plan[0]["work_times"][-1]["start_time"] == "2023-11-08 00:00"
        assert duty_plan[0]["work_times"][-1]["end_time"] == "2023-11-08 08:00"
        assert duty_plan[0]["user_index"] == 0
        assert len(duty_plan[1]["work_times"]) == 7
        assert duty_plan[1]["work_times"][-1]["start_time"] == "2023-11-15 00:00"
        assert duty_plan[1]["work_times"][-1]["end_time"] == "2023-11-15 08:00"
        assert duty_plan[1]["user_index"] == 1
        assert len(duty_plan[2]["work_times"]) == 7
        assert duty_plan[2]["user_index"] == 2
        assert duty_plan[3]["user_index"] == 0

    def test_weekly_datetime_range_handoff_on_eight(self, rotation_duty_rule):
        """
        周一 至 可以工作周五
        """
        rotation_duty_rule["duty_arranges"] = [
            {
                "duty_time": [
                    {
                        "work_type": "weekly",
                        "work_days": [],
                        "work_time_type": "datetime_range",
                        "work_time": ["01 08:00--01 08:00"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ]

        rotation_duty_rule["effective_time"] = "2023-11-13 08:00:00"

        m = DutyRuleManager(duty_rule=rotation_duty_rule, days=21)
        duty_plan = m.get_duty_plan()
        print(duty_plan)

        assert len(duty_plan) == 3
        assert len(duty_plan[0]["work_times"]) == 7
        # 每个周期的最后一天为周一的8点
        assert duty_plan[0]["work_times"][-1]["start_time"] == "2023-11-19 00:00"
        assert duty_plan[0]["work_times"][-1]["end_time"] == "2023-11-20 08:00"
        assert duty_plan[0]["user_index"] == 0
        assert len(duty_plan[1]["work_times"]) == 7
        assert duty_plan[1]["user_index"] == 1
        assert len(duty_plan[2]["work_times"]) == 7
        assert duty_plan[2]["user_index"] == 2

    def test_monthly_datetime_range_handoff(self, rotation_duty_rule):
        """
        1号至15号一班
        16号至31号一班
        3个班轮流来
        """
        rotation_duty_rule["duty_arranges"] = [
            {
                "duty_time": [
                    {
                        "work_type": "monthly",
                        "work_days": [],
                        "work_time_type": "datetime_range",
                        "work_time": ["01 00:00--15 23:59"],
                        "period_settings": {},
                    },
                    {
                        "work_type": "monthly",
                        "work_days": [],
                        "work_time_type": "datetime_range",
                        "work_time": ["16 00:00--31 23:59"],
                        "period_settings": {},
                    },
                ],
                "duty_users": [
                    [
                        {"id": "Alan", "type": "user"},
                        {"id": "Frances", "type": "user"},
                        {"id": "Lucile", "type": "user"},
                    ],
                    [{"id": "Brian", "type": "user"}, {"id": "Danny", "type": "user"}, {"id": "Alice", "type": "user"}],
                    [
                        {"id": "Brian1", "type": "user"},
                        {"id": "Danny1", "type": "user"},
                        {"id": "Alice1", "type": "user"},
                    ],
                ],
                "group_type": "specified",
                "group_number": 0,
            }
        ]

        rotation_duty_rule["effective_time"] = "2023-12-01 00:00:00"

        m = DutyRuleManager(duty_rule=rotation_duty_rule, days=60)
        duty_plan = m.get_duty_plan()
        print(duty_plan)

        assert len(duty_plan) == 4
        assert len(duty_plan[0]["work_times"]) == 15
        assert duty_plan[0]["user_index"] == 0
        assert len(duty_plan[1]["work_times"]) == 16
        assert duty_plan[1]["user_index"] == 1
        assert len(duty_plan[2]["work_times"]) == 15
        assert duty_plan[2]["user_index"] == 2
        assert duty_plan[3]["user_index"] == 0

    def test_multi_regular_weekly_duty_rule(self, regular_duty_rule):
        regular_duty_rule["effective_time"] = "2023-07-23 11:00:00"
        regular_duty_rule["duty_arranges"] = [
            {
                # 周末工作人员
                "duty_time": [{"work_type": RotationType.WEEKEND, "work_days": [6, 7], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
            },
            {
                # 工作日工作人员
                "duty_time": [
                    {"work_type": RotationType.WORK_DAY, "work_days": [1, 2, 3, 4, 5], "work_time": ["00:00--23:59"]}
                ],
                "duty_users": [
                    [
                        {
                            "id": "bk_biz_developer",
                            "type": "group",
                        }
                    ]
                ],
            },
        ]
        m = DutyRuleManager(duty_rule=regular_duty_rule, days=7)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan) == 2
        assert len(duty_plan[0]["work_times"]) == 2
        assert len(duty_plan[1]["work_times"]) == 5

    def test_custom_even_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {"window_unit": "day", "duration": 2},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                    {"id": "admin5", "type": "user"},
                ]
            ],
            "group_type": "auto",
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=6)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan) == 3

    def test_custom_odd_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {"window_unit": "day", "duration": 2},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                ]
            ],
            "group_type": "auto",
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=6)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan) == 3
        assert duty_plan[-1]["users"] == [{"id": "admin4", "type": "user"}, {"id": "admin", "type": "user"}]

    def test_auto_period_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {"window_unit": "day", "duration": 2},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                ],
                [{"id": "admin3", "type": "user"}, {"id": "admin4", "type": "user"}, {"id": "admin5", "type": "user"}],
            ],
            "group_type": "",
            "group_number": 0,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=4)
        duty_plan = m.get_duty_plan()
        assert len(duty_plan) == 2
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
            {"id": "admin2", "type": "user"},
        ]

    def test_odd_auto_period_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {"window_unit": "day", "duration": 2},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                ],
                [{"id": "admin3", "type": "user"}, {"id": "admin4", "type": "user"}, {"id": "admin5", "type": "user"}],
            ],
            "group_type": "",
            "group_number": 0,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=5)
        duty_plan = m.get_duty_plan()
        # 如果是5天计划，实际上需要设置轮值到交接时间点，所以会生成6天
        assert len(duty_plan) == 3
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
            {"id": "admin2", "type": "user"},
        ]

        # 最后一个周期的轮班时间应该也是2天
        assert len(duty_plan[-1]["work_times"]) == 2

        # 下一个周期, 需要从开始时间生成5天，实际上上一次第一天已经安排，应该从31号开始
        m = DutyRuleManager(rotation_duty_rule, begin_time="2023-07-30 00:00:00", days=5)

        duty_plan = m.get_duty_plan()
        print(duty_plan)
        assert len(duty_plan) == 2
        assert duty_plan[-1]["work_times"] == [
            {'start_time': '2023-08-02 00:00', 'end_time': '2023-08-02 23:59'},
            {'start_time': '2023-08-03 00:00', 'end_time': '2023-08-03 23:59'},
        ]

    def test_multi_rotation_duty_rule(self, rotation_duty_rule):
        """
        主备份人模式
        """
        duty_arranges = [
            {
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--23:59"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [
                    [
                        {"id": "admin1", "type": "user"},
                        {"id": "admin2", "type": "user"},
                        {"id": "admin3", "type": "user"},
                        {"id": "admin4", "type": "user"},
                    ],
                ],
                "group_type": "auto",
                "group_number": 1,
            },
            {  # 一个人做垫底
                "duty_time": [
                    {
                        "work_type": "daily",
                        "work_days": [],
                        "work_time_type": "time_range",
                        "work_time": ["00:00--23:59"],
                        "period_settings": {},
                    }
                ],
                "duty_users": [[{"id": "admin", "type": "user"}]],
            },
        ]
        rotation_duty_rule["duty_arranges"] = duty_arranges
        m = DutyRuleManager(rotation_duty_rule, days=4)
        duty_plan = m.get_duty_plan()
        # 如果是5天计划，实际上需要设置轮值到交接时间点，所以会生成6天
        print(duty_plan)
        assert len(duty_plan) == 8
        assert duty_plan[0]["users"] == [{"id": "admin1", "type": "user"}]

        assert duty_plan[-1]["users"] == [{"id": "admin", "type": "user"}]
        assert duty_plan[-1]["work_times"] == [
            {'start_time': '2023-07-28 00:00', 'end_time': '2023-07-28 23:59'},
        ]

    def test_even_auto_group_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、按天来轮班， 每天一次
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                    {"id": "admin5", "type": "user"},
                ]
            ],
            "group_type": DutyGroupType.AUTO,
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=4)
        duty_plan = m.get_duty_plan()
        # 4天排班，应该有4个班次
        assert len(duty_plan) == 4
        # 按照轮值规则来，第一个班次应该是前两个
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]

        # 最后一个班次应该是前两个用户
        assert duty_plan[-1]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]

    def test_odd_auto_group_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义测试场景
        1、按天来轮班， 每天一次
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": "daily",
                    "work_days": [],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                }
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                ]
            ],
            "group_type": DutyGroupType.AUTO,
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        m = DutyRuleManager(rotation_duty_rule, days=4)
        duty_plan = m.get_duty_plan()
        # 4天排班，应该有4个班次
        assert len(duty_plan) == 4
        # 按照轮值规则来，第一个班次应该是前两个
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]
        # 最后一个班次应该是前两个用户
        assert duty_plan[-1]["users"] == [
            {"id": "admin1", "type": "user"},
            {"id": "admin2", "type": "user"},
        ]

    def test_odd_auto_group_weekly_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义分人，班次按周轮转确定的测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": RotationType.WEEKLY,
                    "work_days": [1, 2, 3, 4, 5],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                },
                {
                    "work_type": RotationType.WEEKLY,
                    "work_days": [6, 7],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                },
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                ]
            ],
            "group_type": DutyGroupType.AUTO,
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        rotation_duty_rule["effective_time"] = "2023-10-23 00:00:00"

        m = DutyRuleManager(rotation_duty_rule, days=14)
        duty_plan = m.get_duty_plan()
        print(duty_plan)
        # 4天排班，应该有4个班次
        assert len(duty_plan) == 4
        # 按照轮值规则来，第一个班次应该是前两个
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]
        # 单数个，最后一个班次应该第二位和第三位
        # [1,2], [3,4], [5,1], [2,3]
        assert duty_plan[-1]["users"] == [
            {"id": "admin1", "type": "user"},
            {"id": "admin2", "type": "user"},
        ]

    def test_even_auto_group_weekly_rotation_duty_rule(self, rotation_duty_rule):
        """
        自定义分人，班次按周轮转确定的测试场景
        1、每隔两天进行一次交接
        2、每两个人分成一组
        """
        duty_arrange = {
            "duty_time": [
                {
                    "work_type": RotationType.WEEKLY,
                    "work_days": [1, 2, 3, 4, 5],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--08:00"],
                    "period_settings": {},
                },
                {
                    "work_type": RotationType.WEEKLY,
                    "work_days": [6, 7],
                    "work_time_type": "time_range",
                    "work_time": ["00:00--23:59"],
                    "period_settings": {},
                },
            ],
            "duty_users": [
                [
                    {"id": "admin", "type": "user"},
                    {"id": "admin1", "type": "user"},
                    {"id": "admin2", "type": "user"},
                    {"id": "admin3", "type": "user"},
                    {"id": "admin4", "type": "user"},
                    {"id": "admin5", "type": "user"},
                ]
            ],
            "group_type": DutyGroupType.AUTO,
            "group_number": 2,
        }
        rotation_duty_rule["duty_arranges"] = [duty_arrange]

        rotation_duty_rule["effective_time"] = "2023-10-23 00:00:00"

        m = DutyRuleManager(rotation_duty_rule, days=14)
        duty_plan = m.get_duty_plan()
        print(duty_plan)
        # 4天排班，应该有4个班次
        assert len(duty_plan) == 4
        # 按照轮值规则来，第一个班次应该是前两个
        assert duty_plan[0]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]
        # 单数个，最后一个班次应该第二位和第三位
        # [1,2], [3,4], [5,1], [2,3]
        assert duty_plan[-1]["users"] == [
            {"id": "admin", "type": "user"},
            {"id": "admin1", "type": "user"},
        ]


class TestDutyPlan:
    @pytest.fixture
    def datetime_today(self, mocker):
        """mock 用户组和规则保存时，datetime_today 返回 2024-06-01 而不是今天。"""
        return mocker.patch("bkmonitor.utils.time_tools.datetime_today", return_value=datetime.datetime(2024, 6, 1))

    def test_manage_duty_rule_snap(self, db_setup, duty_group):
        assert DutyRuleSnap.objects.filter(user_group_id=duty_group.id).count() == 1
        assert DutyPlan.objects.filter(user_group_id=duty_group.id, is_effective=1).count() == 15

        snap = DutyRuleSnap.objects.get(user_group_id=duty_group.id)
        assert snap.next_plan_time == (datetime.datetime.today() + datetime.timedelta(days=30)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def test_nochange_duty_rule(self, datetime_today, db_setup, duty_group, duty_rule_data):
        # 重新修改
        origin_rule = DutyRule.objects.get(id=duty_group.duty_rules[0])
        duty_rule_data["id"] = duty_group.duty_rules[0]
        new_slz = DutyRuleDetailSlz(instance=origin_rule, data=duty_rule_data)
        new_slz.is_valid(raise_exception=True)
        new_slz.save()
        assert new_slz.validated_data["hash"] == origin_rule.hash

        new_data = DutyRuleDetailSlz(new_slz.instance).data
        m = GroupDutyRuleManager(user_group=duty_group, duty_rules=[new_data])
        m.manage_duty_rule_snap(duty_rule_data["effective_time"])

        # 没有发生变化，应该是不做调整
        assert DutyRuleSnap.objects.filter(user_group_id=duty_group.id).count() == 1
        assert DutyPlan.objects.filter(user_group_id=duty_group.id, is_effective=1).count() == 15

        snap = DutyRuleSnap.objects.get(user_group_id=duty_group.id)
        assert snap.next_plan_time == (datetime.datetime(2024, 6, 1) + datetime.timedelta(days=30)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def test_change_duty_rule(self, db_setup, duty_group, duty_rule_data):
        # 重新修改
        origin_rule = DutyRule.objects.get(id=duty_group.duty_rules[0])
        duty_rule_data["id"] = duty_group.duty_rules[0]
        #  3天后才生效
        duty_rule_data["effective_time"] = (datetime.datetime.today() + datetime.timedelta(days=3)).strftime(
            "%Y-%m-%d 12:00:00"
        )
        new_slz = DutyRuleDetailSlz(instance=origin_rule, data=duty_rule_data)
        new_slz.is_valid(raise_exception=True)
        # hash发生了变化
        assert new_slz.validated_data["hash"] != origin_rule.hash
        new_slz.save()

        new_slz.validated_data["id"] = origin_rule.id
        new_data = DutyRuleDetailSlz(new_slz.instance).data
        m = GroupDutyRuleManager(user_group=duty_group, duty_rules=[new_data])
        m.manage_duty_rule_snap(duty_rule_data["effective_time"])

        assert DutyRuleSnap.objects.filter(user_group_id=duty_group.id).count() == 1
        # 三天后产生一波新的，之前配置三天后开始的失效
        assert DutyPlan.objects.filter(user_group_id=duty_group.id, is_effective=1).count() == 17

        # 第一次安排的有效期限提前到下一次生效之前
        assert (
            DutyPlan.objects.filter(
                user_group_id=duty_group.id, finished_time__lte=duty_rule_data["effective_time"], is_effective=1
            ).count()
            == 2
        )

        # 生效那天，start_time 不能小于 effective_time
        plan3 = DutyPlan.objects.filter(user_group_id=duty_group.id, is_effective=1)[2]
        assert plan3.start_time == duty_rule_data["effective_time"]
        assert duty_group.duty_plans[2].start_time == plan3.start_time[:-3]

    def test_disable_duty_rule(self, db_setup, duty_group, duty_rule_data):
        # 重新修改
        origin_rule = DutyRule.objects.get(id=duty_group.duty_rules[0])
        duty_rule_data["id"] = duty_group.duty_rules[0]
        duty_rule_data["enabled"] = False
        new_slz = DutyRuleDetailSlz(instance=origin_rule, data=duty_rule_data)
        new_slz.is_valid(raise_exception=True)
        new_slz.save()
        # 是否开启不影响hash
        assert new_slz.validated_data["hash"] == origin_rule.hash

        m = GroupDutyRuleManager(user_group=duty_group, duty_rules=[duty_rule_data])
        m.manage_duty_rule_snap(origin_rule.effective_time)
        # 被禁用了之后，原有的快照直接被禁用掉
        assert DutyRuleSnap.objects.filter(user_group_id=duty_group.id).count() == 0

        # 原有的排班计划被设置为非激活状态
        assert DutyPlan.objects.filter(user_group_id=duty_group.id, is_effective=0).count() == 15

    def test_generate_duty_plan_task(
        self, db_setup, duty_rule_data, user_group_data, manager_delay_mock, weekly_duty_rule_data
    ):
        """
        测试一个没有进行过排班的分组
        """
        # 方案 1 两天一班，一共30班
        dslz = DutyRuleDetailSlz(data=duty_rule_data)
        dslz.is_valid(raise_exception=True)
        dslz.save()

        user_group_data["duty_rules"] = [dslz.instance.id]
        user_group = UserGroup.objects.create(**user_group_data)
        DutyRuleRelation.objects.create(duty_rule_id=dslz.instance.id, user_group_id=user_group.id)

        managers = generate_duty_plan_task()

        # 启动了一次管理任务
        assert manager_delay_mock.call_count == 1
        assert len(managers) == 1
        assert managers[0].duty_rules

        # 进行一次任务的执行
        manage_group_duty_snap(managers[0])

        assert DutyRuleSnap.objects.filter(user_group_id=user_group.id).count() == 1
        assert DutyPlan.objects.filter(user_group_id=user_group.id, is_effective=1).count() == 15

        snap = DutyRuleSnap.objects.get(user_group_id=user_group.id)
        assert snap.next_plan_time[:10] == (datetime.datetime.today() + datetime.timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )

        week_slz = DutyRuleDetailSlz(data=weekly_duty_rule_data)
        week_slz.is_valid(raise_exception=True)
        week_slz.save()

        user_group.duty_rules.append(week_slz.instance.id)
        DutyRuleRelation.objects.create(duty_rule_id=week_slz.instance.id, user_group_id=user_group.id)
        user_group.save()

        managers = generate_duty_plan_task()

        # 此时再进行一次任务的执行
        manage_group_duty_snap(managers[0])
        assert DutyRuleSnap.objects.filter(user_group_id=user_group.id).count() == 2
        assert DutyPlan.objects.filter(user_group_id=user_group.id).count() > 15

    def test_generate_multi_duty_plan_task(
        self, db_setup, multi_duty_rule_data, user_group_data, manager_delay_mock, weekly_duty_rule_data
    ):
        """
        测试一个没有进行过排班的分组
        """
        # 方案 第一组，四个人值班每人一天轮流来
        # 第二组，admin作为语音备份人员
        dslz = DutyRuleDetailSlz(data=multi_duty_rule_data)
        dslz.is_valid(raise_exception=True)
        dslz.save()

        user_group_data["duty_rules"] = [dslz.instance.id]
        user_group = UserGroup.objects.create(**user_group_data)
        DutyRuleRelation.objects.create(duty_rule_id=dslz.instance.id, user_group_id=user_group.id)

        managers = generate_duty_plan_task()

        # 启动了一次管理任务
        assert manager_delay_mock.call_count == 1
        assert len(managers) == 1
        assert managers[0].duty_rules

        # 进行一次任务的执行
        manage_group_duty_snap(managers[0])

        assert DutyRuleSnap.objects.filter(user_group_id=user_group.id).count() == 1

        # 一天一天来，最近30天，相当于两个排班组
        assert DutyPlan.objects.filter(user_group_id=user_group.id, is_effective=1).count() == 60

        snap = DutyRuleSnap.objects.get(user_group_id=user_group.id)
        assert snap.next_plan_time[:10] == (datetime.datetime.today() + datetime.timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )

    def test_create_duty_rule(self, db_setup, duty_group, duty_rule_data):
        """测试多次创建规则"""
        assert DutyArrange.objects.all().count() == 1
        dslz = DutyRuleDetailSlz(data=duty_rule_data)
        dslz.is_valid(raise_exception=True)
        dslz.save()

        assert DutyArrange.objects.all().count() == 2

    def test_duty_plan_notice(self, db_setup, duty_group, duty_plans, send_wxbot_mock):
        plan_notice = {
            "enabled": True,
            "chat_ids": ["12323321123123123123213211111111"],
            "days": 7,
            "type": "weekly",
            "date": 1,
            "time": "00:00",
        }
        DutyPlan.objects.all().delete()
        for d in duty_plans:
            d.user_group_id = duty_group.id
            d.finished_time = "2023-12-13 00:00:00"

        DutyPlan.objects.bulk_create(duty_plans)
        manager = GroupDutyRuleManager(duty_group, {})
        task_time = time_tools.str2datetime("2023-11-13 00:00:00")
        manager.send_plan_notice(plan_notice, task_time)
        # 没有发送过，需要发送一把
        assert send_wxbot_mock.call_count == 1
        # 会产生一条通知记录
        assert DutyPlanSendRecord.objects.get(user_group_id=duty_group.id)

    def test_expired_plan_notice(self, db_setup, duty_group, duty_plans, send_wxbot_mock):
        plan_notice = {
            "enabled": True,
            "chat_ids": ["12323321123123123123213211111111"],
            "days": 7,
            "type": "weekly",
            "date": 1,
            "time": "00:00",
        }
        DutyPlan.objects.all().delete()
        for d in duty_plans:
            d.user_group_id = duty_group.id
            d.finished_time = "2023-12-13 00:00:00"

        DutyPlan.objects.bulk_create(duty_plans)
        manager = GroupDutyRuleManager(duty_group, {})
        task_time = time_tools.str2datetime("2023-11-13 10:00:00")
        manager.send_plan_notice(plan_notice, task_time)
        # 没有发送过，需要发送一把
        assert send_wxbot_mock.call_count == 1
        # 会产生一条通知记录
        assert DutyPlanSendRecord.objects.get(user_group_id=duty_group.id)

    def test_duty_personal_notice(self, db_setup, duty_group, duty_plans, send_mail_mock):
        DutyPlan.objects.all().delete()
        for d in duty_plans:
            d.user_group_id = duty_group.id

        DutyPlan.objects.bulk_create(duty_plans)

        # 发最近3天内的个人通知
        personal_notice = {"enabled": True, "hours_ago": 3 * 24, "duty_rules": []}
        manager = GroupDutyRuleManager(duty_group, {})
        manager.send_personal_notice(personal_notice, time_tools.str2datetime("2023-11-13 00:00:00"))
        # 有两个有效的通知用户，主备负责人无法获取，所以不会发给任何人
        # 两个用户发送通知内容不一样，所以需要发送2次
        assert send_mail_mock.call_count == 2

    def test_duty_personal_notice_last_send_time(self, db_setup, duty_group, duty_plans, send_mail_mock):
        DutyPlan.objects.all().delete()
        for d in duty_plans:
            d.user_group_id = duty_group.id
            # 随便记录一个发送时间
            d.last_send_time = 123455677

        DutyPlan.objects.bulk_create(duty_plans)

        # 发最近3天内的个人通知
        personal_notice = {"enabled": True, "hours_ago": 3 * 24, "duty_rules": []}
        manager = GroupDutyRuleManager(duty_group, {})
        manager.send_personal_notice(personal_notice, time_tools.str2datetime("2023-11-13 00:00:00"))
        # 第二个排班计划，已经发送过值班通知，当前忽略
        # 第一个排班计划是三天以后生效，可以忽略最后发送值班通知
        assert send_mail_mock.call_count == 1


class TestEffectiveTime:
    @pytest.mark.parametrize(
        "create_time, duty_user",
        [
            pytest.param("2024-02-22 00:00:00", "admin", id="2024-02-22 00:00:00 -> admin"),
            pytest.param("2024-02-23 00:00:00", "admin1", id="2024-02-23 00:00:00 -> admin1"),
            pytest.param("2024-06-23 00:00:00", "admin2", id="2024-06-23 00:00:00 -> admin2"),
            pytest.param("2026-07-12 00:00:00", "admin3", id="2026-07-12 00:00:00 -> admin3"),
        ],
    )
    def test_user_group_save(self, db_setup, duty_group_data, create_time, duty_user):
        create_time = time_tools.str2datetime(create_time)
        with mock.patch("bkmonitor.action.serializers.strategy.time_tools.datetime_today", return_value=create_time):
            g_slz = UserGroupDetailSlz(data=duty_group_data)
            g_slz.is_valid(raise_exception=True)
            g_slz.save()

            # 排过一次班，下一次排班时间会大于 create_time
            assert DutyRuleSnap.objects.filter(next_plan_time__gt=create_time).exists()

            first_duty_plan = (
                DutyPlan.objects.filter(user_group_id=g_slz.instance.id, is_effective=1)
                .order_by("start_time")
                .values()[0]
            )
            assert first_duty_plan["users"][0]["id"] == duty_user
