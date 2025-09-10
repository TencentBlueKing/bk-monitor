# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
from datetime import timedelta, timezone

import mock
from django.test import TestCase

from bkmonitor.action.serializers.strategy import *  # noqa
from bkmonitor.models import DutyArrange, UserGroup
from kernel_api.views.v4 import SaveDutyRuleResource
from monitor_web.user_group.resources import (
    PreviewDutyRulePlanResource,
    PreviewUserGroupPlanResource,
)

DUTY_RULE_DATA = {
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
                {"work_type": "daily", "work_days": [], "work_time_type": "time_range", "work_time": ["00:00--23:59"]}
            ],
            "duty_users": [
                [{"id": "admin", "display_name": "admin", "type": "user"}],
                [{"id": "admin1", "display_name": "admin1", "type": "user"}],
                [{"id": "admin2", "display_name": "admin2", "type": "user"}],
                [{"id": "admin3", "display_name": "admin3", "type": "user"}],
            ],
            "group_type": DutyGroupType.SPECIFIED,
            "group_number": 0,
        }
    ],
}

USER_GROUP_DATA = {
    "name": "轮值用户组测试",
    "desc": "按照轮值的格式",
    "duty_rules": [],
    "alert_notice": [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {"level": 3, "type": ["weixin"]},
                {"level": 2, "type": ["weixin"]},
                {"level": 1, "type": ["weixin"]},
            ],
        }
    ],
    "action_notice": [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {"level": 3, "type": ["weixin"], "phase": 3},
                {"level": 2, "type": ["weixin"], "phase": 2},
                {"level": 1, "type": ["weixin"], "phase": 1},
            ],
        }
    ],
    "need_duty": True,
    "bk_biz_id": 2,
}


