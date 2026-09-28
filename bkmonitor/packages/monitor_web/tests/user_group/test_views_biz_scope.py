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

from monitor_web.user_group.views import DutyRuleViewSet, PermissionMixin

MODULE = "monitor_web.user_group.views"


class _BaseView:
    def __init__(self, queryset, action, biz_id):
        self.queryset = queryset
        self.action = action
        self.request = SimpleNamespace(biz_id=biz_id)

    def get_queryset(self):
        return self.queryset


class _View(PermissionMixin, _BaseView):
    pass


class TestPermissionMixinQueryset(TestCase):
    def test_list_limited_to_request_biz(self):
        queryset = mock.MagicMock()
        result = _View(queryset, "list", "2").get_queryset()
        queryset.filter.assert_called_once_with(bk_biz_id="2")
        self.assertIs(result, queryset.filter.return_value)

    def test_other_actions_not_filtered(self):
        queryset = mock.MagicMock()
        for action in ("retrieve", "update", "partial_update", "destroy"):
            self.assertIs(_View(queryset, action, "2").get_queryset(), queryset)
        queryset.filter.assert_not_called()


class TestDutyRuleSwitch(TestCase):
    @mock.patch(f"{MODULE}.DutyPlan.objects")
    @mock.patch(f"{MODULE}.DutyRuleSnap.objects")
    @mock.patch(f"{MODULE}.DutyRule.objects")
    @mock.patch(f"{MODULE}.DutySwitchSlz")
    def test_switch_uses_request_biz(self, slz_cls, rule_objects, snap_objects, plan_objects):
        slz_cls.return_value.data = {"ids": [1, 2], "enabled": False, "bk_biz_id": 9}
        rule_objects.filter.return_value.values_list.return_value = [1]
        request = SimpleNamespace(data={"ids": [1, 2], "enabled": False, "bk_biz_id": 9}, biz_id=2)

        response = DutyRuleViewSet().switch(request)

        rule_objects.filter.assert_any_call(id__in=[1, 2], bk_biz_id=2)
        rule_objects.filter.assert_any_call(id__in=[1])
        rule_objects.filter.return_value.update.assert_called_once_with(enabled=False)
        snap_objects.filter.assert_called_once_with(duty_rule_id__in=[1])
        plan_objects.filter.assert_called_once_with(duty_rule_id__in=[1])
        self.assertEqual(response.data, {"rule_ids": [1]})
