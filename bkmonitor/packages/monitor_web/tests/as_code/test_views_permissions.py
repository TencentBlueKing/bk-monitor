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
from unittest import TestCase

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from monitor_web.as_code.views import AsCodeViewSet


class TestAsCodeViewSetPermissions(TestCase):
    def assert_actions(self, action, expected):
        view = AsCodeViewSet()
        view.action = action
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], BusinessActionPermission)
        self.assertEqual(permissions[0].actions, expected)

    def test_import_actions_require_manage(self):
        for action in ("import_config", "import_config_file"):
            with self.subTest(action=action):
                self.assert_actions(action, [ActionEnum.MANAGE_RULE, ActionEnum.MANAGE_NOTIFY_TEAM])

    def test_export_actions_require_view(self):
        for action in ("export_config", "export_config_json", "export_config_file"):
            with self.subTest(action=action):
                self.assert_actions(action, [ActionEnum.VIEW_RULE, ActionEnum.VIEW_NOTIFY_TEAM])
