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
from bkmonitor.models import Shield
from core.errors.shield import ShieldNotExist
from monitor_web.shield.resources.backend_resources import (
    DisableShieldResource,
    EditShieldResource,
    ShieldDetailResource,
)

MODULE = "monitor_web.shield.resources.backend_resources"


class Denied(Exception):
    pass


def _shield(bk_biz_id, is_enabled=True):
    return SimpleNamespace(id=1, bk_biz_id=bk_biz_id, is_enabled=is_enabled, save=mock.Mock())


@mock.patch(f"{MODULE}.Permission")
@mock.patch(f"{MODULE}.Shield.objects")
class TestShieldBizPermission(TestCase):
    def test_detail_checks_shield_biz(self, shield_objects, permission_cls):
        shield_objects.get.return_value = _shield(3)
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            ShieldDetailResource().perform_request({"id": 1, "bk_biz_id": 2})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.VIEW_DOWNTIME, raise_exception=True
        )

    def test_missing_shield_not_checked(self, shield_objects, permission_cls):
        shield_objects.get.side_effect = Shield.DoesNotExist

        with self.assertRaises(ShieldNotExist):
            ShieldDetailResource().perform_request({"id": 1, "bk_biz_id": 2})
        permission_cls.assert_not_called()

    @mock.patch(f"{MODULE}.handle_shield_time")
    def test_edit_checks_shield_biz(self, handle_shield_time, shield_objects, permission_cls):
        shield = _shield(3)
        shield_objects.get.return_value = shield
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            EditShieldResource().perform_request({"id": 1, "bk_biz_id": 2})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_DOWNTIME, raise_exception=True
        )
        handle_shield_time.assert_not_called()
        shield.save.assert_not_called()

    def test_disable_checks_shield_biz(self, shield_objects, permission_cls):
        shield = _shield(3)
        shield_objects.get.return_value = shield
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            DisableShieldResource().perform_request({"id": 1})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_DOWNTIME, raise_exception=True
        )
        self.assertTrue(shield.is_enabled)
        shield.save.assert_not_called()

    def test_disable_own_shield(self, shield_objects, permission_cls):
        shield = _shield(2)
        shield_objects.get.return_value = shield

        self.assertEqual(DisableShieldResource().perform_request({"id": 1}), "success")

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            2, ActionEnum.MANAGE_DOWNTIME, raise_exception=True
        )
        self.assertFalse(shield.is_enabled)
        shield.save.assert_called_once_with()
