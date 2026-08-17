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

from bkmonitor.models import ActionConfig, ActionPlugin
from constants.action import ActionPluginType
from core.errors.export_import import ExportImportError
from monitor_web.export_import.constant import ImportDetailStatus
from monitor_web.export_import.import_config import import_strategy
from monitor_web.export_import.resources import ExportPackageResource


def _resource_with_strategy_condition(condition):
    resource = ExportPackageResource()
    resource.bk_biz_id = 2
    resource.strategy_config_ids = [1]

    strategy = SimpleNamespace(id=1, name="test_strategy")
    item = SimpleNamespace(id=2)
    query_config = SimpleNamespace(config={"agg_condition": [condition]})
    return resource, strategy, item, query_config


def _action_config(timeout):
    return {
        "name": "HTTP callback",
        "plugin_id": 2,
        "bk_biz_id": 2,
        "desc": "",
        "execute_config": {
            "template_detail": {
                "method": "POST",
                "url": "https://example.com",
                "headers": [],
                "authorize": {"auth_type": "none"},
                "body": {"data_type": "raw", "params": [], "content": "", "content_type": "json"},
                "query_params": [],
            },
            "timeout": timeout,
        },
    }


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("is_overwrite_mode", [False, True])
def test_import_strategy_rejects_action_timeout_over_limit(is_overwrite_mode):
    ActionPlugin.objects.update_or_create(
        id=2,
        defaults={
            "name": "HTTP callback",
            "plugin_type": ActionPluginType.WEBHOOK,
            "plugin_key": ActionPluginType.WEBHOOK,
            "category": "",
            "config_schema": {},
            "backend_config": {},
        },
    )
    if is_overwrite_mode:
        ActionConfig.objects.create(**_action_config(timeout=600))

    parse_instance = SimpleNamespace(
        config={
            "name": "strategy",
            "actions": [{"config": _action_config(timeout=7201)}],
            "notice": {"user_group_list": []},
            "items": [{"query_configs": []}],
        }
    )
    import_record = SimpleNamespace(parse_id=1, save=mock.Mock())

    with (
        mock.patch("monitor_web.export_import.import_config.ImportParse.objects.get", return_value=parse_instance),
        mock.patch("monitor_web.export_import.import_config.resource.strategies.save_strategy_v2") as save_strategy,
    ):
        save_strategy.return_value = {}
        import_strategy(2, SimpleNamespace(id=1), [import_record], is_overwrite_mode=is_overwrite_mode)

    assert import_record.import_status == ImportDetailStatus.FAILED
    assert all(config.execute_config.get("timeout") != 7201 for config in ActionConfig.objects.all())
    if is_overwrite_mode:
        assert ActionConfig.objects.get(name="HTTP callback").execute_config["timeout"] == 600
    save_strategy.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_import_strategy_timeout_validation_does_not_request_plugin_detail():
    ActionPlugin.objects.update_or_create(
        id=3,
        defaults={
            "name": "SOPS",
            "plugin_type": ActionPluginType.SOPS,
            "plugin_key": ActionPluginType.SOPS,
            "category": "",
            "config_schema": {},
            "backend_config": {},
        },
    )
    action_config = _action_config(timeout=7200)
    action_config["name"] = "SOPS"
    action_config["plugin_id"] = 3
    action_config["execute_config"]["template_id"] = "template-id"
    parse_instance = SimpleNamespace(
        config={
            "name": "strategy",
            "actions": [{"config": action_config}],
            "notice": {"user_group_list": []},
            "items": [{"query_configs": []}],
        }
    )
    import_record = SimpleNamespace(parse_id=1, save=mock.Mock())

    with (
        mock.patch("monitor_web.export_import.import_config.ImportParse.objects.get", return_value=parse_instance),
        mock.patch("monitor_web.export_import.import_config.resource.strategies.save_strategy_v2") as save_strategy,
        mock.patch.object(ActionPlugin, "perform_resource_request", return_value=[]) as request_plugin_detail,
    ):
        save_strategy.return_value = {"id": 1}
        import_strategy(2, SimpleNamespace(id=1), [import_record])

    assert import_record.import_status == ImportDetailStatus.SUCCESS
    request_plugin_detail.assert_not_called()


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
