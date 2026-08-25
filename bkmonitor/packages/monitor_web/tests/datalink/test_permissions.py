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
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from bkmonitor.iam import ActionEnum
from monitor_web.datalink.views import CollectConfigActionPermission, DatalinkStatusViewSet
from monitor_web.models.collecting import CollectConfigMeta


class TestCollectConfigActionPermission(TestCase):
    def test_deny_without_collect_config_id(self):
        perm = CollectConfigActionPermission([ActionEnum.MANAGE_COLLECTION])
        request = SimpleNamespace(method="POST", data={}, query_params={})
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_get_without_collect_config_id(self):
        perm = CollectConfigActionPermission([ActionEnum.VIEW_COLLECTION])
        request = SimpleNamespace(method="GET", data={}, query_params={})
        self.assertFalse(perm.has_permission(request, None))

    def test_deny_when_collect_config_missing(self):
        perm = CollectConfigActionPermission([ActionEnum.MANAGE_COLLECTION])
        request = SimpleNamespace(method="POST", data={"collect_config_id": 1}, query_params={})
        with mock.patch("monitor_web.datalink.views.CollectConfigMeta.objects.only") as only:
            only.return_value.get.side_effect = CollectConfigMeta.DoesNotExist
            self.assertFalse(perm.has_permission(request, None))

    def test_deny_when_collect_config_has_no_biz_id(self):
        perm = CollectConfigActionPermission([ActionEnum.MANAGE_COLLECTION])
        request = SimpleNamespace(method="POST", data={"collect_config_id": 1}, query_params={})
        with mock.patch("monitor_web.datalink.views.CollectConfigMeta.objects.only") as only:
            only.return_value.get.return_value = SimpleNamespace(id=1, bk_biz_id=0)
            self.assertFalse(perm.has_permission(request, None))

    def test_uses_collect_config_biz_id_even_without_request_biz_id(self):
        perm = CollectConfigActionPermission([ActionEnum.MANAGE_COLLECTION])
        request = SimpleNamespace(method="POST", data={"collect_config_id": 9}, query_params={})
        with mock.patch("monitor_web.datalink.views.CollectConfigMeta.objects.only") as only, mock.patch(
            "bkmonitor.iam.drf.Permission"
        ) as perm_cls:
            only.return_value.get.return_value = SimpleNamespace(id=9, bk_biz_id=22)
            perm_cls.return_value.is_allowed.return_value = True
            self.assertTrue(perm.has_permission(request, None))
            self.assertEqual(len(perm.resources), 1)
            perm_cls.return_value.is_allowed.assert_called()

    def test_update_action_uses_collect_config_permission(self):
        view = DatalinkStatusViewSet()
        view.action = "update_alert_user_groups"
        permissions = view.get_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], CollectConfigActionPermission)
