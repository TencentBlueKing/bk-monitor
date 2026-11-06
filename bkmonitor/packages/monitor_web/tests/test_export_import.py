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
from constants.action import GLOBAL_BIZ_ID, ActionPluginType
from constants.strategy import TargetFieldType
from core.errors.export_import import ExportImportError
from monitor_web.export_import.constant import ImportDetailStatus
from monitor_web.export_import.import_config import import_strategy
from monitor_web.export_import.resources import ExportPackageResource, GetAllConfigListResource


@pytest.fixture
def export_config_list_data():
    target_nodes = [{"bk_obj_id": "module", "bk_inst_id": 3}]
    collect = SimpleNamespace(
        id=1,
        bk_biz_id=2,
        name="demo collection",
        plugin_id="demo_plugin",
        deployment_config=SimpleNamespace(target_nodes=target_nodes, target_node_type="TOPO", config_meta_id=1),
    )
    strategy = SimpleNamespace(id=2, name="demo strategy")
    item = SimpleNamespace(
        id=3,
        strategy_id=2,
        target=[[{"field": TargetFieldType.host_topo, "value": target_nodes}]],
    )
    collect_queryset = mock.MagicMock()
    collect_queryset.__iter__.side_effect = lambda: iter([collect])
    collect_queryset.filter.return_value = collect_queryset
    collect_queryset.select_related.return_value = collect_queryset
    strategy_queryset = mock.MagicMock()
    strategy_queryset.__iter__.side_effect = lambda: iter([strategy])
    strategy_queryset.filter.return_value = strategy_queryset
    with (
        mock.patch(
            "monitor_web.export_import.resources.CollectConfigMeta.objects.filter", return_value=collect_queryset
        ),
        mock.patch("monitor_web.export_import.resources.StrategyModel.objects.filter", return_value=strategy_queryset),
        mock.patch("monitor_web.export_import.resources.ItemModel.objects.filter", return_value=[item]),
        mock.patch("monitor_web.export_import.resources.QueryConfigModel.objects.filter", return_value=[]),
        mock.patch(
            "monitor_web.export_import.resources.resource.grafana.get_dashboard_list",
            return_value=[{"uid": "demo", "name": "demo dashboard"}],
        ),
    ):
        yield collect_queryset, strategy_queryset, item


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"search_value": "demo"},
        {"label": "os"},
        {"cmdb_node": "module|3"},
        {"cmdb_node": "module|3", "search_value": "demo", "label": "os"},
        {"service_category_id": 0},
    ],
)
def test_export_config_list_without_category_skips_unavailable_cmdb(export_config_list_data, filters):
    with mock.patch(
        "monitor_web.export_import.resources.CmdbUtil", side_effect=RuntimeError("CMDB unavailable")
    ) as cmdb:
        result = GetAllConfigListResource().request({"bk_biz_id": 2, **filters})

    cmdb.assert_not_called()
    assert result == {
        "collect_config_list": [{"id": 1, "name": "demo collection", "dependency_plugin": "demo_plugin"}],
        "strategy_config_list": [{"id": 2, "name": "demo strategy", "dependency_collect_config": ""}],
        "view_config_list": [{"id": "demo", "name": "demo dashboard", "dependency_collect_config": []}],
    }


@pytest.mark.parametrize("target_field", [TargetFieldType.host_topo, TargetFieldType.service_topo])
@pytest.mark.parametrize("matches_category", [True, False])
def test_export_config_list_filters_by_service_category(export_config_list_data, target_field, matches_category):
    collect_queryset, strategy_queryset, item = export_config_list_data
    item.target[0][0]["field"] = target_field
    if not matches_category:
        collect_queryset.filter.return_value = []
        strategy_queryset.filter.return_value = []

    with mock.patch("monitor_web.export_import.resources.CmdbUtil") as cmdb:
        cmdb.return_value.get_category_list.return_value = [7] if matches_category else [8]
        result = GetAllConfigListResource().request({"bk_biz_id": 2, "service_category_id": 7})

    cmdb.assert_called_once_with(2)
    assert cmdb.return_value.get_category_list.call_args_list == [
        mock.call(2, [{"bk_obj_id": "module", "bk_inst_id": 3}]),
        mock.call(2, [{"bk_obj_id": "module", "bk_inst_id": 3}]),
    ]
    collect_queryset.filter.assert_called_once_with(id__in=[1] if matches_category else [])
    strategy_queryset.filter.assert_called_once_with(id__in=[2] if matches_category else [])
    assert [config["id"] for config in result["collect_config_list"]] == ([1] if matches_category else [])
    assert [config["id"] for config in result["strategy_config_list"]] == ([2] if matches_category else [])
    assert result["view_config_list"] == [{"id": "demo", "name": "demo dashboard", "dependency_collect_config": []}]


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


def _ensure_webhook_plugin():
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


def _import_strategy_with_action(action_config, *, is_overwrite_mode=False, save_strategy_id=1):
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
    ):
        save_strategy.return_value = {"id": save_strategy_id} if save_strategy_id else {}
        import_strategy(2, SimpleNamespace(id=1), [import_record], is_overwrite_mode=is_overwrite_mode)
    return import_record


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("is_overwrite_mode", [False, True])
def test_import_strategy_renames_action_colliding_with_global_builtin(is_overwrite_mode):
    _ensure_webhook_plugin()
    builtin_name = "「快捷」自动授权uwork处理"
    ActionConfig.objects.create(
        **{
            **_action_config(timeout=600),
            "name": builtin_name,
            "bk_biz_id": GLOBAL_BIZ_ID,
            "is_builtin": True,
        }
    )
    imported = _action_config(timeout=600)
    imported["name"] = builtin_name

    import_record = _import_strategy_with_action(imported, is_overwrite_mode=is_overwrite_mode)

    assert import_record.import_status == ImportDetailStatus.SUCCESS
    assert ActionConfig.objects.filter(bk_biz_id=GLOBAL_BIZ_ID, name=builtin_name).exists()
    assert not ActionConfig.objects.filter(bk_biz_id=2, name=builtin_name).exists()
    assert ActionConfig.objects.filter(bk_biz_id=2, name=f"{builtin_name}_clone").exists()


@pytest.mark.django_db(databases="__all__")
def test_import_strategy_overwrite_still_updates_same_biz_action():
    _ensure_webhook_plugin()
    ActionConfig.objects.create(**_action_config(timeout=600))
    imported = _action_config(timeout=600)
    imported["desc"] = "updated by overwrite"

    import_record = _import_strategy_with_action(imported, is_overwrite_mode=True)

    assert import_record.import_status == ImportDetailStatus.SUCCESS
    action = ActionConfig.objects.get(bk_biz_id=2, name="HTTP callback")
    assert action.desc == "updated by overwrite"
    assert ActionConfig.objects.filter(bk_biz_id=2, name="HTTP callback").count() == 1


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
