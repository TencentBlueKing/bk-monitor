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
from monitor_web.custom_report.resources import (
    CreateOrUpdateGroupingRule,
    CustomTimeSeriesDetail,
    CustomTsGroupingRuleList,
    DeleteCustomEventGroup,
    DeleteCustomTimeSeries,
    GetCustomEventGroup,
    GroupCustomTSItem,
    ModifyCustomTsGroupingRuleList,
    QueryCustomEventTarget,
    check_biz_permission,
)

MODULE = "monitor_web.custom_report.resources"

# 删除接口带 atomic 装饰器，测试通过 perform_request.__wrapped__ 调用以避免连接数据库


class Denied(Exception):
    pass


class Stop(Exception):
    pass


def _obj(bk_biz_id, is_platform=False, **kwargs):
    return SimpleNamespace(bk_biz_id=bk_biz_id, is_platform=is_platform, **kwargs)


def _deny(permission_cls):
    permission_cls.return_value.is_allowed_by_biz.side_effect = Denied


class TestCheckBizPermission(TestCase):
    @mock.patch(f"{MODULE}.Permission")
    def test_checks_object_biz(self, permission_cls):
        check_biz_permission(_obj(3), ActionEnum.MANAGE_CUSTOM_METRIC)
        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_CUSTOM_METRIC, raise_exception=True
        )

    @mock.patch(f"{MODULE}.Permission")
    def test_platform_and_global_objects_readable(self, permission_cls):
        for obj in (_obj(3, is_platform=True), _obj(0)):
            check_biz_permission(obj, ActionEnum.VIEW_CUSTOM_METRIC, allow_public=True)
        permission_cls.assert_not_called()

    @mock.patch(f"{MODULE}.Permission")
    def test_platform_object_checked_without_allow_public(self, permission_cls):
        check_biz_permission(_obj(3, is_platform=True), ActionEnum.MANAGE_CUSTOM_EVENT)
        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_CUSTOM_EVENT, raise_exception=True
        )


class TestCustomEventGroupBizPermission(TestCase):
    detail_params = {"bk_event_group_id": 1, "time_range": "", "need_refresh": False, "bk_biz_id": 2}

    @mock.patch(f"{MODULE}.CustomEventGroupDetailSerializer")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_detail_of_other_biz_group_denied(self, group_objects, permission_cls, serializer_cls):
        group_objects.prefetch_related.return_value.get.return_value = _obj(3)
        _deny(permission_cls)

        with self.assertRaises(Denied):
            GetCustomEventGroup().perform_request(dict(self.detail_params))

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.VIEW_CUSTOM_EVENT, raise_exception=True
        )
        serializer_cls.assert_not_called()

    @mock.patch(f"{MODULE}.CustomEventGroupDetailSerializer", side_effect=Stop)
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_detail_of_platform_group_readable(self, group_objects, permission_cls, serializer_cls):
        group = _obj(3, is_platform=True)
        group_objects.prefetch_related.return_value.get.return_value = group

        with self.assertRaises(Stop):
            GetCustomEventGroup().perform_request(dict(self.detail_params))

        permission_cls.assert_not_called()
        serializer_cls.assert_called_once_with(group, context={"request_bk_biz_id": 2})

    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_query_target_of_other_biz_group_denied(self, group_objects, permission_cls):
        group = _obj(3, query_target=mock.Mock())
        group_objects.get.return_value = group
        _deny(permission_cls)

        with self.assertRaises(Denied):
            QueryCustomEventTarget().perform_request({"bk_event_group_id": 1})
        group.query_target.assert_not_called()

    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_query_target_of_platform_group_readable(self, group_objects, permission_cls):
        group_objects.get.return_value = _obj(3, is_platform=True, query_target=lambda: ["a", "a"])

        self.assertEqual(QueryCustomEventTarget().perform_request({"bk_event_group_id": 1}), ["a"])
        permission_cls.assert_not_called()

    @mock.patch(f"{MODULE}.api")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_delete_of_other_biz_group_denied(self, group_objects, permission_cls, api):
        group = _obj(3, is_platform=True, bk_event_group_id=1, delete=mock.Mock())
        group_objects.get.return_value = group
        _deny(permission_cls)

        with self.assertRaises(Denied):
            DeleteCustomEventGroup.perform_request.__wrapped__(DeleteCustomEventGroup(), {"bk_event_group_id": 1})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_CUSTOM_EVENT, raise_exception=True
        )
        api.metadata.delete_event_group.assert_not_called()
        group.delete.assert_not_called()

    @mock.patch(f"{MODULE}.CustomEventItem.objects")
    @mock.patch(f"{MODULE}.api")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomEventGroup.objects")
    def test_delete_of_own_group(self, group_objects, permission_cls, api, item_objects):
        group = _obj(2, bk_event_group_id=1, delete=mock.Mock())
        group_objects.get.return_value = group

        DeleteCustomEventGroup.perform_request.__wrapped__(DeleteCustomEventGroup(), {"bk_event_group_id": 1})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            2, ActionEnum.MANAGE_CUSTOM_EVENT, raise_exception=True
        )
        self.assertEqual(api.metadata.delete_event_group.call_args[1]["event_group_id"], 1)
        group.delete.assert_called_once_with()
        item_objects.filter.assert_called_once_with(bk_event_group_id=1)


