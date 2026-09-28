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
import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase, mock

from bkmonitor.iam import ActionEnum
from constants.cmdb import TargetObjectType
from constants.strategy import TargetFieldType
from core.errors.export_import import ImportHistoryNotExistError
from monitor_web.export_import.constant import ConfigType
from monitor_web.export_import.resources import (
    AddMonitorTargetResource,
    ExportPackageRequestSerializer,
    ExportPackageResource,
)

MODULE = "monitor_web.export_import.resources"


class Denied(Exception):
    pass


class Stop(Exception):
    pass


class TestExportPackageRequestSerializer(TestCase):
    def test_list_data_only_does_not_require_biz(self):
        self.assertTrue(ExportPackageRequestSerializer(data={"list_data": [{"a": 1}]}).is_valid())

    def test_config_ids_require_biz(self):
        for key in ("collect_config_ids", "strategy_config_ids", "view_config_ids"):
            with self.subTest(key=key):
                slz = ExportPackageRequestSerializer(data={key: [1], "list_data": [{"a": 1}]})
                self.assertFalse(slz.is_valid())

    def test_empty_request_requires_biz(self):
        self.assertFalse(ExportPackageRequestSerializer(data={}).is_valid())

    def test_config_ids_with_biz(self):
        self.assertTrue(ExportPackageRequestSerializer(data={"bk_biz_id": 2, "strategy_config_ids": [1]}).is_valid())


class TestExportPackageBizScope(TestCase):
    @mock.patch.object(ExportPackageResource, "prepare_file")
    @mock.patch(f"{MODULE}.Permission")
    def test_export_checks_biz_permission(self, permission_cls, prepare_file):
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            ExportPackageResource().perform_request({"bk_biz_id": 2, "strategy_config_ids": [1]})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            2, ActionEnum.EXPORT_CONFIG, raise_exception=True
        )
        prepare_file.assert_not_called()

    @mock.patch.object(ExportPackageResource, "prepare_file", side_effect=Stop)
    @mock.patch(f"{MODULE}.Permission")
    def test_list_data_only_skips_biz_permission(self, permission_cls, prepare_file):
        with self.assertRaises(Stop):
            ExportPackageResource().perform_request({"list_data": [{"a": 1}]})
        permission_cls.assert_not_called()

    @mock.patch(f"{MODULE}.CollectConfigMeta.objects")
    @mock.patch(f"{MODULE}.QueryConfigModel.objects")
    @mock.patch(f"{MODULE}.ItemModel.objects")
    @mock.patch(f"{MODULE}.StrategyModel.objects")
    def test_prepare_file_filters_by_biz(self, strategy_objects, item_objects, query_config_objects, collect_objects):
        strategy_objects.filter.return_value = [SimpleNamespace(id=1)]
        item_objects.filter.return_value = [SimpleNamespace(id=11)]
        query_config_objects.filter.return_value = [
            SimpleNamespace(config={"agg_condition": [{"key": "bk_collect_config_id", "value": ["7"]}]})
        ]
        collect_objects.filter.return_value = [SimpleNamespace(plugin_id="p1")]
        resource = ExportPackageResource()
        resource.bk_biz_id = 2
        resource.strategy_config_ids = [1, 9]
        resource.collect_config_ids = [5]

        resource.prepare_file()

        strategy_objects.filter.assert_called_once_with(id__in=[1, 9], bk_biz_id=2)
        collect_kwargs = collect_objects.filter.call_args[1]
        self.assertEqual(set(collect_kwargs["id__in"]), {5, "7"})
        self.assertEqual(collect_kwargs["bk_biz_id"], 2)
        self.assertEqual(resource.associated_plugin_list, ["p1"])

    @mock.patch(f"{MODULE}.CollectConfigMeta.objects")
    def test_make_collect_config_filters_by_biz(self, collect_objects):
        config = SimpleNamespace(
            id=5,
            name="c",
            bk_biz_id=2,
            collect_type="Script",
            label="os",
            target_object_type=TargetObjectType.HOST,
            deployment_config=SimpleNamespace(
                target_node_type="TOPO",
                target_nodes=[],
                params={},
                plugin_version=SimpleNamespace(plugin_id="p1"),
                subscription_id=1,
            ),
            label_info={},
        )
        collect_objects.select_related.return_value.filter.return_value = [config]
        resource = ExportPackageResource()
        resource.bk_biz_id = 2
        resource.collect_config_ids = [5]
        resource.associated_collect_config_list = ["7"]

        with tempfile.TemporaryDirectory() as package_path:
            resource.package_path = package_path
            resource.make_collect_config()
            files = os.listdir(os.path.join(package_path, "collect_config_directory"))

        filter_kwargs = collect_objects.select_related.return_value.filter.call_args[1]
        self.assertEqual(set(filter_kwargs["id__in"]), {5, "7"})
        self.assertEqual(filter_kwargs["bk_biz_id"], 2)
        self.assertEqual(files, ["c_5.json"])


class TestAddMonitorTargetBizScope(TestCase):
    target = [[{"field": TargetFieldType.host_topo, "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}]}]]

    def params(self):
        return {"bk_biz_id": 2, "import_history_id": 1, "target": self.target}

    @mock.patch(f"{MODULE}.ImportHistory.objects")
    @mock.patch(f"{MODULE}.Permission")
    def test_checks_biz_permission_before_loading_history(self, permission_cls, history_objects):
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            AddMonitorTargetResource().perform_request(self.params())

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            2, ActionEnum.IMPORT_CONFIG, raise_exception=True
        )
        history_objects.filter.assert_not_called()

    @mock.patch(f"{MODULE}.ImportHistory.objects")
    @mock.patch(f"{MODULE}.Permission")
    def test_history_of_other_biz_not_found(self, permission_cls, history_objects):
        history_objects.filter.return_value.first.return_value = None

        with self.assertRaises(ImportHistoryNotExistError):
            AddMonitorTargetResource().perform_request(self.params())
        history_objects.filter.assert_called_once_with(id=1, bk_biz_id=2)

    @mock.patch(f"{MODULE}.StrategyModel.objects")
    @mock.patch(f"{MODULE}.resource")
    @mock.patch(f"{MODULE}.CollectConfigMeta.objects")
    @mock.patch(f"{MODULE}.ImportDetail.objects")
    @mock.patch(f"{MODULE}.ImportHistory.objects")
    @mock.patch(f"{MODULE}.Permission")
    def test_enable_strategies_limited_to_biz(
        self, permission_cls, history_objects, detail_objects, collect_objects, resource, strategy_objects
    ):
        history_objects.filter.return_value.first.return_value.get_target_type.return_value = {
            "target_type": TargetObjectType.HOST
        }
        detail_objects.filter.side_effect = lambda **kwargs: (
            [SimpleNamespace(config_id="11")] if kwargs["type"] == ConfigType.STRATEGY else []
        )
        collect_objects.filter.return_value = []

        self.assertEqual(AddMonitorTargetResource().perform_request(self.params()), "success")

        resource.strategies.bulk_edit_strategy.assert_called_once_with(
            bk_biz_id=2, id_list=[11], edit_data={"target": self.target}
        )
        strategy_objects.filter.assert_called_once_with(id__in=[11], bk_biz_id=2)
        strategy_objects.filter.return_value.update.assert_called_once_with(is_enabled=True)
