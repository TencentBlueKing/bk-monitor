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
from unittest import TestCase, mock

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.permission import Permission


class TestTokenActionPermission(TestCase):
    """携带分享令牌时按令牌类型校验动作"""

    def _make_permission(self, token="token-xxx"):
        with mock.patch.object(Permission, "get_iam_client", return_value=mock.MagicMock()):
            permission = Permission(username="tester")
        permission.token = token
        permission.skip_check = False
        permission.iam_client.is_allowed.return_value = False
        permission.iam_client.is_allowed_with_cache.return_value = False
        return permission

    def _run(self, permission, action, record, request=None):
        with mock.patch("bkmonitor.iam.permission.ApiAuthToken.objects.get", return_value=record), mock.patch(
            "bkmonitor.iam.permission.get_request", return_value=request
        ):
            return permission.is_allowed(action)

    def test_action_outside_token_type_is_not_granted(self):
        # host 类型令牌对应主机查看动作
        permission = self._make_permission()
        allowed = self._run(permission, ActionEnum.MANAGE_HOST, SimpleNamespace(type="host"))
        self.assertFalse(allowed)

    def test_action_within_token_type_is_granted(self):
        permission = self._make_permission()
        allowed = self._run(permission, ActionEnum.VIEW_HOST, SimpleNamespace(type="host"))
        self.assertTrue(allowed)
        permission.iam_client.is_allowed.assert_not_called()
        permission.iam_client.is_allowed_with_cache.assert_not_called()

    def test_view_business_is_granted(self):
        permission = self._make_permission()
        allowed = self._run(permission, ActionEnum.VIEW_BUSINESS, SimpleNamespace(type="host"))
        self.assertTrue(allowed)

    def test_unknown_token_type_is_not_granted(self):
        # 未登记的令牌类型按无对应动作处理
        permission = self._make_permission()
        allowed = self._run(permission, ActionEnum.MANAGE_HOST, SimpleNamespace(type="not-a-scene"))
        self.assertFalse(allowed)

    def test_missing_token_record_is_not_granted(self):
        permission = self._make_permission()
        allowed = self._run(permission, ActionEnum.MANAGE_HOST, None)
        self.assertFalse(allowed)

    def test_api_path_is_granted_and_missing_request_is_tolerated(self):
        permission = self._make_permission()
        request = SimpleNamespace(path="/rest/v2/grafana/time_series/unify_query/")
        self.assertTrue(self._run(permission, ActionEnum.MANAGE_HOST, SimpleNamespace(type="host"), request))
        # request 缺失时正常返回
        self.assertFalse(self._run(permission, ActionEnum.MANAGE_HOST, SimpleNamespace(type="host"), None))