class TestCustomTimeSeriesBizPermission(TestCase):
    @mock.patch(f"{MODULE}.CustomTSItem.objects")
    @mock.patch(f"{MODULE}.api")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_delete_of_other_biz_table_denied(self, table_objects, permission_cls, api, item_objects):
        table = _obj(3, time_series_group_id=10, delete=mock.Mock())
        table_objects.get.return_value = table
        _deny(permission_cls)

        with self.assertRaises(Denied):
            DeleteCustomTimeSeries.perform_request.__wrapped__(DeleteCustomTimeSeries(), {"time_series_group_id": 10})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.MANAGE_CUSTOM_METRIC, raise_exception=True
        )
        api.metadata.delete_time_series_group.assert_not_called()
        item_objects.filter.assert_not_called()
        table.delete.assert_not_called()

    @mock.patch(f"{MODULE}.CustomTSTableSerializer")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_detail_of_other_biz_table_denied(self, table_objects, permission_cls, serializer_cls):
        table_objects.get.return_value = _obj(3)
        _deny(permission_cls)

        with self.assertRaises(Denied):
            CustomTimeSeriesDetail().perform_request({"time_series_group_id": 10, "bk_biz_id": 2, "model_only": True})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.VIEW_CUSTOM_METRIC, raise_exception=True
        )
        serializer_cls.assert_not_called()

    @mock.patch(f"{MODULE}.CustomTSTableSerializer")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_detail_of_public_table_readable(self, table_objects, permission_cls, serializer_cls):
        for table in (_obj(3, is_platform=True), _obj(0)):
            table_objects.get.return_value = table
            serializer_cls.return_value.data = {"time_series_group_id": 10}

            result = CustomTimeSeriesDetail().perform_request(
                {"time_series_group_id": 10, "bk_biz_id": 2, "model_only": True}
            )

            self.assertEqual(result, {"time_series_group_id": 10})
            serializer_cls.assert_called_with(table, context={"request_bk_biz_id": 2})
        permission_cls.assert_not_called()

    @mock.patch(f"{MODULE}.CustomTSGroupingRuleSerializer")
    @mock.patch(f"{MODULE}.CustomTSGroupingRule.objects")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_grouping_rule_list_of_platform_table_readable(
        self, table_objects, permission_cls, rule_objects, serializer_cls
    ):
        table_objects.get.return_value = _obj(3, is_platform=True)
        serializer_cls.return_value.data = [{"name": "g"}]

        result = CustomTsGroupingRuleList().perform_request({"time_series_group_id": 10})

        self.assertEqual(result, [{"name": "g"}])
        table_objects.get.assert_called_once_with(pk=10)
        permission_cls.assert_not_called()
        rule_objects.filter.assert_called_once_with(time_series_group_id=10)

    @mock.patch(f"{MODULE}.CustomTSGroupingRule.objects")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_grouping_rule_list_of_other_biz_table_denied(self, table_objects, permission_cls, rule_objects):
        table_objects.get.return_value = _obj(3)
        _deny(permission_cls)

        with self.assertRaises(Denied):
            CustomTsGroupingRuleList().perform_request({"time_series_group_id": 10})
        rule_objects.filter.assert_not_called()

    @mock.patch(f"{MODULE}.CustomTSItem.objects")
    @mock.patch(f"{MODULE}.CustomTSGroupingRule.objects")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_grouping_rule_writes_check_table_biz(self, table_objects, permission_cls, rule_objects, item_objects):
        # 平台级分组只放开读取，写操作仍按所属业务校验
        table_objects.get.return_value = _obj(3, is_platform=True)
        _deny(permission_cls)
        cases = [
            (ModifyCustomTsGroupingRuleList, {"time_series_group_id": 10, "group_list": []}),
            (CreateOrUpdateGroupingRule, {"time_series_group_id": 10, "name": "g"}),
            (GroupCustomTSItem, {"time_series_group_id": 10}),
        ]
        for resource_cls, params in cases:
            with self.subTest(resource=resource_cls.__name__):
                permission_cls.reset_mock()
                with self.assertRaises(Denied):
                    resource_cls().perform_request(params)
                permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
                    3, ActionEnum.MANAGE_CUSTOM_METRIC, raise_exception=True
                )

        table_objects.get.assert_called_with(pk=10)
        rule_objects.filter.assert_not_called()
        rule_objects.create.assert_not_called()
        item_objects.filter.assert_not_called()

    @mock.patch(f"{MODULE}.resource")
    @mock.patch(f"{MODULE}.CustomTSGroupingRule.objects")
    @mock.patch(f"{MODULE}.Permission")
    @mock.patch(f"{MODULE}.CustomTSTable.objects")
    def test_modify_grouping_rules_of_own_table(self, table_objects, permission_cls, rule_objects, resource):
        table_objects.get.return_value = _obj(2)

        result = ModifyCustomTsGroupingRuleList().perform_request({"time_series_group_id": 10, "group_list": []})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            2, ActionEnum.MANAGE_CUSTOM_METRIC, raise_exception=True
        )
        resource.custom_report.group_custom_ts_item.assert_called_once_with(time_series_group_id=10)
        self.assertIs(result, resource.custom_report.group_custom_ts_item.return_value)
