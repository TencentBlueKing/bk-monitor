"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from core.errors.export_import import ExportImportError
from monitor_web.export_import.resources import ExportPackageResource


def _resource_with_strategy_condition(condition):
    resource = ExportPackageResource()
    resource.bk_biz_id = 2
    resource.strategy_config_ids = [1]

    strategy = SimpleNamespace(id=1, name="test_strategy")
    item = SimpleNamespace(id=2)
    query_config = SimpleNamespace(config={"agg_condition": [condition]})
    return resource, strategy, item, query_config


@pytest.mark.parametrize("invalid_value", ["invalid-id", "²"])
def test_prepare_file_reports_invalid_collect_config_id_value(invalid_value):
    resource, strategy, item, query_config = _resource_with_strategy_condition(
        {"key": "bk_collect_config_id", "method": "eq", "value": [invalid_value]}
    )

    with (
        mock.patch("monitor_web.export_import.resources.StrategyModel.objects.filter", return_value=[strategy]),
        mock.patch("monitor_web.export_import.resources.ItemModel.objects.filter", return_value=[item]),
        mock.patch("monitor_web.export_import.resources.QueryConfigModel.objects.filter", return_value=[query_config]),
        mock.patch("monitor_web.export_import.resources.CollectConfigMeta.objects.filter") as collect_config_filter,
    ):
        collect_config_filter.side_effect = ValueError(f"invalid literal for int() with base 10: '{invalid_value}'")

        with pytest.raises(ExportImportError) as error:
            resource.prepare_file()

    assert str(error.value) == (
        "导入导出模块错误：策略「test_strategy」(ID: 1)的条件字段「bk_collect_config_id」期望为数字采集配置ID，"
        f"实际值为「{invalid_value}」，无法查询关联采集配置"
    )
    collect_config_filter.assert_not_called()


def test_prepare_file_reports_invalid_scalar_collect_config_id_value():
    resource, strategy, item, query_config = _resource_with_strategy_condition(
        {"key": "bk_collect_config_id", "method": "eq", "value": None}
    )

    with (
        mock.patch("monitor_web.export_import.resources.StrategyModel.objects.filter", return_value=[strategy]),
        mock.patch("monitor_web.export_import.resources.ItemModel.objects.filter", return_value=[item]),
        mock.patch("monitor_web.export_import.resources.QueryConfigModel.objects.filter", return_value=[query_config]),
        mock.patch("monitor_web.export_import.resources.CollectConfigMeta.objects.filter") as collect_config_filter,
    ):
        with pytest.raises(ExportImportError) as error:
            resource.prepare_file()

    assert str(error.value) == (
        "导入导出模块错误：策略「test_strategy」(ID: 1)的条件字段「bk_collect_config_id」期望为数字采集配置ID，"
        "实际值为「None」，无法查询关联采集配置"
    )
    collect_config_filter.assert_not_called()


def test_prepare_file_keeps_ignoring_empty_collect_config_id_value():
    resource, strategy, item, query_config = _resource_with_strategy_condition(
        {"key": "bk_collect_config_id", "method": "neq", "value": [""]}
    )

    with (
        mock.patch("monitor_web.export_import.resources.StrategyModel.objects.filter", return_value=[strategy]),
        mock.patch("monitor_web.export_import.resources.ItemModel.objects.filter", return_value=[item]),
        mock.patch("monitor_web.export_import.resources.QueryConfigModel.objects.filter", return_value=[query_config]),
        mock.patch(
            "monitor_web.export_import.resources.CollectConfigMeta.objects.filter", return_value=[]
        ) as filter_mock,
    ):
        resource.prepare_file()

    assert resource.associated_collect_config_list == []
    assert filter_mock.call_args.kwargs["id__in"] == []


@pytest.mark.parametrize(
    ("condition_value", "expected_ids"),
    [
        (["100", "200"], {"100", "200"}),
        ("100(test_collect_config)", {"100"}),
    ],
)
def test_prepare_file_keeps_supported_collect_config_ids(condition_value, expected_ids):
    resource, strategy, item, query_config = _resource_with_strategy_condition(
        {"key": "bk_collect_config_id", "method": "eq", "value": condition_value}
    )

    with (
        mock.patch("monitor_web.export_import.resources.StrategyModel.objects.filter", return_value=[strategy]),
        mock.patch("monitor_web.export_import.resources.ItemModel.objects.filter", return_value=[item]),
        mock.patch("monitor_web.export_import.resources.QueryConfigModel.objects.filter", return_value=[query_config]),
        mock.patch(
            "monitor_web.export_import.resources.CollectConfigMeta.objects.filter", return_value=[]
        ) as filter_mock,
    ):
        resource.prepare_file()

    assert set(resource.associated_collect_config_list) == expected_ids
    assert set(filter_mock.call_args.kwargs["id__in"]) == expected_ids
