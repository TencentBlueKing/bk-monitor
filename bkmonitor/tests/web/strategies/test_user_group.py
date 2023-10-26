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


from django.test import TestCase
from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import DutyArrange, UserGroup


class TestUserGroupSlz(TestCase):
    def setUp(self):
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()

    def tearDown(self) -> None:
        UserGroup.objects.all().delete()
        DutyArrange.objects.all().delete()

    def test_user_group_create(self):
        data = {
            "name": "测试用户组",
            "desc": "用户组的说明",
            "bk_biz_id": 2,
            "duty_arranges": [
                {
                    "duty_type": "always",
                    "work_time": "always",
                    "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
                },
                {
                    "duty_type": "week",
                    "work_time": "always",
                    "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
                },
            ],
        }
        user_slz = UserGroupDetailSlz(data=data)
        user_slz.is_valid(raise_exception=True)
        self.assertIsNotNone(user_slz.save())
        self.assertEqual(DutyArrange.objects.filter(user_group_id=user_slz.instance.id).count(), 2)

    def test_user_group_name_error(self):
        data = {
            "name": "测试用户组",
            "desc": "用户组的说明",
            "bk_biz_id": 2,
            "duty_arranges": [
                {
                    "duty_type": "always",
                    "work_time": "always",
                    "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
                },
                {
                    "duty_type": "week",
                    "work_time": "always",
                    "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
                },
            ],
        }
        user_slz = UserGroupDetailSlz(data=data)
        user_slz.is_valid(raise_exception=True)
        self.assertIsNotNone(user_slz.save())
        self.assertEqual(DutyArrange.objects.filter(user_group_id=user_slz.instance.id).count(), 2)

        user_slz2 = UserGroupDetailSlz(data=data)
        self.assertFalse(user_slz2.is_valid())