class BaseTestCase(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        UserGroup.objects.all().delete()
        DutyRule.objects.all().delete()
        DutyRuleRelation.objects.all().delete()
        DutyArrange.objects.all().delete()

        self.user_mock = mock.patch(
            "core.drf_resource.api.bk_login.get_all_user",
            return_value={"results": [{"username": "admin", "display_name": "admin"}]},
        )

        self.users_representation_mock = mock.patch(
            "bkmonitor.action.serializers.strategy.DutyBaseInfoSlz.users_representation",
            return_value=[
                {
                    "id": "admin",
                    "display_name": "admin",
                    "type": "user",
                }
            ],
        )
        self.user_mock.start()
        self.users_representation_mock.start()

    def tearDown(self):
        UserGroup.objects.all().delete()
        DutyRule.objects.all().delete()
        DutyRuleRelation.objects.all().delete()
        DutyArrange.objects.all().delete()
        self.user_mock.stop()
        self.users_representation_mock.stop()

    def create_duty_user_group(self):
        duty_arranges = [
            {
                "need_rotation": True,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [
                    {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": ["00:00--23:59"]}
                ],
                "backups": [
                    {
                        "users": [
                            {
                                "display_name": "运维人员",
                                "logo": "",
                                "id": "bk_biz_maintainer",
                                "type": "group",
                                "members": [{"id": "admin", "display_name": "admin"}],
                            }
                        ],
                        "begin_time": "2022-03-11 00:00:00",
                        "end_time": "2022-03-13 00:00:00",
                        "duty_time": {
                            "work_type": "weekly",
                            "work_days": [1, 2, 3, 4, 5],
                            "work_time": ["08:00--18:00"],
                        },
                        "exclude_settings": [{"date": "2021-11-09", "time": "10:00--11:00"}],
                    }
                ],
                "duty_users": [
                    [
                        {"display_name": "admin", "logo": "", "id": "admin", "type": "user"},
                        {
                            "display_name": "运维人员",
                            "logo": "",
                            "id": "bk_biz_maintainer",
                            "type": "group",
                            "members": [{"id": "admin", "display_name": "admin"}],
                        },
                    ]
                ],
            },
            {
                "need_rotation": False,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["08:00--18:00"]}],
                "backups": [
                    {
                        "users": [
                            {
                                "display_name": "运维人员",
                                "logo": "",
                                "id": "bk_biz_maintainer",
                                "type": "group",
                                "members": [{"id": "admin", "display_name": "admin"}],
                            }
                        ],
                        "begin_time": "2022-03-11 00:00:00",
                        "end_time": "2022-03-13 00:00:00",
                        "duty_time": {
                            "work_type": "weekly",
                            "work_days": [1, 2, 3, 4, 5],
                            "work_time": ["08:00--18:00"],
                        },
                        "exclude_settings": [{"date": "2021-11-09", "time": "10:00--11:00"}],
                    }
                ],
                "duty_users": [
                    [
                        {
                            "display_name": "运维人员",
                            "logo": "",
                            "id": "bk_biz_maintainer",
                            "type": "group",
                            "members": [{"id": "admin", "display_name": "admin"}],
                        },
                        {"display_name": "admin", "logo": "", "id": "admin", "type": "user"},
                        {
                            "display_name": "开发人员",
                            "logo": "",
                            "id": "bk_biz_developer",
                            "type": "group",
                            "members": [{"id": "admin", "display_name": "admin"}],
                        },
                    ]
                ],
            },
        ]

        user_group_data = copy.deepcopy(USER_GROUP_DATA)
        user_group_data.pop("duty_rules")
        user_group_data["duty_arranges"] = duty_arranges
        user_group_data["need_duty"] = False

        slz = UserGroupDetailSlz(data=user_group_data)
        slz.is_valid(raise_exception=True)
        slz.save()

    def create_regular_duty_rule(self, name):
        duty_rule = {
            "name": name,
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "regular",
            "duty_arranges": [
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
            ],
        }
        slz = DutyRuleDetailSlz(data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        return slz.save()

    def get_handoff_duty_arrange(self):
        return {
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
            "backups": [],
        }

    def get_handoff_duty_rule(self, name):
        """
        创建需要自定义交接轮班的
        """
        duty_rule = {
            "name": name,
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "handoff",
            "duty_arranges": [self.get_handoff_duty_arrange()],
        }
        return duty_rule


class TestDutyArrangeSlzResource(BaseTestCase):
    def test_rotation_handoff_time(self):
        def validate(value):
            slz = HandOffSettingsSerializer(data=value)
            return slz.is_valid(raise_exception=True)

        value = {"rotation_type": "weekly", "date": 1, "time": "08:00"}
        self.assertTrue(validate(value))

        value["date"] = "8"
        with self.assertRaises(ValidationError):
            validate(value)

        value["date"] = 2
        value["time"] = "24:67"
        with self.assertRaises(ValidationError):
            validate(value)

        monthly_value = {"rotation_type": "monthly", "date": 1, "time": "08:00"}
        self.assertTrue(validate(monthly_value))

        monthly_value["date"] = 32
        with self.assertRaises(ValidationError):
            validate(value)

        daily_value = {"rotation_type": "daily", "date": 1, "time": "08:00"}
        self.assertTrue(validate(daily_value))

    def test_duty_time(self):
        def validate(value):
            slz = DutyTimeSerializer(data=value)
            return slz.is_valid(raise_exception=True)

        value = {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": ["08:00--18:00"]}
        self.assertTrue(validate(value))

        value["work_days"] = [1, 2, 3, 4, 5, 9]
        with self.assertRaises(ValidationError):
            validate(value)

        value["work_days"] = 2
        value["work_time"] = ["00:00--24:67"]
        with self.assertRaises(ValidationError):
            validate(value)

        value["work_time"] = ["00:00"]
        with self.assertRaises(ValidationError):
            validate(value)

        monthly_value = {"work_type": "monthly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": ["08:00--18:00"]}
        self.assertTrue(validate(monthly_value))

        monthly_value["work_days"] = [32, 45, 12]
        with self.assertRaises(ValidationError):
            validate(value)

        daily_value = {"work_type": "monthly", "work_time": ["08:00--18:00"]}
        self.assertTrue(validate(daily_value))

    def test_exclude_settings(self):
        def validate(value):
            slz = ExcludeSettingsSerializer(data=value)
            return slz.is_valid(raise_exception=True)

        value = {"date": "2021-11-09", "time": "10:00--11:00"}
        self.assertTrue(validate(value))

        value = {"date": "2021-11-09123", "time": "10:00--11:00"}
        with self.assertRaises(ValidationError):
            validate(value)

        value = {"date": "2021-11-09", "time": "50:00--11:00"}
        with self.assertRaises(ValidationError):
            validate(value)

        value = {"date": "2021-11-09", "time": "10:00"}
        with self.assertRaises(ValidationError):
            validate(value)

    def test_backup(self):
        def validate(value):
            slz = BackupSerializer(data=value)
            return slz.is_valid(raise_exception=True)

        exclude_settings = [{"date": "2021-11-09", "time": "10:00--11:00"}]
        value = {
            "users": [
                {
                    "display_name": "运维人员",
                    "logo": "",
                    "id": "bk_biz_maintainer",
                    "type": "group",
                    "members": [{"id": "admin", "display_name": "admin"}],
                }
            ],
            "begin_time": "2022-03-11 00:00:00",
            "end_time": "2022-03-13 00:00:00",
            "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["08:00--18:00"]},
            "exclude_settings": exclude_settings,
        }
        self.assertTrue(validate(value))

    def test_weekly_rotation_duty(self):
        def validate(value):
            slz = DutyArrangeSlz(data=duty_data)
            return slz.is_valid(raise_exception=True)

        duty_data = {
            "need_rotation": True,
            "effective_time": "2022-03-11 00:00:00",
            "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
            "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["08:00--18:00"]}],
            "backups": [
                {
                    "users": [
                        {
                            "display_name": "运维人员",
                            "logo": "",
                            "id": "bk_biz_maintainer",
                            "type": "group",
                            "members": [{"id": "admin", "display_name": "admin"}],
                        }
                    ],
                    "begin_time": "2022-03-11 00:00:00",
                    "end_time": "2022-03-13 00:00:00",
                    "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["08:00--18:00"]},
                    "exclude_settings": [{"date": "2021-11-09", "time": "10:00--11:00"}],
                }
            ],
            "duty_users": [
                [
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                    {"display_name": "admin", "logo": "", "id": "admin", "type": "user"},
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                ]
            ],
        }
        self.assertTrue(validate(duty_data))

        duty_data["handoff_time"] = {}
        with self.assertRaises(ValidationError):
            validate(duty_data)

    def test_user_group_duty(self):
        self.create_duty_user_group()
        duty_objs = DutyArrange.objects.all()
        self.assertEqual(duty_objs.count(), 2)
        self.assertEqual(DutyArrange.objects.get(order=1).need_rotation, True)
        self.assertEqual(DutyArrange.objects.get(order=2).need_rotation, False)

    def test_user_group_with_no_duty(self):
        duty_arranges = [
            {
                "need_rotation": True,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["08:00--18:00"]}],
                "backups": [
                    {
                        "users": [
                            {
                                "display_name": "运维人员",
                                "logo": "",
                                "id": "bk_biz_maintainer",
                                "type": "group",
                                "members": [{"id": "admin", "display_name": "admin"}],
                            }
                        ],
                        "begin_time": "2022-03-11 00:00:00",
                        "end_time": "2022-03-13 00:00:00",
                        "duty_time": {
                            "work_type": "weekly",
                            "work_days": [1, 2, 3, 4, 5],
                            "work_time": ["08:00--18:00"],
                        },
                        "exclude_settings": [{"date": "2021-11-09", "time": "10:00--11:00"}],
                    }
                ],
                "users": [
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                    {"display_name": "admin", "logo": "", "id": "admin", "type": "user"},
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                ],
            },
            {
                "need_rotation": False,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": ["19:00--23:00"]}],
                "backups": [
                    {
                        "users": [
                            {
                                "display_name": "运维人员",
                                "logo": "",
                                "id": "bk_biz_maintainer",
                                "type": "group",
                                "members": [{"id": "admin", "display_name": "admin"}],
                            }
                        ],
                        "begin_time": "2022-03-11 00:00:00",
                        "end_time": "2022-03-13 00:00:00",
                        "duty_time": {
                            "work_type": "weekly",
                            "work_days": [1, 2, 3, 4, 5],
                            "work_time": ["08:00--18:00"],
                        },
                        "exclude_settings": [{"date": "2021-11-09", "time": "10:00--11:00"}],
                    }
                ],
                "users": [
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                    {"display_name": "admin", "logo": "", "id": "admin", "type": "user"},
                    {
                        "display_name": "运维人员",
                        "logo": "",
                        "id": "bk_biz_maintainer",
                        "type": "group",
                        "members": [{"id": "admin", "display_name": "admin"}],
                    },
                ],
            },
        ]

        user_group_data = copy.deepcopy(USER_GROUP_DATA)
        user_group_data.pop("duty_rules")
        user_group_data["need_duty"] = False
        user_group_data["duty_arranges"] = duty_arranges

        slz = UserGroupDetailSlz(data=user_group_data)
        slz.is_valid(raise_exception=True)
        slz.save()
        duty_objs = DutyArrange.objects.all()

        self.assertEqual(duty_objs.count(), 2)
        self.assertEqual(DutyArrange.objects.get(order=1).need_rotation, True)
        self.assertEqual(DutyArrange.objects.get(order=2).need_rotation, False)

    def test_user_group_plan(self):
        self.create_duty_user_group()
        user_groups = UserGroup.objects.all()
        users_mock = mock.patch(
            "bkmonitor.action.serializers.strategy.DutyBaseInfoSlz.users_representation",
            return_value=[
                {"id": "admin", "display_name": "admin", "type": "user"},
                {"id": "bk_biz_maintainer", "display_name": "bk_biz_maintainer", "type": "group"},
            ],
        )
        users_mock.start()

        duty_objs = DutyArrange.objects.all()
        for duty_obj in duty_objs:
            DutyPlan.objects.create(
                is_active=True,
                duty_arrange_id=duty_obj.id,
                user_group_id=duty_obj.user_group_id,
                users=duty_obj.duty_users[0],
                duty_time=duty_obj.duty_time,
                begin_time=datetime.now(tz=timezone.utc),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                order=duty_obj.order,
            )
        slz = UserGroupSlz(instance=user_groups, many=True)
        group_data = slz.data
        users_id = [user["id"] for user in group_data[0]["users"]]
        self.assertTrue({"admin", "bk_biz_maintainer"}.issubset(set(users_id)))
        self.assertTrue(group_data[0]["channels"] == NoticeChannel.DEFAULT_CHANNELS)

        slz = UserGroupDetailSlz(instance=user_groups.first())
        group_data = slz.data
        self.assertTrue("notice_ways" in group_data["alert_notice"][0]["notify_config"][0])
        self.assertTrue(group_data["channels"] == NoticeChannel.DEFAULT_CHANNELS)
        users_mock.stop()

    def test_validate_user_group_new(self):
        user_group_data = {
            "name": "test-内部通知对象",
            "desc": "",
            "need_duty": False,
            "duty_arranges": [
                {
                    "duty_type": "always",
                    "work_time": ["always"],
                    "users": [
                        {
                            "display_name": "运维人员",
                            "logo": "",
                            "id": "bk_biz_maintainer",
                            "type": "group",
                            "members": [
                                {"id": "admin", "display_name": "admin"},
                                {"id": "selina", "display_name": "selina"},
                            ],
                        }
                    ],
                }
            ],
            "alert_notice": [
                {
                    "time_range": "00:00:00--23:59:00",
                    "notify_config": [
                        {"level": 3, "notice_ways": [{"name": "weixin"}]},
                        {"level": 2, "notice_ways": [{"name": "mail"}]},
                        {"level": 1, "notice_ways": [{"name": "sms"}]},
                    ],
                }
            ],
            "action_notice": [
                {
                    "time_range": "00:00:00--23:59:00",
                    "notify_config": [
                        {"notice_ways": [{"name": "mail"}], "phase": 3},
                        {"notice_ways": [{"name": "sms"}], "phase": 2},
                        {"notice_ways": [{"name": "voice"}], "phase": 1},
                    ],
                }
            ],
            "channels": ["user"],
            "bk_biz_id": 2,
        }
        slz = UserGroupDetailSlz(data=user_group_data)
        self.assertTrue(slz.is_valid(raise_exception=False))


