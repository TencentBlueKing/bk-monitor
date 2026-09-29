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
from bkmonitor.iam.drf import BusinessActionPermission


class TestBusinessActionPermissionBizId(TestCase):
    """请求参数中的业务 ID 与解析出的业务 ID 需保持一致"""

    def _request(self, method, biz_id, data=None, query=None):
        return SimpleNamespace(method=method, biz_id=biz_id, data=data or {}, query_params=query or {})

    @mock.patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=True)
    @mock.patch("bkmonitor.iam.drf.ResourceEnum.BUSINESS.create_instance")
    @mock.patch("bkmonitor.iam.drf.Permission")
    def _check(self, request, perm_cls, create_instance, _in_tenant):
        perm_cls.return_value.is_allowed.return_value = True
        permission = BusinessActionPermission([ActionEnum.VIEW_BUSINESS])
        return permission.has_permission(request, None), perm_cls

    def test_without_biz_id_keeps_existing_behavior(self):
        allowed, _ = self._check(self._request("POST", None))
        self.assertTrue(allowed)

    def test_consistent_body_biz_id_is_checked_by_iam(self):
        allowed, perm_cls = self._check(self._request("POST", "2", {"bk_biz_id": 2}))
        self.assertTrue(allowed)
        perm_cls.return_value.is_allowed.assert_called_once()

    def test_mismatched_body_biz_id_is_rejected(self):
        allowed, perm_cls = self._check(self._request("POST", "2", {"bk_biz_id": 3}))
        self.assertFalse(allowed)
        perm_cls.return_value.is_allowed.assert_not_called()

    def test_mismatched_alias_biz_id_is_rejected(self):
        allowed, _ = self._check(self._request("POST", "2", {"biz_id": 2, "bk_biz_id": 3}))
        self.assertFalse(allowed)

    def test_body_without_biz_id_is_checked_by_iam(self):
        allowed, perm_cls = self._check(self._request("POST", "2", {"name": "x"}))
        self.assertTrue(allowed)
        perm_cls.return_value.is_allowed.assert_called_once()

    def test_get_request_compares_query_params(self):
        allowed, _ = self._check(self._request("GET", "2", query={"bk_biz_id": "2"}))
        self.assertTrue(allowed)
        allowed, _ = self._check(self._request("GET", "2", query={"biz_id": "2", "bk_biz_id": "3"}))
        self.assertFalse(allowed)

    def test_get_request_ignores_body(self):
        allowed, _ = self._check(self._request("GET", "2", data={"bk_biz_id": 3}))
        self.assertTrue(allowed)
