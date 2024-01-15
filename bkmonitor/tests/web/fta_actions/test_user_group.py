# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from datetime import timedelta, timezone

import mock
from django.test import TestCase
from fta_web.action.resources.frontend_resources import BatchCreateResource

from bkmonitor.action.serializers.strategy import *  # noqa
from bkmonitor.models import DutyArrange, UserGroup

mock.patch(
    "core.drf_resource.api.bk_login.get_all_user",
    return_value={"results": [{"username": "admin", "display_name": "admin"}]},
).start()


class TestDutyArrangeSlzResource(TestCase):
    def setUp(self):
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()

    def tearDown(self):
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()

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

        value = {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": "08:00--18:00"}
        self.assertTrue(validate(value))

        value["work_days"] = [1, 2, 3, 4, 5, 9]
        with self.assertRaises(ValidationError):
            validate(value)

        value["work_days"] = 2
        value["work_time"] = "00:00--24:67"
        with self.assertRaises(ValidationError):
            validate(value)

        value["work_time"] = "00:00"
        with self.assertRaises(ValidationError):
            validate(value)

        monthly_value = {"work_type": "monthly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": "08:00--18:00"}
        self.assertTrue(validate(monthly_value))

        monthly_value["work_days"] = [32, 45, 12]
        with self.assertRaises(ValidationError):
            validate(value)

        daily_value = {"work_type": "monthly", "work_time": "08:00--18:00"}
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
            "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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
            "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"}],
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
                    "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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

    def create_duty_user_group(self):
        duty_arranges = [
            {
                "need_rotation": True,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5, 6, 7], "work_time": "00:00--23:59"}],
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
                        "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"}],
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
                        "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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

        user_group_data = {
            "name": "轮值用户组测试",
            "desc": "按照轮值的格式",
            "duty_arranges": duty_arranges,
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

        slz = UserGroupDetailSlz(data=user_group_data)
        slz.is_valid(raise_exception=True)
        slz.save()

    def test_user_group_with_no_duty(self):
        duty_arranges = [
            {
                "need_rotation": True,
                "effective_time": "2022-03-11 00:00:00",
                "handoff_time": {"rotation_type": "weekly", "date": 1, "time": "08:00"},
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"}],
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
                        "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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
                "duty_time": [{"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"}],
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
                        "duty_time": {"work_type": "weekly", "work_days": [1, 2, 3, 4, 5], "work_time": "08:00--18:00"},
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

        user_group_data = {
            "name": "轮值用户组测试",
            "desc": "按照轮值的格式",
            "duty_arranges": duty_arranges,
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
                    "work_time": "always",
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


class TestUserGroupResource(TestCase):
    def batch_create_resource(self):
        request_data = {
            "bk_biz_id": 2,
            "create_data": [
                {
                    "alert_ids": self.alert_ids[:4],
                    "config_ids": [self.ac.id],
                },
                {
                    "alert_ids": self.alert_ids[5:],
                    "config_ids": [self.ac.id],
                },
            ],
        }
        response_data = BatchCreateResource().request(**request_data)
        self.assertTrue(response_data["result"])
        self.assertEqual(len(response_data["actions"]), 2)