class TestDutyRuleSlz(BaseTestCase):
    def test_create_duty_rule(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "regular",
            "duty_arranges": [
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
            ],
        }
        slz = DutyRuleDetailSlz(data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        instance = slz.save()
        duty_arrange = DutyArrange.objects.get(duty_rule_id=instance.id)

        # 产生了一条记录之后，去掉duty_users无效的参数，保存duty_arranges仍然不变
        duty_rule["duty_arranges"] = [
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            }
        ]

        slz = DutyRuleDetailSlz(instance=instance, data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        instance = slz.save()
        latest_duty_arrange = DutyArrange.objects.get(duty_rule_id=instance.id)
        print("duty_arrange.hash", duty_arrange.hash)
        self.assertTrue(latest_duty_arrange.id == duty_arrange.id)

    def test_create_handoff_duty_rule(self):
        duty_rule = self.get_handoff_duty_rule("handoff duty")
        slz = DutyRuleDetailSlz(data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))

    def test_handoff_duty_arrange(self):
        def validate(value):
            slz = DutyArrangeSlz(data=value)
            return slz.is_valid(raise_exception=True)

        # 正常的为True
        duty_arrange = self.get_handoff_duty_arrange()
        self.assertTrue(validate(duty_arrange))

        duty_arrange["group_number"] = 0
        with self.assertRaises(ValidationError):
            # 人员轮转的，人数不正确，应该报错
            validate(duty_arrange)

    def test_create_multi_regular_duty_rule(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "regular",
            "duty_arranges": [
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
                },
                {
                    "duty_time": [
                        {"work_type": "monthly", "work_days": [1, 2, 3, 4, 5], "work_time": ["00:00--23:59"]}
                    ],
                    "duty_users": [
                        [
                            {
                                "id": "admin",
                                "type": "user",
                            },
                            {
                                "id": "admin1",
                                "type": "user",
                            },
                        ]
                    ],
                    "backups": [],
                },
            ],
        }
        slz = DutyRuleDetailSlz(data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        instance = slz.save()
        self.assertEqual(DutyArrange.objects.filter(duty_rule_id=instance.id).count(), 2)
        duty_arrange = DutyArrange.objects.get(duty_rule_id=instance.id, order=1)

        # 产生了一条记录之后，去掉duty_users无效的参数，保存duty_arranges仍然不变
        duty_rule["duty_arranges"] = [
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            }
        ]

        slz = DutyRuleDetailSlz(instance=instance, data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        instance = slz.save()
        latest_duty_arrange = DutyArrange.objects.get(duty_rule_id=instance.id)
        self.assertTrue(latest_duty_arrange.id == duty_arrange.id)
        self.assertTrue(latest_duty_arrange.hash == duty_arrange.hash)

        # 增加一个duty_arrange, 调整了顺序
        duty_rule["duty_arranges"] = [
            {
                "duty_time": [{"work_type": "weekend", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            },
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            },
        ]

        slz = DutyRuleDetailSlz(instance=instance, data=duty_rule)
        self.assertTrue(slz.is_valid(raise_exception=True))
        instance = slz.save()
        # 挪动了顺序，所以顺序跑到了第二位
        same_duty_arrange = DutyArrange.objects.get(duty_rule_id=instance.id, order=2)
        self.assertTrue(same_duty_arrange.id == duty_arrange.id)

    def test_duty_rule_relation(self):
        pass

    def test_duty_rules_list(self):
        for i in range(0, 10):
            self.create_regular_duty_rule(f"test{i}")

        queryset = DutyRule.objects.filter(bk_biz_id=2).order_by("update_time")
        self.assertEqual(queryset.count(), 10)
        list_data = DutyRuleSlz(instance=queryset, many=True).data

        self.assertEqual(list_data[0]["user_groups"], [])

    def test_duty_rule_detail(self):
        self.create_regular_duty_rule("test duty rule")
        instance = DutyRule.objects.get(name="test duty rule")
        data = DutyRuleDetailSlz(instance=instance).data

        self.assertIsNotNone(data.get("duty_arranges"))

        expected_hash = "252c671d9c9fa8c429c3922c3aba22a2"
        self.assertEqual(data["duty_arranges"][0]["hash"], expected_hash)


class TestDutyRuleResource(BaseTestCase):
    def setUp(self):
        DutyRule.objects.all().delete()
        DutyRuleSnap.objects.all().delete()
        DutyPlan.objects.all().delete()

    def tearDown(self):
        DutyRule.objects.all().delete()
        DutyRuleSnap.objects.all().delete()
        DutyPlan.objects.all().delete()

    def test_create_multi_regular_duty_rule(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "regular",
            "duty_arranges": [
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
                },
                {
                    "duty_time": [
                        {"work_type": "monthly", "work_days": [1, 2, 3, 4, 5], "work_time": ["00:00--23:59"]}
                    ],
                    "duty_users": [
                        [
                            {
                                "id": "admin",
                                "type": "user",
                            },
                            {
                                "id": "admin1",
                                "type": "user",
                            },
                        ]
                    ],
                    "backups": [],
                },
            ],
        }
        r = SaveDutyRuleResource()
        data = r.request(duty_rule)
        self.assertEqual(data["name"], duty_rule["name"])
        self.assertEqual(DutyArrange.objects.filter(duty_rule_id=data["id"]).count(), 2)
        duty_arrange = DutyArrange.objects.get(duty_rule_id=data["id"], order=1)

        # 产生了一条记录之后，去掉duty_users无效的参数，保存duty_arranges仍然不变
        duty_rule["duty_arranges"] = [
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            }
        ]
        duty_rule["id"] = data["id"]

        new_data = r.request(duty_rule)
        latest_duty_arrange = DutyArrange.objects.get(duty_rule_id=new_data["id"])

        self.assertTrue(latest_duty_arrange.id == duty_arrange.id)
        self.assertTrue(latest_duty_arrange.hash == duty_arrange.hash)

        # 增加一个duty_arrange, 调整了顺序
        duty_rule["duty_arranges"] = [
            {
                "duty_time": [{"work_type": "weekend", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            },
            {
                "duty_time": [{"work_type": "daily", "work_days": [], "work_time": ["00:00--23:59"]}],
                "duty_users": [[{"id": "bk_biz_maintainer", "type": "group"}]],
                "backups": [],
            },
        ]

        duty_rule["id"] = new_data["id"]
        new_data = r.request(duty_rule)
        # 挪动了顺序，所以顺序跑到了第二位
        same_duty_arrange = DutyArrange.objects.get(duty_rule_id=new_data["id"], order=2)
        self.assertTrue(same_duty_arrange.id == duty_arrange.id)

        user_group_data = copy.deepcopy(USER_GROUP_DATA)
        user_group_data["need_duty"] = True
        user_group_data["duty_rules"] = [new_data["id"]]
        UserGroup.objects.create(**user_group_data)

        self.assertEqual(UserGroup.objects.filter(duty_rules__contains=new_data["id"]).count(), 1)

    def test_api_duty_preview(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "source_type": "API",
            "begin_time": "2023-07-25 11:00:00",
            "config": {
                "effective_time": "2023-07-25 11:00:00",
                "end_time": "",
                "labels": ["mysql", "redis", "business"],
                "enabled": True,
                "category": "regular",
                "duty_arranges": [
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
                ],
            },
        }
        r = PreviewDutyRulePlanResource()
        data = r.request(duty_rule)
        self.assertEqual(len(data), 1)

    def test_db_duty_preview(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
            "end_time": "",
            "labels": ["mysql", "redis", "business"],
            "enabled": True,
            "category": "regular",
            "duty_arranges": [
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
            ],
        }

        r = SaveDutyRuleResource()
        data = r.request(duty_rule)
        self.assertIsNotNone(data.get("id"))
        duty_id = data["id"]
        preview_data = {"source_type": "DB", "bk_biz_id": 2}
        r = PreviewDutyRulePlanResource()
        with self.assertRaises(ValidationError):
            r.request(preview_data)
        preview_data = {"source_type": "DB", "id": duty_id, "bk_biz_id": 2}
        data = r.request(preview_data)
        self.assertEqual(len(data), 1)
        # 每天轮一次产生了30天的排班
        self.assertEqual(len(data[0]["work_times"]), 30)

        user_group_view = {"source_type": "API", "duty_rules": [duty_id], "bk_biz_id": 2}
        r = PreviewUserGroupPlanResource()
        with self.assertRaises(ValidationError):
            # 通过API方式进行请求，应该返回config字段不能为空的error
            r.validate_request_data(user_group_view)

        user_group_view = {"source_type": "API", "config": {"duty_rules": [duty_id]}, "bk_biz_id": 2}
        r = PreviewUserGroupPlanResource()
        data = r.request(user_group_view)
        print(data)

    def test_multi_db_duty_preview(self):
        duty_rule = {
            "name": "duty rule",
            "bk_biz_id": 2,
            "effective_time": "2023-07-25 11:00:00",
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
                            "period_settings": {},
                        }
                    ],
                    "duty_users": [
                        [
                            {"id": "admin1", "type": "user"},
                            {"id": "admin2", "type": "user"},
                            {"id": "admin3", "type": "user"},
                            {"id": "admin4", "type": "user"},
                        ]
                    ],
                    "group_type": "auto",
                    "group_number": 1,
                },
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
                    "duty_users": [[{"id": "admin", "type": "user"}]],
                },
            ],
        }
        r = SaveDutyRuleResource()
        data = r.request(duty_rule)
        self.assertIsNotNone(data.get("id"))
        duty_id = data["id"]
        r = PreviewDutyRulePlanResource()
        preview_data = {"source_type": "DB", "id": duty_id, "bk_biz_id": 2}
        data = r.request(preview_data)
        print(data)
        self.assertEqual(len(data), 60)
        # 每天轮一次产生了30天的排班
        self.assertEqual(len(data[0]["work_times"]), 1)


class TestPreviewDutyRulePlanResource(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.users_representation_mock = mock.patch(
            "bkmonitor.action.serializers.strategy.DutyBaseInfoSlz.users_representation", side_effect=lambda x: x
        )
        self.users_representation_mock.start()

    def test_db(self):
        duty_rule_data = copy.deepcopy(DUTY_RULE_DATA)
        slz = DutyRuleDetailSlz(data=duty_rule_data)
        slz.is_valid(raise_exception=True)
        duty_rule = slz.save()

        query_params = {
            "bk_biz_id": duty_rule_data["bk_biz_id"],
            "begin_time": "2024-02-23 00:00:00",
            "days": 35,
            "id": duty_rule.id,
            "source_type": "DB",
        }

        duty_plans = PreviewDutyRulePlanResource().request(query_params)
        self.assertEqual(len(duty_plans), query_params["days"])
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin1")

        duty_plans = PreviewDutyRulePlanResource().request({**query_params, "begin_time": "2024-06-23 00:00:00"})
        self.assertEqual(len(duty_plans), query_params["days"])
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin2")

        duty_plans = PreviewDutyRulePlanResource().request({**query_params, "begin_time": "2024-02-22 00:00:00"})
        self.assertEqual(len(duty_plans), query_params["days"])
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin")


class TestPreviewUserGroupPlanResource(TestPreviewDutyRulePlanResource):
    def setUp(self):
        super().setUp()
        self.users_representation_mock = mock.patch(
            "bkmonitor.action.serializers.strategy.DutyBaseInfoSlz.users_representation", side_effect=lambda x: x
        )
        self.users_representation_mock.start()

    def test_db(self):
        duty_rule_data = copy.deepcopy(DUTY_RULE_DATA)
        slz = DutyRuleDetailSlz(data=duty_rule_data)
        slz.is_valid(raise_exception=True)
        duty_rule = slz.save()

        user_group_data = copy.deepcopy(USER_GROUP_DATA)
        user_group_data["need_duty"] = True
        user_group_data["duty_rules"] = [duty_rule.id]

        with mock.patch(
            "bkmonitor.action.serializers.strategy.time_tools.datetime_today",
            return_value=time_tools.str2datetime(duty_rule_data["effective_time"]),
        ):
            # 创建会提前排好一个月的数据
            g_slz = UserGroupDetailSlz(data=user_group_data)
            g_slz.is_valid(raise_exception=True)
            g_slz.save()

        query_params = {
            "bk_biz_id": duty_rule_data["bk_biz_id"],
            "begin_time": "2024-02-22 00:00:00",
            "days": 7,
            "id": g_slz.instance.id,
            "source_type": "DB",
        }

        duty_plans = PreviewUserGroupPlanResource().request(query_params)[0]["duty_plans"]
        self.assertEqual(len(duty_plans), 30)
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin")

        duty_plans = PreviewUserGroupPlanResource().request({**query_params, "begin_time": "2024-06-23 00:00:00"})[0][
            "duty_plans"
        ]
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin2")

    def test_db_with_change_rule(self):
        """测试两个快照并存时，预览两者还没生成排班的时间段。"""
        duty_rule_data = copy.deepcopy(DUTY_RULE_DATA)
        slz = DutyRuleDetailSlz(data=duty_rule_data)
        slz.is_valid(raise_exception=True)
        duty_rule = slz.save()

        user_group_data = copy.deepcopy(USER_GROUP_DATA)
        user_group_data["need_duty"] = True
        user_group_data["duty_rules"] = [duty_rule.id]

        with mock.patch(
            "bkmonitor.action.serializers.strategy.time_tools.datetime_today",
            return_value=time_tools.str2datetime(duty_rule_data["effective_time"]),
        ):
            # 创建会提前排好一个月的数据
            g_slz = UserGroupDetailSlz(data=user_group_data)
            g_slz.is_valid(raise_exception=True)
            g_slz.save()

            # 修改规则，这会生成一个新快照
            duty_rule_data["effective_time"] = "2024-03-24 00:00:00"
            duty_rule_data["duty_arranges"][0]["duty_users"][0][0]["id"] = "admin_new"
            slz = DutyRuleDetailSlz(instance=duty_rule, data=duty_rule_data)
            slz.is_valid(raise_exception=True)
            slz.save()

        query_params = {
            "bk_biz_id": duty_rule_data["bk_biz_id"],
            "begin_time": "2024-03-22 00:00:00",
            "days": 3,
            "id": g_slz.instance.id,
            "source_type": "DB",
        }
        duty_plans = PreviewUserGroupPlanResource().request(query_params)[0]["duty_plans"]

        # 旧快照负责到 23 号（之前已生成到 22 号的计划）
        # 新快照从 24 号开始（用户重新开始，第一个是修改后的 admin_new）
        self.assertEqual(len(duty_plans), 32)
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin2")
        self.assertEqual(duty_plans[1]["users"][0]["id"], "admin_new")

    def test_api(self):
        duty_rule_data = copy.deepcopy(DUTY_RULE_DATA)
        slz = DutyRuleDetailSlz(data=duty_rule_data)
        slz.is_valid(raise_exception=True)
        duty_rule = slz.save()

        query_params = {
            "source_type": "API",
            "days": 7,
            "begin_time": "2024-2-22 00:00:00",
            "config": {"duty_rules": [duty_rule.id]},
            "bk_biz_id": duty_rule_data["bk_biz_id"],
        }

        duty_plans = PreviewUserGroupPlanResource().request(query_params)[0]["duty_plans"]
        self.assertEqual(len(duty_plans), 7)
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin")

        duty_plans = PreviewUserGroupPlanResource().request({**query_params, "begin_time": "2024-2-23 00:00:00"})[0][
            "duty_plans"
        ]
        self.assertEqual(len(duty_plans), 7)
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin1")

        duty_plans = PreviewUserGroupPlanResource().request({**query_params, "begin_time": "2024-06-23 00:00:00"})[0][
            "duty_plans"
        ]
        self.assertEqual(len(duty_plans), 7)
        self.assertEqual(duty_plans[0]["users"][0]["id"], "admin2")
