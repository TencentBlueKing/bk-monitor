"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import json
import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from django.utils.translation import gettext_lazy

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.kernel_rpc import KernelRPCResource
from kernel_api.rpc.functions.admin.api_auth_token import (
    _normalize_biz_ids,
    _normalize_namespaces,
    _serialize_api_auth_token,
)
from kernel_api.rpc.functions.admin import apm as admin_apm
from kernel_api.rpc.functions.admin import bcs_cluster as admin_bcs_cluster
from kernel_api.rpc.functions.admin import cluster_info as admin_cluster_info
from kernel_api.rpc.functions.admin import collect_config as admin_collect_config
from kernel_api.rpc.functions.admin import collect_plugin as admin_collect_plugin
from kernel_api.rpc.functions.admin import config_delivery as admin_config_delivery
from kernel_api.rpc.functions.admin import custom_report as admin_custom_report
from kernel_api.rpc.functions.admin.bcs_cluster import _serialize_bcs_cluster
from kernel_api.rpc.functions.admin.cluster_info import (
    _build_es_cluster_overview,
    _build_es_analysis_storage_index,
    _build_es_analysis_storage_queryset,
    _parse_es_analysis_index_base,
    _parse_es_analysis_owner,
    _serialize_es_analysis_index_row,
    _serialize_cluster_info,
    _serialize_cluster_space_vm_info,
)
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin.datasource import _serialize_datasource
from kernel_api.rpc.functions.admin import datalink as admin_datalink
from kernel_api.rpc.functions.admin import es_storage as admin_es_storage
from kernel_api.rpc.functions.admin.datalink import (
    get_component_detail,
    get_datalink_component_config,
    list_components,
)
from kernel_api.rpc.functions.admin.es_storage import (
    _build_runtime_index_item,
    _contains_index_wildcard,
    _is_virtual_es_storage,
    _serialize_es_storage_config,
    _table_kind,
)
from kernel_api.rpc.functions.admin.query_route import (
    _format_filter_groups,
    _normalize_string_list,
    _resolve_space_identity,
)
from kernel_api.rpc.functions.admin.result_table import _serialize_result_table_detail
from kernel_api.rpc.functions.admin.render_image_task import _serialize_render_image_task
from kernel_api.rpc.functions.admin import space as admin_space
from kernel_api.rpc.functions.admin import kafka_sample as kafka_sample_module
from kernel_api.rpc.functions.admin import storage as admin_storage
from kernel_api.rpc.functions.admin.storage import (
    _build_doris_relations,
    get_doris_storage_latest_records,
    get_doris_storage_physical_metadata,
    _serialize_bkbase_item,
    _serialize_doris_storage,
)
from kernel_api.rpc.functions.admin.storage_cluster_history import (
    clone_storage_with_runtime_cluster,
    resolve_runtime_storage_cluster,
    resolve_storage_history_table_id,
    serialize_storage_cluster_record,
)
from kernel_api.rpc.functions.admin.uptime_check import _build_subscription_detail_payload, _summarize_subscription
from kernel_api.rpc.registry import KernelRPCRegistry
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import PluginType


def _doris_storage_manager():
    return admin_storage.models.DorisStorage.objects


class _FakeQuerySet:
    def __init__(self, items):
        self.items = list(items)
        self.filters = []
        self.excludes = []
        self.ordering = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def exclude(self, **kwargs):
        self.excludes.append(kwargs)
        return self

    def order_by(self, *fields):
        self.ordering.append(fields)
        return self

    def count(self):
        return len(self.items)

    def __getitem__(self, key):
        return self.items[key]


def test_admin_rpc_functions_registered_by_builtin_loader():
    func_names = {function["func_name"] for function in KernelRPCRegistry.list_functions()}

    assert {
        "admin.datasource.list",
        "admin.datasource.detail",
        "admin.space.list",
        "admin.space.detail",
        "admin.space.es_usage",
        "admin.result_table.list",
        "admin.result_table.detail",
        "admin.result_table.field_list",
        "admin.result_table.field_options",
        "admin.cluster_info.list",
        "admin.cluster_info.detail",
        "admin.cluster_info.space_vm_info_list",
        "admin.cluster_info.es_overview",
        "admin.cluster_info.es_storage_analysis",
        "admin.cluster_info.health_check",
        "admin.bcs_cluster.list",
        "admin.bcs_cluster.detail",
        "admin.bcs_cluster.data_id_list",
        "admin.bcs_cluster.data_id_detail",
        "admin.bcs_cluster.bk_collector_config_list",
        "admin.bcs_cluster.bk_collector_config_detail",
        "admin.bcs_cluster.bkmonitor_operator_release_list",
        "admin.bcs_cluster.bkmonitor_operator_release_detail",
        "admin.datasource.kafka_sample",
        "admin.es_storage.list",
        "admin.es_storage.detail",
        "admin.es_storage.runtime_overview",
        "admin.es_storage.sample",
        "admin.es_storage.rotate_aliases",
        "admin.query_route.query",
        "admin.query_route.refresh",
        "admin.doris_storage.list",
        "admin.doris_storage.detail",
        "admin.doris_storage.physical_metadata",
        "admin.doris_storage.latest_records",
        "admin.vm_storage.list",
        "admin.vm_storage.detail",
        "admin.kafka_storage.list",
        "admin.kafka_storage.detail",
        "admin.bkbase_result_table.list",
        "admin.bkbase_result_table.detail",
        "admin.custom_report.list",
        "admin.custom_report.detail",
        "admin.custom_report.scope_list",
        "admin.custom_report.metric_list",
        "admin.custom_report.refresh_metrics",
        "admin.api_auth_token.list",
        "admin.api_auth_token.detail",
        "admin.api_auth_token.create",
        "admin.api_auth_token.update",
        "admin.api_auth_token.delete",
        "admin.uptime_check.node_list",
        "admin.uptime_check.node_detail",
        "admin.uptime_check.task_list",
        "admin.uptime_check.task_detail",
        "admin.uptime_check.subscription_detail",
        "admin.config_delivery.runtime_settings",
        "admin.config_delivery.proxy_list",
        "admin.config_delivery.ping_server_list",
        "admin.config_delivery.ping_server_detail",
        "admin.config_delivery.custom_report_list",
        "admin.config_delivery.custom_report_detail",
        "admin.config_delivery.log_subscription_list",
        "admin.config_delivery.log_subscription_detail",
        "admin.config_delivery.apm_subscription_list",
        "admin.config_delivery.apm_subscription_detail",
        "admin.config_delivery.subscription_detail",
        "admin.config_delivery.batch_status",
        "admin.collect_plugin.list",
        "admin.collect_plugin.detail",
        "admin.collect_plugin.version_list",
        "admin.collect_plugin.version_detail",
        "admin.collect_config.list",
        "admin.collect_config.detail",
        "admin.collect_config.version_list",
        "admin.collect_config.version_detail",
        "admin.collect_config.target_status",
        "admin.collect_config.subscription_detail",
        "admin.render_image_task.list",
        "admin.render_image_task.detail",
        "admin.token.resolve",
    } <= func_names

    detail = KernelRPCRegistry.get_function_detail("admin.result_table.detail")
    assert detail is not None
    assert detail["params_schema"]["include"].find("fields") != -1

    space_detail = KernelRPCRegistry.get_function_detail("admin.space.detail")
    assert space_detail is not None
    assert "SpaceVMInfo" in space_detail["description"]

    space_list = KernelRPCRegistry.get_function_detail("admin.space.list")
    assert space_list is not None
    assert "bk_biz_id" in space_list["params_schema"]

    custom_report_list = KernelRPCRegistry.get_function_detail("admin.custom_report.list")
    assert custom_report_list is not None
    assert "bk_data_ids" in custom_report_list["params_schema"]

    apm_application_list = KernelRPCRegistry.get_function_detail("admin.apm.application_list")
    assert apm_application_list is not None
    assert "application_ids" in apm_application_list["params_schema"]

    config_delivery_batch_status = KernelRPCRegistry.get_function_detail("admin.config_delivery.batch_status")
    assert config_delivery_batch_status is not None
    assert "subscription_ids" in config_delivery_batch_status["params_schema"]

    config_delivery_proxy_list = KernelRPCRegistry.get_function_detail("admin.config_delivery.proxy_list")
    assert config_delivery_proxy_list is not None
    assert "bk_biz_id" in config_delivery_proxy_list["params_schema"]

    collect_plugin_detail = KernelRPCRegistry.get_function_detail("admin.collect_plugin.detail")
    assert collect_plugin_detail is not None
    assert "plugin_id" in collect_plugin_detail["params_schema"]

    collect_config_target_status = KernelRPCRegistry.get_function_detail("admin.collect_config.target_status")
    assert collect_config_target_status is not None
    assert "diff" in collect_config_target_status["params_schema"]

    collect_config_version_detail = KernelRPCRegistry.get_function_detail("admin.collect_config.version_detail")
    assert collect_config_version_detail is not None
    assert "deployment_id" in collect_config_version_detail["params_schema"]


def test_collect_plugin_version_detail_marks_process_special_design():
    plugin = CollectorPluginMeta(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        plugin_type=PluginType.PROCESS,
        bk_biz_id=0,
        tag="主机",
        label="host_process",
    )
    config = CollectorPluginConfig(
        collector_json={"linux": {"file_id": "bkmonitorbeat"}},
        config_json=[{"key": "match_pattern", "default": "gunicorn.*app"}],
        is_support_remote=False,
    )
    info = CollectorPluginInfo(
        plugin_display_name="进程采集",
        metric_json=[{"table_name": "process.perf", "fields": [{"name": "cpu_usage", "monitor_type": "metric"}]}],
    )
    version = PluginVersionHistory(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        stage=PluginVersionHistory.Stage.RELEASE,
        config=config,
        info=info,
        config_version=1,
        info_version=1,
        is_packaged=True,
    )

    detail = admin_collect_plugin._serialize_version_detail(version, plugin)

    assert detail["plugin_display_name"] == "进程采集"
    assert detail["special_design"]["kind"] == "process"
    assert detail["metric_json"][0]["table_id"] == "process.process.perf"


def test_collect_config_summary_keeps_version_and_subscription_context(monkeypatch):
    plugin = CollectorPluginMeta(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        plugin_type=PluginType.PROCESS,
        bk_biz_id=0,
        label="host_process",
    )
    config_definition = CollectorPluginConfig(collector_json={}, config_json=[], is_support_remote=False)
    info = CollectorPluginInfo(plugin_display_name="进程采集", metric_json=[])
    version = PluginVersionHistory(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        stage=PluginVersionHistory.Stage.RELEASE,
        config=config_definition,
        info=info,
        config_version=1,
        info_version=1,
        is_packaged=True,
    )
    deployment = DeploymentConfigVersion(
        plugin_version=version,
        subscription_id=82002,
        target_node_type="INSTANCE",
        params={"collector": {"period": 60}},
        target_nodes=[{"ip": "127.0.0.1", "bk_cloud_id": 0}],
    )
    collect_config = CollectConfigMeta(
        id=202,
        bk_tenant_id="system",
        bk_biz_id=2,
        name="业务进程存活",
        collect_type=PluginType.PROCESS,
        plugin_id="bkprocessbeat",
        target_object_type="HOST",
        deployment_config=deployment,
        cache_data={"error_instance_count": 1, "total_instance_count": 3},
        last_operation="START",
        operation_result="SUCCESS",
        label="host_process",
    )

    monkeypatch.setattr(admin_collect_config, "_get_plugin_for_config", lambda _config: plugin)
    monkeypatch.setattr(admin_collect_config, "_latest_plugin_version", lambda _plugin: version)

    summary = admin_collect_config._serialize_collect_config_summary(collect_config)
    detail = admin_collect_config._serialize_collect_config_detail(collect_config)
    deployment_detail = admin_collect_config._serialize_deployment_version_detail(collect_config, deployment)

    assert summary["subscription_id"] == 82002
    assert summary["config_version"] == 1
    assert summary["task_status"] == "WARNING"
    assert detail["subscription_summary"]["scope_summary"]["nodes_count"] == 1
    assert detail["plugin_info"]["special_design"]["kind"] == "process"
    assert deployment_detail["config_id"] == 202
    assert deployment_detail["params"]["collector"]["period"] == 60
    assert deployment_detail["plugin_info"]["config_version"] == 1


def test_collect_config_summary_uses_injected_plugin_context(monkeypatch):
    plugin = CollectorPluginMeta(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        plugin_type=PluginType.PROCESS,
        bk_biz_id=0,
        label="host_process",
    )
    current_config_definition = CollectorPluginConfig(collector_json={}, config_json=[], is_support_remote=False)
    latest_config_definition = CollectorPluginConfig(collector_json={}, config_json=[], is_support_remote=False)
    current_info = CollectorPluginInfo(plugin_display_name="进程采集", metric_json=[])
    latest_info = CollectorPluginInfo(plugin_display_name="进程采集", metric_json=[])
    current_version = PluginVersionHistory(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        stage=PluginVersionHistory.Stage.RELEASE,
        config=current_config_definition,
        info=current_info,
        config_version=1,
        info_version=1,
        is_packaged=True,
    )
    latest_version = PluginVersionHistory(
        bk_tenant_id="system",
        plugin_id="bkprocessbeat",
        stage=PluginVersionHistory.Stage.RELEASE,
        config=latest_config_definition,
        info=latest_info,
        config_version=2,
        info_version=1,
        is_packaged=True,
    )
    deployment = DeploymentConfigVersion(
        plugin_version=current_version,
        subscription_id=82002,
        target_node_type="INSTANCE",
        params={"collector": {"period": 60}},
        target_nodes=[{"ip": "127.0.0.1", "bk_cloud_id": 0}],
    )
    collect_config = CollectConfigMeta(
        id=203,
        bk_tenant_id="system",
        bk_biz_id=2,
        name="业务进程存活",
        collect_type=PluginType.PROCESS,
        plugin_id="bkprocessbeat",
        target_object_type="HOST",
        deployment_config=deployment,
        cache_data={"error_instance_count": 0, "total_instance_count": 3},
        last_operation="START",
        operation_result="SUCCESS",
        label="host_process",
    )

    monkeypatch.setattr(
        admin_collect_config,
        "_get_plugin_for_config",
        Mock(side_effect=AssertionError("plugin should be provided by page context")),
    )
    monkeypatch.setattr(
        admin_collect_config,
        "_latest_plugin_version",
        Mock(side_effect=AssertionError("latest version should be provided by page context")),
    )

    summary = admin_collect_config._serialize_collect_config_summary(
        collect_config,
        plugin=plugin,
        latest_version=latest_version,
        upgrade_version=latest_version,
    )

    assert summary["latest_config_version"] == 2
    assert summary["latest_info_version"] == 1
    assert summary["need_upgrade"] is True


def test_admin_rpc_response_keeps_collect_config_detail_json_safe():
    result = build_response(
        operation="collect_config.detail",
        func_name=admin_collect_config.FUNC_COLLECT_CONFIG_DETAIL,
        bk_tenant_id="system",
        data={
            "config": {
                "label_info": gettext_lazy("其他"),
                "params": {"raw": b"log keyword"},
            }
        },
    )

    serializer = KernelRPCResource.ResponseSerializer(
        data={
            "func_name": admin_collect_config.FUNC_COLLECT_CONFIG_DETAIL,
            "protocol": "call",
            "result": result,
        }
    )

    serializer.is_valid(raise_exception=True)
    assert result["data"]["config"]["label_info"] == "其他"
    assert result["data"]["config"]["params"]["raw"] == "log keyword"


def test_config_delivery_ping_server_serializer_marks_disabled_flags(monkeypatch):
    monkeypatch.setattr(admin_config_delivery.settings, "ENABLE_PING_ALARM", False, raising=False)
    monkeypatch.setattr(admin_config_delivery.settings, "ENABLE_DIRECT_AREA_PING_COLLECT", False, raising=False)
    subscription = SimpleNamespace(
        subscription_id=1001,
        bk_tenant_id="system",
        bk_cloud_id=0,
        ip="127.0.0.1",
        bk_host_id=2001,
        bk_biz_id=19078,
        plugin_name="bkmonitorproxy",
        config={
            "type": "PLUGIN",
            "status": "STOP",
            "config": {
                "plugin_name": "bkmonitorproxy",
                "config_templates": [{"name": "bkmonitorproxy_ping.conf", "version": "latest"}],
            },
            "scope": {"nodes": [{"bk_host_id": 2001}]},
            "params": {
                "context": {
                    "ip_to_items": {
                        2001: [
                            {"target_biz_id": 11, "target_ip": "127.0.0.1", "target_cloud_id": 0},
                            {"target_biz_id": 12, "target_ip": "127.0.0.1", "target_cloud_id": 0},
                        ]
                    }
                }
            },
        },
    )

    item = admin_config_delivery._serialize_ping_server_config(subscription)

    assert item["bk_biz_id"] == 19078
    assert item["direct_area"] is True
    assert item["special_area"] is False
    assert item["global_ping_disabled"] is True
    assert item["direct_area_disabled"] is True
    assert item["collect_disabled"] is True
    assert item["target"]["node_count"] == 1
    assert item["target_count"] == 2
    assert item["target"]["ping_target_count"] == 2
    assert item["ping_target_summary"]["source_host_count"] == 1
    assert item["expected_status"] == "STOP"
    assert item["config_summary"]["plugin_names"] == ["bkmonitorproxy"]
    assert item["config_summary"]["template_names"] == ["bkmonitorproxy_ping.conf"]

    first_page = admin_config_delivery._paginate_ping_targets(subscription.config, page=1, page_size=1)
    assert first_page["total"] == 2
    assert first_page["source_host_count"] == 1
    assert first_page["items"] == [
        {
            "index": 1,
            "source_host_id": "2001",
            "target_biz_id": 11,
            "target_ip": "127.0.0.1",
            "target_cloud_id": 0,
        }
    ]

    second_page = admin_config_delivery._paginate_ping_targets(subscription.config, page=2, page_size=1)
    assert second_page["items"][0]["index"] == 2
    assert second_page["items"][0]["target_ip"] == "127.0.0.1"


def test_config_delivery_ping_server_queryset_filters_by_model_biz_id(monkeypatch):
    queryset = _FakeQuerySet([])
    monkeypatch.setattr(
        admin_config_delivery.PingServerSubscriptionConfig,
        "objects",
        SimpleNamespace(all=lambda: queryset),
    )

    result, warnings = admin_config_delivery._build_ping_server_queryset(
        {"bk_biz_id": 19078, "bk_cloud_id": 42}, "system"
    )

    assert result is queryset
    assert warnings == []
    assert {"bk_tenant_id": "system"} in queryset.filters
    assert {"bk_biz_id": 19078} in queryset.filters
    assert {"bk_cloud_id": 42} in queryset.filters
    assert ("bk_biz_id", "bk_cloud_id", "bk_host_id", "subscription_id") in queryset.ordering


def test_config_delivery_custom_report_serializer_keeps_default_tenant():
    subscription = SimpleNamespace(
        subscription_id=1002,
        bk_biz_id=0,
        bk_data_id=5001,
        config={
            "scope": {"nodes": [{"bk_host_id": 1}, {"bk_host_id": 2}]},
            "steps": [
                {
                    "config": {"plugin_name": "bk-collector"},
                    "params": {"context": {"bk_data_id": 5001, "password": "secret"}},
                }
            ],
        },
    )

    item = admin_config_delivery._serialize_custom_report_subscription(subscription)
    detail = admin_config_delivery._with_config_detail(item, subscription.config)

    assert item["bk_tenant_id"] == "system"
    assert item["data_id_consistent"] is True
    assert item["target"]["node_count"] == 2
    assert detail["config_detail"]["steps"][0]["params"]["context"]["password"] == "***"


def test_config_delivery_log_subscription_serializer_extracts_log_context():
    subscription = SimpleNamespace(
        subscription_id=1005,
        bk_tenant_id="system",
        bk_biz_id=2,
        log_name="checkout-log",
        config={
            "scope": {"nodes": [{"bk_host_id": 1}, {"bk_host_id": 2}]},
            "steps": [
                {
                    "config": {
                        "plugin_name": "bk-collector",
                        "config_templates": [{"name": "bk-collector-application.conf"}],
                    },
                    "params": {
                        "context": {
                            "bk_app_name": "checkout-log",
                            "log_data_id": 50020,
                            "bk_data_token": "secret-token",
                            "qps_config": {"qps": 1024},
                        }
                    },
                }
            ],
        },
    )

    item = admin_config_delivery._serialize_log_subscription(subscription)
    detail = admin_config_delivery._with_config_detail(item, subscription.config)

    assert item["source_type"] == "log_subscription"
    assert item["log_data_id"] == 50020
    assert item["bk_data_id"] == 50020
    assert item["qps"] == 1024
    assert item["has_token"] is True
    assert item["target_count"] == 2
    assert detail["config_detail"]["steps"][0]["params"]["context"]["bk_data_token"] == "***"


def test_config_delivery_apm_subscription_type_serializer():
    platform_subscription = SimpleNamespace(
        subscription_id=1003,
        bk_tenant_id="system",
        bk_biz_id=0,
        app_name="",
        config={"steps": [{"config": {"plugin_name": "bk-collector"}}]},
    )
    application_subscription = SimpleNamespace(
        subscription_id=1004,
        bk_tenant_id="system",
        bk_biz_id=2,
        app_name="checkout",
        config={"steps": [{"config": {"plugin_name": "bk-collector"}}]},
    )

    platform_item = admin_config_delivery._serialize_apm_subscription(platform_subscription)
    application_item = admin_config_delivery._serialize_apm_subscription(application_subscription)

    assert platform_item["subscription_type"] == "platform"
    assert platform_item["is_platform"] is True
    assert application_item["subscription_type"] == "application"
    assert application_item["is_platform"] is False


def test_config_delivery_apm_queryset_accepts_empty_app_name(monkeypatch):
    queryset = _FakeQuerySet([])
    monkeypatch.setattr(
        admin_config_delivery,
        "_apm_subscription_model",
        lambda: SimpleNamespace(objects=SimpleNamespace(all=lambda: queryset)),
    )

    admin_config_delivery._build_apm_subscription_queryset({"app_name": ""}, "system")

    assert {"bk_tenant_id": "system"} in queryset.filters
    assert {"app_name": ""} in queryset.filters


def test_config_delivery_proxy_related_configs_collects_four_config_types(monkeypatch):
    ping_subscription = SimpleNamespace(
        subscription_id=1001,
        bk_tenant_id="system",
        bk_cloud_id=30000901,
        ip="127.0.0.1",
        bk_host_id=70001,
        bk_biz_id=19078,
        plugin_name="bk-collector",
        config={"scope": {"nodes": [{"bk_host_id": 70001}]}, "steps": [{"config": {"plugin_name": "bk-collector"}}]},
    )
    custom_subscription = SimpleNamespace(
        subscription_id=1002,
        bk_biz_id=19078,
        bk_data_id=5001,
        config={"scope": {"nodes": [{"bk_host_id": 70001}]}, "steps": [{"config": {"plugin_name": "bk-collector"}}]},
    )
    log_subscription = SimpleNamespace(
        subscription_id=1003,
        bk_tenant_id="system",
        bk_biz_id=19078,
        log_name="proxy-log",
        config={
            "scope": {"nodes": [{"bk_host_id": 70001}]},
            "steps": [{"config": {"plugin_name": "bk-collector"}, "params": {"context": {"log_data_id": 5002}}}],
        },
    )
    apm_subscription = SimpleNamespace(
        subscription_id=1004,
        bk_tenant_id="system",
        bk_biz_id=19078,
        app_name="checkout",
        config={"scope": {"nodes": [{"bk_host_id": 70001}]}, "steps": [{"config": {"plugin_name": "bk-collector"}}]},
    )

    monkeypatch.setattr(
        admin_config_delivery.PingServerSubscriptionConfig,
        "objects",
        SimpleNamespace(all=lambda: _FakeQuerySet([ping_subscription])),
    )
    monkeypatch.setattr(
        admin_config_delivery.CustomReportSubscription,
        "objects",
        SimpleNamespace(all=lambda: _FakeQuerySet([custom_subscription])),
    )
    monkeypatch.setattr(
        admin_config_delivery.LogSubscriptionConfig,
        "objects",
        SimpleNamespace(all=lambda: _FakeQuerySet([log_subscription])),
    )
    monkeypatch.setattr(
        admin_config_delivery,
        "_apm_subscription_model",
        lambda: SimpleNamespace(
            objects=SimpleNamespace(filter=lambda *args, **kwargs: _FakeQuerySet([apm_subscription]))
        ),
    )
    monkeypatch.setattr(admin_config_delivery, "_custom_report_biz_matches_tenant", lambda bk_biz_id, tenant_id: True)

    related, warnings = admin_config_delivery._build_proxy_related_configs(
        bk_tenant_id="system",
        bk_biz_id=19078,
        proxy={"bk_cloud_id": 30000901, "inner_ip": "127.0.0.1", "bk_biz_id": 19078},
        proxy_host_id=70001,
    )

    assert warnings == []
    assert related["ping_server"]["subscription_ids"] == [1001]
    assert related["custom_report"]["subscription_ids"] == [1002]
    assert related["log_subscription"]["subscription_ids"] == [1003]
    assert related["apm_subscription"]["subscription_ids"] == [1004]
    assert related["custom_report"]["items"][0]["relation"] == "target_host"


def test_apm_application_list_filters_by_application_ids(monkeypatch):
    class FakeApmApplicationQuerySet:
        def __init__(self, items):
            self.items = list(items)
            self.filters = []
            self.ordering = []

        def filter(self, **kwargs):
            self.filters.append(kwargs)
            if "bk_tenant_id" in kwargs:
                self.items = [item for item in self.items if item.bk_tenant_id == kwargs["bk_tenant_id"]]
            if "id__in" in kwargs:
                application_ids = set(kwargs["id__in"])
                self.items = [item for item in self.items if item.id in application_ids]
            if "bk_biz_id" in kwargs:
                self.items = [item for item in self.items if item.bk_biz_id == kwargs["bk_biz_id"]]
            if "app_name__icontains" in kwargs:
                keyword = kwargs["app_name__icontains"]
                self.items = [item for item in self.items if keyword in item.app_name]
            return self

        def order_by(self, *fields):
            self.ordering.append(fields)
            return self

        def none(self):
            self.items = []
            return self

        def count(self):
            return len(self.items)

        def __getitem__(self, key):
            return self.items[key]

    applications = [
        SimpleNamespace(
            id=1,
            app_name="checkout",
            app_alias="结算服务",
            bk_tenant_id="system",
            bk_biz_id=2,
            update_time=datetime(2026, 5, 28, 10, 0, 0),
        ),
        SimpleNamespace(
            id=2,
            app_name="payment",
            app_alias="支付服务",
            bk_tenant_id="system",
            bk_biz_id=2,
            update_time=datetime(2026, 5, 28, 11, 0, 0),
        ),
        SimpleNamespace(
            id=3,
            app_name="trace-demo",
            app_alias="链路示例",
            bk_tenant_id="system",
            bk_biz_id=3,
            update_time=datetime(2026, 5, 28, 12, 0, 0),
        ),
    ]
    queryset = FakeApmApplicationQuerySet(applications)
    monkeypatch.setattr(
        admin_apm.apm_models,
        "ApmApplication",
        SimpleNamespace(objects=SimpleNamespace(all=lambda: queryset)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_apm,
        "_load_apm_datasource_maps",
        lambda apps: {datasource_type: {} for datasource_type in admin_apm.DATASOURCE_TYPES},
    )
    monkeypatch.setattr(admin_apm, "_load_service_count_map", lambda apps: {})

    result = admin_apm.list_apm_applications(
        {"bk_tenant_id": "system", "application_ids": "2,3,2", "page": 1, "page_size": 20}
    )

    assert result["data"]["total"] == 2
    assert [item["application_id"] for item in result["data"]["items"]] == [2, 3]
    assert {"id__in": [2, 3]} in queryset.filters


def test_space_vm_info_serializer_includes_vm_cluster_or_null():
    space_vm_info = SimpleNamespace(
        id=1,
        space_type="bkcc",
        space_id="2",
        vm_cluster_id=10001,
        vm_retention_time="30d",
        status="normal",
        creator="admin",
        create_time=datetime(2026, 5, 27, 10, 0, 0),
        updater="admin",
        update_time=datetime(2026, 5, 27, 10, 5, 0),
    )
    cluster = SimpleNamespace(
        cluster_id=10001,
        cluster_name="vm-main",
        display_name="主 VM 集群",
        cluster_type="victoria_metrics",
    )

    item = admin_space._serialize_space_vm_info(space_vm_info, {10001: cluster})

    assert item["space_vm_info"]["space_type"] == "bkcc"
    assert item["space_vm_info"]["update_time"] == "2026-05-27 10:05:00"
    assert item["vm_cluster"] == {
        "cluster_id": 10001,
        "cluster_name": "vm-main",
        "display_name": "主 VM 集群",
        "cluster_type": "victoria_metrics",
    }

    missing_cluster_item = admin_space._serialize_space_vm_info(space_vm_info, {})
    assert missing_cluster_item["vm_cluster"] is None


def test_space_es_usage_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.space.es_usage")

    assert detail is not None
    assert detail["func_name"] == "admin.space.es_usage"
    assert "inspect" in detail["description"]
    assert "实体表" in detail["description"]
    assert "space_uid" in detail["params_schema"]


def test_space_es_usage_prefix_uses_biz_id_or_space_pk():
    cmdb_space = SimpleNamespace(space_type_id="bkcc", space_id="2", pk=20)
    custom_space = SimpleNamespace(space_type_id="bkci", space_id="demo-project", pk=4779)

    assert admin_space._build_space_es_usage_prefix(cmdb_space) == "2_"
    assert admin_space._build_space_es_usage_prefix(custom_space) == "space_4779_"


def test_space_list_filters_by_mapped_bk_biz_id():
    positive_queryset = _FakeQuerySet([])
    admin_space._apply_space_bk_biz_id_filter(positive_queryset, "2")

    assert positive_queryset.filters == [{"space_type_id": "bkcc", "space_id": "2"}]
    assert positive_queryset.excludes == []

    negative_queryset = _FakeQuerySet([])
    admin_space._apply_space_bk_biz_id_filter(negative_queryset, -4779)

    assert negative_queryset.filters == [{"id": 4779}]
    assert negative_queryset.excludes == [{"space_type_id": "bkcc"}]

    with pytest.raises(CustomException, match="bk_biz_id 必须是整数"):
        admin_space._apply_space_bk_biz_id_filter(_FakeQuerySet([]), "demo")


def test_space_es_usage_builds_exact_table_index_patterns():
    patterns = admin_space._build_es_usage_index_patterns(["2_bklog.demo", "space_4779_bklog.demo"])

    assert patterns == [
        "v2_2_bklog_demo_*",
        "2_bklog_demo_*",
        "v2_space_4779_bklog_demo_*",
        "space_4779_bklog_demo_*",
    ]


def test_space_es_usage_cluster_aggregates_physical_storage_rows():
    warnings = []
    cluster = SimpleNamespace(
        cluster_id=9,
        cluster_name="es-main",
        display_name="主 ES 集群",
        cluster_type="elasticsearch",
    )
    storages = [_fake_es_analysis_storage("2_bklog.demo"), _fake_es_analysis_storage("2_bklog.legacy")]
    index_rows = [
        {
            "index": "v2_2_bklog_demo_2026060612_0",
            "health": "green",
            "status": "open",
            "docs.count": "10",
            "store.size": "1024",
            "pri": "2",
            "rep": "1",
        },
        {
            "index": "2_bklog_legacy_2026060612_0",
            "health": "yellow",
            "status": "open",
            "docs.count": "5",
            "store.size": "512",
            "pri": "1",
            "rep": "0",
        },
    ]

    payload = admin_space._build_space_es_usage_cluster(
        cluster=cluster,
        es_storages=storages,
        result_table_map={},
        index_rows=index_rows,
        current_table_ids={"2_bklog.demo"},
        historical_table_ids={"2_bklog.legacy"},
        historical_cluster_ids_by_table={"2_bklog.legacy": {9}},
        warnings=warnings,
    )

    storages_by_table = {storage["table_id"]: storage for storage in payload["storages"]}
    assert warnings == []
    assert "role" not in payload
    assert payload["summary"]["storage_count"] == 2
    assert payload["summary"]["index_count"] == 2
    assert payload["summary"]["docs_count"] == 15
    assert payload["summary"]["store_size_bytes"] == 1536
    assert payload["summary"]["shards"] == 5
    assert payload["summary"]["health_counts"] == {"green": 1, "yellow": 1}
    assert storages_by_table["2_bklog.demo"]["role"] == "current"
    assert storages_by_table["2_bklog.demo"]["summary"]["index_count"] == 1
    assert storages_by_table["2_bklog.legacy"]["role"] == "historical"
    assert storages_by_table["2_bklog.legacy"]["historical_cluster_ids"] == [9]


def test_space_es_usage_query_skips_failed_chunks_without_fallback(monkeypatch):
    calls = []

    class FakeCat:
        def indices(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("es unavailable")

    monkeypatch.setattr(
        admin_space.es_tools,
        "get_client",
        lambda bk_tenant_id, cluster_id: SimpleNamespace(cat=FakeCat()),
    )
    warnings = []

    rows = admin_space._query_es_usage_index_rows(
        bk_tenant_id="system",
        cluster_id=9,
        table_ids=["2_bklog.demo"],
        timeout=30,
        warnings=warnings,
    )

    assert rows == []
    assert warnings[0]["code"] == "SPACE_ES_USAGE_INDEX_QUERY_FAILED"
    assert calls[0]["index"] == "v2_2_bklog_demo_*,2_bklog_demo_*"
    assert calls[0]["index"] != "*"


def test_cluster_space_vm_info_serializer_includes_space_summary_or_null():
    space_vm_info = SimpleNamespace(
        id=1,
        space_type="bkcc",
        space_id="2",
        vm_cluster_id=10001,
        vm_retention_time="30d",
        status="normal",
        creator="admin",
        create_time=datetime(2026, 5, 27, 10, 0, 0),
        updater="admin",
        update_time=datetime(2026, 5, 27, 10, 5, 0),
    )
    space = SimpleNamespace(
        id=2,
        bk_tenant_id="system",
        space_type_id="bkcc",
        space_id="2",
        space_name="蓝鲸监控",
        space_code=None,
        status="normal",
        time_zone="Asia/Shanghai",
        language="zh-hans",
        is_bcs_valid=True,
        is_global=False,
        creator="admin",
        create_time=datetime(2026, 5, 27, 9, 0, 0),
        last_modify_user="admin",
        last_modify_time=datetime(2026, 5, 27, 9, 5, 0),
    )

    item = _serialize_cluster_space_vm_info(space_vm_info, {("bkcc", "2"): space})

    assert item["space_vm_info"]["vm_cluster_id"] == 10001
    assert item["space"]["space_uid"] == "bkcc__2"
    assert item["space"]["space_name"] == "蓝鲸监控"

    missing_space_item = _serialize_cluster_space_vm_info(space_vm_info, {})
    assert missing_space_item["space"] is None


def test_render_image_task_serializer_extracts_options_and_duration():
    start_time = datetime(2026, 5, 27, 10, 0, 0)
    finish_time = datetime(2026, 5, 27, 10, 2, 5)
    task = SimpleNamespace(
        id=1,
        task_id=uuid.UUID("b916e23d-5328-44a2-a6aa-af3d0c1b5c64"),
        bk_tenant_id="system",
        options={"bk_biz_id": 2, "dashboard_uid": "dashboard-demo", "image_format": "png"},
        type="dashboard",
        status="success",
        username="admin",
        image=None,
        error="",
        create_time=start_time,
        start_time=start_time,
        finish_time=finish_time,
    )

    item = _serialize_render_image_task(task, include_detail=True)

    assert item["task_id"] == "b916e23d-5328-44a2-a6aa-af3d0c1b5c64"
    assert item["bk_biz_id"] == 2
    assert item["dashboard_uid"] == "dashboard-demo"
    assert item["duration_seconds"] == 125
    assert item["image"] == {"name": "", "url": "", "size": 0}
    assert item["options"]["image_format"] == "png"
    assert "type" not in item
    assert "type_label" not in item

    summary = _serialize_render_image_task(task)
    assert "image" not in summary
    assert "type" not in summary
    assert "type_label" not in summary


def test_uptime_check_subscription_summary_extracts_effective_data_id():
    relation = {
        "subscription_id": 123,
        "bk_biz_id": 2,
        "create_time": "2026-05-14 10:00:00",
        "update_time": "2026-05-14 10:10:00",
    }
    subscription_info = {
        "id": 123,
        "enable": True,
        "category": "once",
        "plugin_name": "bkmonitorbeat",
        "scope": {"object_type": "HOST"},
        "target_hosts": [{"bk_host_id": 1}],
        "steps": [
            {
                "id": "bkmonitorbeat_http",
                "type": "PLUGIN",
                "config": {"plugin_name": "bkmonitorbeat", "plugin_version": "1.31.0"},
                "params": {
                    "context": {
                        "tasks": [
                            {
                                "period": "60s",
                                "task_id": 135,
                                "bk_biz_id": 52,
                                "target_host_list": ["127.0.0.1"],
                            }
                        ],
                        "period": "60s",
                        "data_id": "1009",
                        "task_id": 135,
                        "bk_biz_id": 52,
                        "headers": [{"key": "Authorization", "value": "secret"}],
                    }
                },
            }
        ],
    }

    summary = _summarize_subscription(subscription_info, relation)

    assert summary["data_ids"] == [1009]
    assert summary["steps"][0]["data_ids"] == [1009]
    assert summary["steps"][0]["context_summary"]["tasks_samples"][0]["task_id"] == 135
    assert "headers" not in summary["steps"][0]["context_summary"]


def test_uptime_check_subscription_detail_masks_sensitive_and_truncates_large_json():
    relation = {
        "task_id": 135,
        "subscription_id": 123,
        "bk_biz_id": 2,
        "is_deleted": False,
        "create_time": "2026-05-14 10:00:00",
        "update_time": "2026-05-14 10:10:00",
    }
    subscription_info = {
        "id": 123,
        "enable": True,
        "steps": [
            {
                "id": "bkmonitorbeat_http",
                "params": {
                    "context": {
                        "data_id": "1009",
                        "token": "secret-token",
                        "headers": [{"key": "Authorization", "value": "secret"}],
                        "node_list": [{"bk_host_id": host_id} for host_id in range(25)],
                    }
                },
            }
        ],
    }
    status_detail = [
        {
            "subscription_id": 123,
            "instances": [{"instance_id": f"host-{index}", "status": "SUCCESS"} for index in range(25)],
        }
    ]

    detail = _build_subscription_detail_payload(
        info=subscription_info,
        relation=relation,
        status_detail=status_detail,
    )

    context = detail["config_detail"]["steps"][0]["params"]["context"]
    assert context["token"] == "***"
    assert context["headers"] == "***"
    assert context["node_list"]["count"] == 25
    assert len(context["node_list"]["samples"]) == 20
    assert detail["status_detail"][0]["instances"]["count"] == 25
    assert detail["relation"]["subscription_id"] == 123


def test_api_auth_token_serializer_keeps_api_token_fields():
    token = SimpleNamespace(
        id=1,
        bk_tenant_id="system",
        name="demo-api-token",
        token="secret-token",
        namespaces=["biz#2", "biz#-4779"],
        type="api",
        params={"app_code": "demo-app", "scope": "demo"},
        expire_time=None,
        is_enabled=True,
        is_deleted=False,
        create_user="admin",
        create_time=None,
        update_user="admin",
        update_time=None,
    )

    item = _serialize_api_auth_token(token)

    assert item["type"] == "api"
    assert item["token"] == "secret-token"
    assert item["namespaces"] == ["biz#2", "biz#-4779"]
    assert item["app_code"] == "demo-app"
    assert item["applicant"] == "admin"
    assert item["biz_ids"] == [2, -4779]


def test_api_auth_token_namespaces_accepts_json_and_csv():
    assert _normalize_namespaces('["biz#2", "project#5"]') == ["biz#2", "project#5"]
    assert _normalize_namespaces("biz#2, project#5") == ["biz#2", "project#5"]


def test_api_auth_token_biz_ids_accepts_negative_biz_id():
    assert _normalize_biz_ids([2, "-4779"]) == [2, -4779]


def test_doris_storage_physical_metadata_rpc_marks_inspect_and_serializes_runtime_values():
    runtime_cluster = SimpleNamespace(cluster_id=41)
    storage = SimpleNamespace(
        storage_cluster_id=40,
        query_physical_storage_metadata=lambda *, storage_cluster_id: {
            "physical_metadata": {
                "tables": [{"CREATE_TIME": datetime(2026, 5, 12, 10, 30, 0), "TABLE_ROWS": Decimal("3")}]
            },
            "storage_cluster": {"cluster_id": storage_cluster_id},
            "warnings": [],
            "errors": [],
        },
    )

    with (
        patch.object(_doris_storage_manager(), "get", return_value=storage),
        patch.object(admin_storage, "resolve_runtime_storage_cluster", return_value=runtime_cluster) as resolve_cluster,
    ):
        response = get_doris_storage_physical_metadata(
            {"bk_tenant_id": "system", "table_id": "2_bklog.demo", "storage_cluster_id": 41}
        )

    resolve_cluster.assert_called_once_with(storage, "system", 41, admin_storage.models.ClusterInfo.TYPE_DORIS)
    assert response["meta"]["safety_level"] == "inspect"
    assert response["meta"]["requested_safety_level"] == "inspect"
    assert response["data"]["storage_cluster"]["cluster_id"] == 41
    assert response["data"]["physical_metadata"]["tables"][0]["CREATE_TIME"] == "2026-05-12 10:30:00"
    assert response["data"]["physical_metadata"]["tables"][0]["TABLE_ROWS"] == "3"


def test_doris_storage_latest_records_rpc_passes_limit_and_order_field():
    calls = []

    def query_latest_physical_storage_records(*, limit, order_field, storage_cluster_id):
        calls.append({"limit": limit, "order_field": order_field, "storage_cluster_id": storage_cluster_id})
        return {"records": [{"value": "latest"}], "warnings": [], "errors": []}

    storage = SimpleNamespace(
        storage_cluster_id=40,
        query_latest_physical_storage_records=query_latest_physical_storage_records,
    )
    runtime_cluster = SimpleNamespace(cluster_id=41)

    with (
        patch.object(_doris_storage_manager(), "get", return_value=storage),
        patch.object(admin_storage, "resolve_runtime_storage_cluster", return_value=runtime_cluster),
    ):
        response = get_doris_storage_latest_records(
            {
                "bk_tenant_id": "system",
                "table_id": "2_bklog.demo",
                "storage_cluster_id": "41",
                "limit": "200",
                "order_field": "time",
            }
        )

    assert calls == [{"limit": 100, "order_field": "time", "storage_cluster_id": 41}]
    assert response["meta"]["safety_level"] == "inspect"
    assert response["data"]["records"] == [{"value": "latest"}]


def test_datasource_serializer_masks_token():
    datasource = SimpleNamespace(
        bk_data_id=50010,
        bk_tenant_id="system",
        data_name="demo",
        data_description="demo datasource",
        type_label="time_series",
        source_label="bk_monitor",
        custom_label=None,
        source_system="bk_monitor",
        is_enable=True,
        is_custom_source=True,
        is_platform_data_id=False,
        space_type_id="bkcc",
        space_uid="bkcc__2",
        created_from="bkdata",
        mq_cluster_id=1,
        mq_config_id=2,
        transfer_cluster_id="default",
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        token="secret-token",
    )

    item = _serialize_datasource(datasource)

    assert "token" not in item
    assert item["has_token"] is True


def test_result_table_detail_serializer_does_not_return_fields():
    result_table = SimpleNamespace(
        table_id="system.cpu",
        bk_tenant_id="system",
        table_name_zh="CPU",
        bk_biz_id=2,
        bk_biz_id_alias="",
        schema_type="fixed",
        default_storage="influxdb",
        label="os",
        data_label="bk_monitor",
        labels={},
        is_custom_table=False,
        is_builtin=True,
        is_enable=True,
        is_deleted=False,
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
    )

    item = _serialize_result_table_detail(result_table)

    assert item["table_id"] == "system.cpu"
    assert "fields" not in item


def test_datalink_component_list_accepts_cluster_config_kind():
    cluster_config = SimpleNamespace(
        name="default-vm",
        kind="VmStorage",
        namespace="bkmonitor",
        bk_tenant_id="system",
        origin_config={"domain": "vm.example.com"},
        create_time=None,
        update_time=None,
    )
    queryset = _FakeQuerySet([cluster_config])

    with patch.object(admin_datalink.ClusterConfig.objects, "filter", return_value=queryset) as cluster_filter:
        response = list_components(
            {"bk_tenant_id": "system", "kind": "VmStorage", "namespace": "bkmonitor", "page": 1, "page_size": 20}
        )

    cluster_filter.assert_called_once_with(bk_tenant_id="system", kind="VmStorage")
    assert queryset.filters == [{"namespace": "bkmonitor"}]
    assert queryset.ordering == [("-create_time",)]
    assert response["data"]["total"] == 1
    assert response["data"]["items"][0]["kind"] == "VmStorage"
    assert response["data"]["items"][0]["status"] == ""
    assert response["data"]["items"][0]["data_link_name"] is None
    assert response["data"]["items"][0]["bk_biz_id"] == 0


def test_datalink_databus_serializer_includes_consumer_group():
    databus = SimpleNamespace(
        name="l_1575783",
        namespace="bklog",
        create_time=None,
        last_modify_time=None,
        status="Ok",
        data_link_name="l_1575783",
        bk_biz_id=7,
        bk_tenant_id="default",
        data_id_name="l_1575783",
        bk_data_id=1575783,
        sink_names=["ElasticSearchBinding:l_1575783"],
        consumer_group="bkmonitorv3_transfer0bkmonitor_15757830",
    )

    item = admin_datalink._serialize_component(databus, "Databus")

    assert item["kind"] == "Databus"
    assert item["consumer_group"] == "bkmonitorv3_transfer0bkmonitor_15757830"


def test_datalink_component_detail_accepts_cluster_config_kind_with_component_config():
    cluster_config = SimpleNamespace(
        name="default-vm",
        kind="VmStorage",
        namespace="bkmonitor",
        bk_tenant_id="system",
        origin_config={"domain": "vm.example.com"},
        create_time=None,
        update_time=None,
        component_config={
            "kind": "VmStorage",
            "metadata": {"namespace": "bkmonitor", "name": "default-vm"},
            "spec": {"password": "secret"},
        },
    )

    with patch.object(admin_datalink.ClusterConfig.objects, "get", return_value=cluster_config) as cluster_get:
        response = get_component_detail(
            {
                "bk_tenant_id": "system",
                "kind": "VmStorage",
                "namespace": "bkmonitor",
                "name": "default-vm",
                "include": ["component_config"],
            }
        )

    cluster_get.assert_called_once_with(
        bk_tenant_id="system",
        kind="VmStorage",
        namespace="bkmonitor",
        name="default-vm",
    )
    assert response["data"]["kind"] == "VmStorage"
    assert response["data"]["status"] == ""
    assert response["data"]["component_config"]["kind"] == "VmStorage"
    assert response["data"]["component_config"]["spec"]["password"] == "***"


def test_datalink_component_config_accepts_cluster_config_kind():
    cluster_config = SimpleNamespace(
        name="default-vm",
        kind="VmStorage",
        namespace="bkmonitor",
        bk_tenant_id="system",
        component_config={
            "kind": "VmStorage",
            "metadata": {"namespace": "bkmonitor", "name": "default-vm"},
            "spec": {"password": "secret"},
        },
    )

    with patch.object(admin_datalink.ClusterConfig.objects, "get", return_value=cluster_config):
        response = get_datalink_component_config(
            {"bk_tenant_id": "system", "kind": "VmStorage", "namespace": "bkmonitor", "name": "default-vm"}
        )

    assert response["data"]["kind"] == "VmStorage"
    assert response["data"]["component_config"]["spec"]["password"] == "***"


def test_cluster_info_serializer_masks_sensitive_fields():
    cluster = SimpleNamespace(
        cluster_id=1,
        cluster_name="kafka_cluster1",
        display_name="Kafka Cluster 1",
        cluster_type="kafka",
        domain_name="kafka.example.com",
        port=9092,
        extranet_domain_name="",
        extranet_port=0,
        description="default kafka",
        is_default_cluster=True,
        schema=None,
        is_ssl_verify=False,
        ssl_verification_mode="none",
        ssl_insecure_skip_verify=False,
        is_auth=False,
        sasl_mechanisms=None,
        security_protocol=None,
        registered_system="_default",
        registered_to_bkbase=True,
        is_register_to_gse=False,
        gse_stream_to_id=-1,
        label="",
        default_settings={"bk_biz_id": 2},
        custom_option='{"source": "manual"}',
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        version=None,
        username="admin",
        password="secret123",
        ssl_certificate_authorities="ca-cert-data",
        ssl_certificate="cert-data",
        ssl_certificate_key="key-data",
    )

    item = _serialize_cluster_info(cluster)

    assert "username" not in item
    assert "password" not in item
    assert "ssl_certificate_authorities" not in item
    assert "ssl_certificate" not in item
    assert "ssl_certificate_key" not in item
    assert item["has_username"] is True
    assert item["has_password"] is True
    assert item["has_ssl_certificate_authorities"] is True
    assert item["has_ssl_certificate"] is True
    assert item["has_ssl_certificate_key"] is True
    assert item["default_settings"] == {"bk_biz_id": 2}
    assert item["custom_option"] == '{"source": "manual"}'


def test_cluster_info_serializer_empty_sensitive_fields():
    cluster = SimpleNamespace(
        cluster_id=2,
        cluster_name="test_cluster",
        display_name="Test",
        cluster_type="kafka",
        domain_name="localhost",
        port=9092,
        extranet_domain_name="",
        extranet_port=0,
        description="",
        is_default_cluster=False,
        schema=None,
        is_ssl_verify=False,
        ssl_verification_mode="none",
        ssl_insecure_skip_verify=False,
        is_auth=False,
        sasl_mechanisms=None,
        security_protocol=None,
        registered_system="_default",
        registered_to_bkbase=False,
        is_register_to_gse=False,
        gse_stream_to_id=-1,
        label="",
        default_settings={},
        custom_option="",
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        version=None,
        username="",
        password="",
        ssl_certificate_authorities="",
        ssl_certificate="",
        ssl_certificate_key="",
    )

    item = _serialize_cluster_info(cluster)

    assert item["has_username"] is False
    assert item["has_password"] is False
    assert item["has_ssl_certificate_authorities"] is False
    assert item["has_ssl_certificate"] is False
    assert item["has_ssl_certificate_key"] is False


def test_es_cluster_overview_uses_lightweight_alias_count_query():
    client = SimpleNamespace(
        cluster=SimpleNamespace(
            health=Mock(
                return_value={
                    "status": "green",
                    "timed_out": False,
                    "number_of_nodes": "3",
                    "number_of_data_nodes": "2",
                    "active_shards": "10",
                    "initializing_shards": "0",
                    "relocating_shards": "0",
                    "unassigned_shards": "0",
                }
            ),
            stats=Mock(
                return_value={
                    "nodes": {"count": {"total": 3}},
                    "indices": {
                        "count": 5,
                        "store": {"size_in_bytes": 1024},
                        "docs": {"count": 100, "deleted": 2},
                        "shards": {"total": 10},
                    },
                }
            ),
            get_settings=Mock(return_value={"defaults": {"cluster": {"max_shards_per_node": "1000"}}}),
        ),
        cat=SimpleNamespace(
            allocation=Mock(return_value=[{"disk.total": "100", "disk.used": "40", "disk.avail": "60"}]),
            aliases=Mock(
                return_value=[
                    {"alias": "write_20260514_system_cpu"},
                    {"alias": "system_cpu_read"},
                    {"alias": "system_cpu_read"},
                ]
            ),
        ),
        indices=SimpleNamespace(get_alias=Mock(side_effect=AssertionError("indices.get_alias should not be called"))),
    )
    cluster = SimpleNamespace(
        cluster_id=3,
        cluster_name="default-es",
        display_name="默认 ES",
        cluster_type="elasticsearch",
    )

    with patch("kernel_api.rpc.functions.admin.cluster_info.es_tools.get_client", return_value=client):
        data, warnings = _build_es_cluster_overview(cluster, "system")

    assert warnings == []
    assert data["aliases"] == {"count": 2, "relation_count": 3, "index_count": None}
    client.cat.allocation.assert_called_once()
    client.cat.aliases.assert_called_once_with(format="json", params={"h": "alias", "request_timeout": 10})
    client.indices.get_alias.assert_not_called()


def test_bcs_cluster_serializer_masks_sensitive_fields():
    cluster = SimpleNamespace(
        cluster_id="BCS-K8S-00000",
        bk_tenant_id="system",
        bcs_api_cluster_id="BCS-K8S-00000",
        bk_biz_id=2,
        bk_cloud_id=None,
        project_id="proj-123",
        status="running",
        domain_name="bcs-api.example.com",
        port=443,
        server_address_path="clusters",
        api_key_type="authorization",
        api_key_prefix="Bearer",
        is_skip_ssl_verify=True,
        K8sMetricDataID=1000,
        CustomMetricDataID=0,
        K8sEventDataID=2000,
        CustomEventDataID=0,
        SystemLogDataID=0,
        CustomLogDataID=0,
        bk_env="",
        operator_ns="bkmonitor-operator",
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        is_deleted_allow_view=False,
        api_key_content="secret-api-key",
        cert_content="cert-data",
    )

    item = _serialize_bcs_cluster(cluster)

    assert "api_key_content" not in item
    assert "cert_content" not in item
    assert item["has_api_key"] is True
    assert item["has_cert"] is True


def test_bcs_cluster_serializer_empty_sensitive_fields():
    cluster = SimpleNamespace(
        cluster_id="BCS-K8S-00001",
        bk_tenant_id="system",
        bcs_api_cluster_id="BCS-K8S-00001",
        bk_biz_id=3,
        bk_cloud_id=None,
        project_id="proj-456",
        status="running",
        domain_name="bcs-api.example.com",
        port=443,
        server_address_path="clusters",
        api_key_type="authorization",
        api_key_prefix="Bearer",
        is_skip_ssl_verify=True,
        K8sMetricDataID=0,
        CustomMetricDataID=0,
        K8sEventDataID=0,
        CustomEventDataID=0,
        SystemLogDataID=0,
        CustomLogDataID=0,
        bk_env="",
        operator_ns="bkmonitor-operator",
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        is_deleted_allow_view=False,
        api_key_content=None,
        cert_content=None,
    )

    item = _serialize_bcs_cluster(cluster)

    assert item["has_api_key"] is False
    assert item["has_cert"] is False


def test_bcs_cluster_data_id_list_reads_k8s_crd_and_marks_inspect():
    api_client = object()
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=api_client)
    custom_client = Mock()
    custom_client.list_cluster_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "name": "bk-monitor-agg-gateway-for-apm",
                    "labels": {
                        "bk_env": "bkop",
                        "usage": "metric",
                        "isCommon": "false",
                        "isSystem": "false",
                    },
                    "creationTimestamp": "2025-10-09T12:58:30Z",
                    "resourceVersion": "2813317942",
                },
                "spec": {
                    "dataID": 1573231,
                    "monitorResource": {
                        "kind": "servicemonitor",
                        "namespace": "blueking",
                        "name": "bk-monitor-agg-gateway-for-apm",
                    },
                    "labels": {
                        "bk_biz_id": "2",
                        "bcs_cluster_id": "BCS-K8S-00000",
                        "scope_name": "default",
                        "service_name": "bk_monitorv3_web",
                    },
                },
            },
            {
                "metadata": {
                    "name": "bkop-relationdataid",
                    "labels": {"usage": "metric"},
                    "creationTimestamp": "2026-04-28T04:04:10Z",
                    "resourceVersion": "3614358247",
                },
                "spec": {
                    "dataID": 1573946,
                    "monitorResource": {
                        "kind": "ServiceMonitor",
                        "namespace": "bkmonitor-operator",
                        "name": "bkmonitor-operator-operator-relation",
                    },
                    "labels": {"bk_biz_id": "2", "bcs_cluster_id": "BCS-K8S-00000"},
                },
            },
        ]
    }

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster) as cluster_get,
        patch.object(admin_bcs_cluster.k8s_client, "CustomObjectsApi", return_value=custom_client) as custom_api,
    ):
        result = admin_bcs_cluster.list_bcs_cluster_data_ids(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "page": 1, "page_size": 1}
        )

    cluster_get.assert_called_once_with(bk_tenant_id="system", cluster_id="BCS-K8S-00001")
    custom_api.assert_called_once_with(api_client)
    custom_client.list_cluster_custom_object.assert_called_once_with(
        group=admin_bcs_cluster.config.BCS_RESOURCE_GROUP_NAME,
        version=admin_bcs_cluster.config.BCS_RESOURCE_VERSION,
        plural=admin_bcs_cluster.config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
    )
    assert result["data"]["total"] == 2
    assert result["data"]["items"][0]["name"] == "bk-monitor-agg-gateway-for-apm"
    assert result["data"]["items"][0]["data_id"] == 1573231
    assert result["data"]["items"][0]["is_common"] is False
    assert result["data"]["items"][0]["monitor_resource"]["kind"] == "servicemonitor"
    assert result["data"]["items"][0]["labels"]["service_name"] == "bk_monitorv3_web"
    assert result["data"]["items"][0]["phase"] is None
    assert result["meta"]["safety_level"] == "inspect"
    assert result["meta"]["requested_safety_level"] == "inspect"


def test_bcs_cluster_data_id_detail_reads_single_k8s_crd():
    api_client = object()
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=api_client)
    resource = {
        "metadata": {
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": (
                    '{"apiVersion":"monitoring.bk.tencent.com/v1beta1"}'
                )
            },
            "creationTimestamp": "2025-10-09T12:58:30Z",
            "generation": 3,
            "labels": {
                "bk_env": "bkop",
                "usage": "metric",
                "isCommon": "false",
                "isSystem": "false",
            },
            "managedFields": [{"manager": "kubectl-client-side-apply"}],
            "name": "bk-monitor-agg-gateway-for-apm",
            "resourceVersion": "2813317942",
            "uid": "33b9d47a-b543-4c35-8d27-b8a3638cf00b",
        },
        "spec": {
            "dataID": "1573231",
            "dimensionReplace": {},
            "labels": {
                "bk_biz_id": "2",
                "bcs_cluster_id": "BCS-K8S-00000",
                "scope_name": "default",
                "service_name": "bk_monitorv3_web",
            },
            "metricReplace": {},
            "monitorResource": {
                "kind": "servicemonitor",
                "namespace": "blueking",
                "name": "bk-monitor-agg-gateway-for-apm",
            },
        },
    }
    custom_client = Mock()
    custom_client.get_cluster_custom_object.return_value = resource

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CustomObjectsApi", return_value=custom_client),
    ):
        result = admin_bcs_cluster.get_bcs_cluster_data_id_detail(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "name": "bk-monitor-agg-gateway-for-apm",
            }
        )

    custom_client.get_cluster_custom_object.assert_called_once_with(
        group=admin_bcs_cluster.config.BCS_RESOURCE_GROUP_NAME,
        version=admin_bcs_cluster.config.BCS_RESOURCE_VERSION,
        plural=admin_bcs_cluster.config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        name="bk-monitor-agg-gateway-for-apm",
    )
    assert result["data"]["name"] == "bk-monitor-agg-gateway-for-apm"
    assert result["data"]["data_id"] == 1573231
    assert result["data"]["is_common"] is False
    assert result["data"]["phase"] is None
    assert result["data"]["monitor_resource"]["kind"] == "servicemonitor"
    assert result["data"]["resource"] == resource
    assert result["meta"]["requested_safety_level"] == "inspect"


def test_bcs_cluster_data_id_detail_converts_k8s_404_to_custom_exception():
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=object())
    custom_client = Mock()
    custom_client.get_cluster_custom_object.side_effect = admin_bcs_cluster.k8s_client.exceptions.ApiException(
        status=404,
        reason="Not Found",
    )

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CustomObjectsApi", return_value=custom_client),
        pytest.raises(CustomException, match="未找到 BCS DataID 资源"),
    ):
        admin_bcs_cluster.get_bcs_cluster_data_id_detail(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "name": "missing"}
        )


def _gzip_b64_config(config_text: str) -> str:
    return base64.b64encode(gzip.compress(config_text.encode())).decode()


def _bk_collector_secret(name: str, data: dict[str, str]):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            namespace="bkmonitor-operator",
            creation_timestamp=datetime(2026, 5, 28, 10, 0, 0),
            resource_version="1001",
        ),
        data=data,
    )


def _collector_secret_list_side_effect(*, platform_config: str | None = None):
    def side_effect(namespace, label_selector):
        if "source=custom_report_v2_json" in label_selector:
            return SimpleNamespace(
                items=[
                    _bk_collector_secret(
                        "bk-collector-subconfig-json-001-100",
                        {
                            "report-v2-1001.conf": _gzip_b64_config(
                                'validator_config = {"type": "event"}\nbk_data_token = "event-token"\n'
                            ),
                            "report-v2-1004.conf": _gzip_b64_config(
                                'validator_config = {"type": "time_series"}\nbk_data_token = "metric-token"\n'
                            ),
                        },
                    )
                ]
            )
        if "source=custom_report_prometheus" in label_selector:
            return SimpleNamespace(
                items=[
                    _bk_collector_secret(
                        "bk-collector-subconfig-prometheus-001-100",
                        {
                            "application-1002.conf": _gzip_b64_config(
                                'bk_app_name = "prometheus_report"\nbk_biz_id = 2\nmetric_data_id = 1002\n'
                            )
                        },
                    )
                ]
            )
        if "source=custom_log" in label_selector:
            return SimpleNamespace(
                items=[
                    _bk_collector_secret(
                        "bk-collector-subconfig-log-001-50",
                        {
                            "application-1003.conf": _gzip_b64_config(
                                'bk_app_name = "demo_log"\nbk_biz_id = 2\nlog_data_id = 1003\n'
                            )
                        },
                    )
                ]
            )
        if "source=apm" in label_selector:
            return SimpleNamespace(
                items=[
                    _bk_collector_secret(
                        "bk-collector-subconfig-apm-01-20",
                        {
                            "application-2001.conf": _gzip_b64_config(
                                'bk_app_name = "demo_apm"\nbk_biz_id = 2\ntrace_data_id = 20011\n'
                            )
                        },
                    )
                ]
            )
        if "type=platform" in label_selector:
            return SimpleNamespace(
                items=[
                    _bk_collector_secret(
                        "bk-collector-platform",
                        {
                            "platform.conf": _gzip_b64_config(
                                platform_config
                                or 'token_checker_config = {"decoded_key": "real-key", "decoded_iv": "real-iv"}\n'
                            )
                        },
                    )
                ]
            )
        return SimpleNamespace(items=[])

    return side_effect


def _k8s_namespace(name: str):
    return SimpleNamespace(metadata=SimpleNamespace(name=name))


def _helm_release_payload(
    revision: int,
    chart_version: str,
    status: str = "superseded",
    release_name: str = "bkmonitor-operator",
) -> str:
    release = {
        "name": release_name,
        "version": revision,
        "info": {
            "status": status,
            "last_deployed": f"2026-04-28T11:{revision % 60:02d}:31+08:00",
            "description": "Upgrade complete",
        },
        "chart": {
            "metadata": {
                "name": "bkmonitor-operator-stack",
                "version": chart_version,
                "appVersion": "3.6.0",
            }
        },
        "config": {
            "bkmonitor-operator-charts": {
                "bkmonitor-operator": {
                    "dryRun": False,
                    "statefulsetReplicas": 1,
                },
                "bk-collector": {
                    "enabled": True,
                    "replicas": 1,
                },
            }
        },
    }
    compressed = gzip.compress(json.dumps(release).encode())
    return base64.b64encode(base64.b64encode(compressed)).decode()


def _helm_release_secret(
    revision: int,
    chart_version: str,
    status: str = "superseded",
    release_name: str = "bkmonitor-operator",
    namespace: str = "bkmonitor-operator",
):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=f"sh.helm.release.v1.{release_name}.v{revision}",
            namespace=namespace,
            creation_timestamp=datetime(2026, 4, 28, 11, revision % 60, 31),
            resource_version=str(7100 + revision),
        ),
        type="helm.sh/release.v1",
        data={"release": _helm_release_payload(revision, chart_version, status, release_name)},
    )


def test_bcs_cluster_bkmonitor_operator_release_list_scans_keyword_namespaces_and_groups_by_release_name():
    api_client = object()
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=api_client, operator_ns="fake-operator-ns")
    core_client = Mock()
    core_client.list_namespace.return_value = SimpleNamespace(
        items=[
            _k8s_namespace("default"),
            _k8s_namespace("bkmonitor-operator"),
            _k8s_namespace("bkmonitor-operator-canary"),
        ]
    )

    def list_secret_side_effect(namespace: str, label_selector: str):
        assert label_selector == "owner=helm"
        if namespace == "bkmonitor-operator":
            return SimpleNamespace(
                items=[
                    _helm_release_secret(70, "3.6.166", namespace=namespace),
                    _helm_release_secret(71, "3.6.174", status="deployed", namespace=namespace),
                ]
            )
        if namespace == "bkmonitor-operator-canary":
            return SimpleNamespace(
                items=[
                    _helm_release_secret(
                        3,
                        "3.7.0",
                        status="deployed",
                        release_name="custom-operator",
                        namespace=namespace,
                    )
                ]
            )
        return SimpleNamespace(items=[])

    core_client.list_namespaced_secret.side_effect = list_secret_side_effect

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client) as core_api,
        patch.object(
            admin_bcs_cluster.settings,
            "K8S_OPERATOR_DEPLOY_NAMESPACE",
            {"BCS-K8S-00001": "configured-ns"},
        ),
    ):
        result = admin_bcs_cluster.list_bcs_cluster_bkmonitor_operator_releases(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "page": 1, "page_size": 20}
        )

    core_api.assert_called_once_with(api_client)
    core_client.list_namespace.assert_called_once_with()
    assert core_client.list_namespaced_secret.call_args_list == [
        call(namespace="bkmonitor-operator", label_selector="owner=helm"),
        call(namespace="bkmonitor-operator-canary", label_selector="owner=helm"),
    ]
    assert result["data"]["namespace_candidates"] == [
        "bkmonitor-operator",
        "bkmonitor-operator-canary",
    ]
    assert "configured_namespace" not in result["data"]
    assert result["data"]["total"] == 2
    assert result["data"]["release_total"] == 3
    assert [group["release_name"] for group in result["data"]["groups"]] == [
        "bkmonitor-operator",
        "custom-operator",
    ]
    assert result["data"]["groups"][0]["latest_revision"] == 71
    assert [item["revision"] for item in result["data"]["groups"][0]["items"]] == [71, 70]
    latest = result["data"]["items"][0]
    assert latest["release_ref"] == "bkmonitor-operator:sh.helm.release.v1.bkmonitor-operator.v71"
    assert latest["release_name"] == "bkmonitor-operator"
    assert latest["chart_name"] == "bkmonitor-operator-stack"
    assert latest["chart_version"] == "3.6.174"
    assert latest["app_version"] == "3.6.0"
    assert latest["status"] == "deployed"
    assert latest["description"] == "Upgrade complete"
    assert "values" not in latest
    assert result["meta"]["safety_level"] == "inspect"
    assert result["meta"]["requested_safety_level"] == "inspect"


def test_bcs_cluster_bkmonitor_operator_release_detail_decodes_values():
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=object(), operator_ns="operator-ns")
    core_client = Mock()
    core_client.read_namespaced_secret.return_value = _helm_release_secret(
        3,
        "3.7.0",
        status="deployed",
        release_name="custom-operator",
        namespace="bkmonitor-operator-canary",
    )

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
    ):
        result = admin_bcs_cluster.get_bcs_cluster_bkmonitor_operator_release_detail(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "release_ref": "bkmonitor-operator-canary:sh.helm.release.v1.custom-operator.v3",
            }
        )

    core_client.read_namespaced_secret.assert_called_once_with(
        name="sh.helm.release.v1.custom-operator.v3",
        namespace="bkmonitor-operator-canary",
    )
    assert result["data"]["release_name"] == "custom-operator"
    assert result["data"]["revision"] == 3
    assert result["data"]["status"] == "deployed"
    assert result["data"]["values"]["bkmonitor-operator-charts"]["bkmonitor-operator"]["dryRun"] is False
    assert result["data"]["values"]["bkmonitor-operator-charts"]["bk-collector"]["enabled"] is True
    assert result["meta"]["requested_safety_level"] == "inspect"


def test_bcs_cluster_bk_collector_config_list_reads_runtime_secrets_and_marks_inspect():
    api_client = object()
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=api_client, operator_ns="operator-ns")
    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect()

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client) as core_api,
    ):
        result = admin_bcs_cluster.list_bcs_cluster_bk_collector_configs(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "page": 1, "page_size": 20}
        )

    core_api.assert_called_once_with(api_client)
    assert core_client.list_namespaced_secret.call_count == 5
    assert {call.kwargs["namespace"] for call in core_client.list_namespaced_secret.call_args_list} == {"operator-ns"}
    assert result["data"]["total"] == 6
    assert result["data"]["namespace"] == "operator-ns"
    assert result["data"]["operator_namespace"] == "operator-ns"
    assert result["data"]["using_configured_namespace"] is False
    assert result["data"]["category_counts"]["custom_report_json"] == 2
    assert result["data"]["category_counts"]["custom_event"] == 0
    assert result["data"]["category_counts"]["custom_metric_json"] == 0
    assert result["data"]["category_counts"]["custom_metric_prometheus"] == 1
    assert result["data"]["category_counts"]["custom_log"] == 1
    assert result["data"]["category_counts"]["apm_application"] == 1
    assert result["data"]["category_counts"]["apm_platform"] == 1
    report_item = next(item for item in result["data"]["items"] if item["config_id"] == 1001)
    assert report_item["category"] == "custom_report_json"
    assert report_item["secret_name"] == "bk-collector-subconfig-json-001-100"
    assert "config" not in report_item
    assert "name" not in report_item
    assert "bk_biz_id" not in report_item
    assert "bk_data_id" not in report_item
    assert "data_ids" not in report_item
    assert "table_id" not in report_item
    assert "category_label" not in report_item
    assert "is_enable" not in report_item
    assert "last_modify_time" not in report_item
    assert "config_size" not in report_item
    assert "decode_error" not in report_item
    assert "has_sensitive" not in report_item
    assert "sensitive_masked" not in report_item
    assert result["meta"]["safety_level"] == "inspect"
    assert result["meta"]["requested_safety_level"] == "inspect"


def test_bcs_cluster_bk_collector_config_list_filters_by_data_id_and_apm_application_id():
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=object(), operator_ns="operator-ns")
    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect()

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
    ):
        data_id_result = admin_bcs_cluster.list_bcs_cluster_bk_collector_configs(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "category": "custom_report_prometheus",
                "keyword": "1002",
            }
        )
        apm_result = admin_bcs_cluster.list_bcs_cluster_bk_collector_configs(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "category": "apm_application",
                "keyword": "2001",
            }
        )

    assert core_client.list_namespaced_secret.call_count == 2
    assert data_id_result["data"]["total"] == 1
    assert data_id_result["data"]["items"][0]["category"] == "custom_metric_prometheus"
    assert data_id_result["data"]["items"][0]["config_id"] == 1002
    assert data_id_result["data"]["category_counts"]["custom_metric_prometheus"] == 1
    assert apm_result["data"]["total"] == 1
    assert apm_result["data"]["items"][0]["category"] == "apm_application"
    assert apm_result["data"]["items"][0]["config_id"] == 2001
    assert apm_result["data"]["category_counts"]["apm_application"] == 1


def test_bcs_cluster_bk_collector_config_list_can_switch_to_configured_namespace():
    api_client = object()
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=api_client, operator_ns="operator-ns")
    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect()

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
        patch.object(
            admin_bcs_cluster.settings,
            "K8S_OPERATOR_DEPLOY_NAMESPACE",
            {"BCS-K8S-00001": "configured-ns"},
        ),
    ):
        result = admin_bcs_cluster.list_bcs_cluster_bk_collector_configs(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "use_config_namespace": True,
                "page": 1,
                "page_size": 20,
            }
        )

    assert {call.kwargs["namespace"] for call in core_client.list_namespaced_secret.call_args_list} == {"configured-ns"}
    assert result["data"]["namespace"] == "configured-ns"
    assert result["data"]["operator_namespace"] == "operator-ns"
    assert result["data"]["configured_namespace"] == "configured-ns"
    assert result["data"]["can_use_configured_namespace"] is True
    assert result["data"]["using_configured_namespace"] is True


def test_bcs_cluster_bk_collector_config_detail_masks_platform_secret_by_default():
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=object(), operator_ns="operator-ns")
    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect()
    config_ref = admin_bcs_cluster._encode_bk_collector_config_ref("platform", "bk-collector-platform", "platform.conf")

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
    ):
        result = admin_bcs_cluster.get_bcs_cluster_bk_collector_config_detail(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "config_ref": config_ref}
        )

    assert result["data"]["category"] == "apm_platform"
    assert result["data"]["namespace"] == "operator-ns"
    assert "has_sensitive" not in result["data"]
    assert "sensitive_masked" not in result["data"]
    assert "include_sensitive" not in result["data"]
    assert "real-key" not in result["data"]["config"]
    assert "******" in result["data"]["config"]


def test_bcs_cluster_bk_collector_config_detail_can_show_platform_secret_and_keeps_report_token():
    cluster = SimpleNamespace(cluster_id="BCS-K8S-00001", api_client=object(), operator_ns="operator-ns")
    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect(
        platform_config='token_checker_config = {"decoded_key": "real-key"}\n'
    )
    platform_ref = admin_bcs_cluster._encode_bk_collector_config_ref(
        "platform", "bk-collector-platform", "platform.conf"
    )

    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
    ):
        platform_result = admin_bcs_cluster.get_bcs_cluster_bk_collector_config_detail(
            {
                "bk_tenant_id": "system",
                "cluster_id": "BCS-K8S-00001",
                "config_ref": platform_ref,
                "include_sensitive": True,
            }
        )

    assert "sensitive_masked" not in platform_result["data"]
    assert "include_sensitive" not in platform_result["data"]
    assert "real-key" in platform_result["data"]["config"]

    core_client = Mock()
    core_client.list_namespaced_secret.side_effect = _collector_secret_list_side_effect()
    report_ref = admin_bcs_cluster._encode_bk_collector_config_ref(
        "json", "bk-collector-subconfig-json-001-100", "report-v2-1001.conf"
    )
    with (
        patch.object(admin_bcs_cluster.models.BCSClusterInfo.objects, "get", return_value=cluster),
        patch.object(admin_bcs_cluster.k8s_client, "CoreV1Api", return_value=core_client),
    ):
        report_result = admin_bcs_cluster.get_bcs_cluster_bk_collector_config_detail(
            {"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00001", "config_ref": report_ref}
        )

    assert report_result["data"]["category"] == "custom_event"
    assert "event-token" in report_result["data"]["config"]


def test_es_storage_table_kind_uses_origin_table_id():
    assert _is_virtual_es_storage(SimpleNamespace(origin_table_id="system.cpu_origin")) is True
    assert _table_kind(SimpleNamespace(origin_table_id="system.cpu_origin")) == "virtual"
    assert _is_virtual_es_storage(SimpleNamespace(origin_table_id="")) is False
    assert _table_kind(SimpleNamespace(origin_table_id=None)) == "physical"


def test_es_storage_config_parses_json_fields_and_warns_on_invalid_json():
    es_storage = SimpleNamespace(
        id=1,
        table_id="system.cpu",
        origin_table_id="",
        bk_tenant_id="system",
        storage_cluster_id=1,
        date_format="%Y%m%d",
        slice_size=500,
        slice_gap=120,
        retention=7,
        warm_phase_days=0,
        time_zone=0,
        source_type="log",
        index_set="system_cpu",
        need_create_index=True,
        archive_index_days=0,
        create_time=None,
        last_modify_time=None,
        index_settings='{"number_of_shards": 1}',
        mapping_settings="{bad-json",
        warm_phase_settings={"allocation_attr_name": "box_type"},
        long_term_storage_settings="",
    )
    warnings = []

    item = _serialize_es_storage_config(es_storage, warnings)

    assert item["table_kind"] == "physical"
    assert item["index_settings"] == {"number_of_shards": 1}
    assert item["mapping_settings"] == "{bad-json"
    assert warnings[0]["code"] == "ES_STORAGE_JSON_PARSE_FAILED"


def test_query_route_normalize_string_list():
    assert _normalize_string_list("system.cpu, 1001_bklog.stdout,,system.cpu", "table_ids") == [
        "system.cpu",
        "1001_bklog.stdout",
    ]
    assert _normalize_string_list(["a", " b ", "a", ""], "data_labels") == ["a", "b"]


def test_query_route_resolve_space_identity():
    assert _resolve_space_identity({"space_uid": "bkcc__2"}) == ("bkcc__2", "bkcc", "2")
    assert _resolve_space_identity({"space_type_id": "bcs", "space_id": "project"}) == (
        "bcs__project",
        "bcs",
        "project",
    )


def test_query_route_format_filter_groups():
    groups = _format_filter_groups([{"bk_biz_id": "2", "cluster_id": ["a", "b"]}, {"project_id": "demo"}])

    assert groups == [
        {
            "operator": "AND",
            "conditions": [
                {"field": "bk_biz_id", "operator": "eq", "value": "2"},
                {"field": "cluster_id", "operator": "in", "value": ["a", "b"]},
            ],
            "raw": {"bk_biz_id": "2", "cluster_id": ["a", "b"]},
        },
        {
            "operator": "AND",
            "conditions": [{"field": "project_id", "operator": "eq", "value": "demo"}],
            "raw": {"project_id": "demo"},
        },
    ]


def test_es_storage_sample_rejects_wildcard_index():
    assert _contains_index_wildcard("v2_system_cpu_20260425_0") is False
    assert _contains_index_wildcard("v2_system_cpu_*") is True
    assert _contains_index_wildcard("v2_system_cpu_20260425_?") is True


def test_cluster_info_detail_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.detail")
    assert detail is not None
    assert detail["func_name"] == "admin.cluster_info.detail"
    assert "params_schema" in detail
    assert "cluster_id" in detail["params_schema"]


def test_cluster_info_space_vm_info_list_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.space_vm_info_list")
    assert detail is not None
    assert detail["func_name"] == "admin.cluster_info.space_vm_info_list"
    assert "search" in detail["params_schema"]


def test_cluster_info_health_check_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.health_check")
    assert detail is not None
    assert detail["func_name"] == "admin.cluster_info.health_check"
    assert "timeout" in detail["params_schema"]


def test_cluster_info_es_storage_analysis_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.es_storage_analysis")
    assert detail is not None
    assert detail["func_name"] == "admin.cluster_info.es_storage_analysis"
    assert "inspect" in detail["description"]
    assert "cluster_id" in detail["params_schema"]


def test_cluster_info_health_check_uses_model_health_check():
    health_result = {
        "cluster_id": 1,
        "cluster_name": "kafka-default",
        "cluster_type": "kafka",
        "status": "available",
        "is_connected": True,
        "is_available": True,
        "error": None,
        "details": {"broker_count": 2},
    }
    cluster = SimpleNamespace(
        cluster_id=1,
        cluster_type="kafka",
        health_check=Mock(return_value=health_result),
    )

    with patch.object(admin_cluster_info.models.ClusterInfo.objects, "get", return_value=cluster) as cluster_get:
        result = admin_cluster_info.check_cluster_info_health(
            {"bk_tenant_id": "system", "cluster_id": "1", "timeout": "3"}
        )

    cluster_get.assert_called_once_with(bk_tenant_id="system", cluster_id=1)
    cluster.health_check.assert_called_once_with(timeout=3)
    assert result["data"] == health_result
    assert result["meta"]["safety_level"] == "inspect"


def test_cluster_info_health_check_rejects_es_cluster():
    cluster = SimpleNamespace(cluster_id=1, cluster_type="elasticsearch")

    with patch.object(admin_cluster_info.models.ClusterInfo.objects, "get", return_value=cluster):
        with pytest.raises(CustomException, match="admin.cluster_info.es_overview"):
            admin_cluster_info.check_cluster_info_health({"bk_tenant_id": "system", "cluster_id": 1})


def _fake_es_analysis_storage(table_id):
    return SimpleNamespace(
        table_id=table_id,
        bk_tenant_id="system",
        storage_cluster_id=1,
        source_type="log",
        retention=30,
        slice_size=500,
        slice_gap=120,
        date_format="%Y%m%d%H",
        time_zone=0,
        index_set=None,
        need_create_index=True,
    )


def test_es_analysis_storage_queryset_includes_historical_cluster_records(monkeypatch):
    class FakeValuesList:
        distinct_called = False

        def distinct(self):
            self.distinct_called = True
            return self

    class FakeRecordQuerySet:
        def __init__(self, values_list):
            self.values_list_result = values_list
            self.values_list_args = None
            self.values_list_kwargs = None

        def values_list(self, *args, **kwargs):
            self.values_list_args = args
            self.values_list_kwargs = kwargs
            return self.values_list_result

    class FakeEsQuerySet:
        def __init__(self):
            self.filter_calls = []
            self.ordering = None

        def filter(self, *args, **kwargs):
            self.filter_calls.append((args, kwargs))
            return self

        def order_by(self, *fields):
            self.ordering = fields
            return self

    record_filter_calls = []
    values_list = FakeValuesList()
    record_queryset = FakeRecordQuerySet(values_list)
    es_filter_calls = []
    es_queryset = FakeEsQuerySet()

    monkeypatch.setattr(
        admin_cluster_info.models.StorageClusterRecord.objects,
        "filter",
        lambda **kwargs: record_filter_calls.append(kwargs) or record_queryset,
    )
    monkeypatch.setattr(
        admin_cluster_info.models.ESStorage.objects,
        "filter",
        lambda *args, **kwargs: es_filter_calls.append((args, kwargs)) or es_queryset,
    )

    queryset = _build_es_analysis_storage_queryset("system", 9)

    assert queryset is es_queryset
    assert record_filter_calls == [{"bk_tenant_id": "system", "cluster_id": 9, "is_deleted": False}]
    assert record_queryset.values_list_args == ("table_id",)
    assert record_queryset.values_list_kwargs == {"flat": True}
    assert values_list.distinct_called is True
    assert es_filter_calls == [((), {"bk_tenant_id": "system"})]
    assert len(es_queryset.filter_calls) == 2
    history_query = es_queryset.filter_calls[1][0][0]
    assert history_query.connector == "OR"
    assert ("storage_cluster_id", 9) in history_query.children
    assert ("table_id__in", values_list) in history_query.children
    assert es_queryset.ordering == ("table_id",)


def test_es_analysis_index_base_parses_v1_and_v2_physical_index_names():
    assert _parse_es_analysis_index_base("v2_2_bklog_demo_2026060612_0") == "2_bklog_demo"
    assert _parse_es_analysis_index_base("2_bklog_demo_2026060612_0") == "2_bklog_demo"
    assert _parse_es_analysis_index_base(".security-7") is None


def test_es_analysis_owner_parses_biz_and_space_prefixes():
    assert _parse_es_analysis_owner("2_bklog.demo") == {"owner_type": "biz", "bk_biz_id": 2}
    assert _parse_es_analysis_owner("space_125_bklog.csu250409__default__json") == {
        "owner_type": "space",
        "bk_biz_id": -125,
    }
    assert _parse_es_analysis_owner("space_demo.bklog.demo") == {
        "owner_type": "space",
        "bk_biz_id": None,
    }
    assert _parse_es_analysis_owner(None) == {"owner_type": "unknown", "bk_biz_id": None}


def test_es_analysis_index_row_matches_physical_es_storage_and_counts_shards():
    warnings = []
    storage_by_base, ambiguous_bases = _build_es_analysis_storage_index(
        [_fake_es_analysis_storage("2_bklog.demo")], {}, warnings
    )

    item = _serialize_es_analysis_index_row(
        {
            "index": "v2_2_bklog_demo_2026060612_0",
            "health": "green",
            "status": "open",
            "docs.count": "10",
            "store.size": "1024",
            "pri": "2",
            "rep": "1",
        },
        storage_by_base,
        ambiguous_bases,
    )

    assert warnings == []
    assert item["base_index"] == "2_bklog_demo"
    assert item["store_bytes"] == 1024
    assert item["docs_count"] == 10
    assert item["primary_shards"] == 2
    assert item["replica_shards"] == 2
    assert item["shards"] == 4
    assert item["match_status"] == "matched"
    assert item["match_reason"] == "base_index"
    assert item["matched_table_id"] == "2_bklog.demo"
    assert item["owner_type"] == "biz"
    assert item["bk_biz_id"] == 2


def test_es_analysis_ambiguous_base_index_goes_to_other_with_warning():
    warnings = []
    storage_by_base, ambiguous_bases = _build_es_analysis_storage_index(
        [_fake_es_analysis_storage("2.a_b"), _fake_es_analysis_storage("2_a.b")], {}, warnings
    )

    item = _serialize_es_analysis_index_row(
        {"index": "2_a_b_2026060612_0", "store.size": "2048"},
        storage_by_base,
        ambiguous_bases,
    )

    assert storage_by_base == {}
    assert "2_a_b" in ambiguous_bases
    assert warnings[0]["code"] == "ES_STORAGE_BASE_INDEX_CONFLICT"
    assert item["match_status"] == "other"
    assert item["match_reason"] == "ambiguous_base_index"
    assert item["matched_table_id"] is None


def test_cluster_info_list_supports_lightweight_include():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.list")
    assert detail is not None
    assert "include" in detail["params_schema"]
    assert "associated_counts" in detail["params_schema"]["include"]


def test_cluster_info_list_filters_by_cluster_id():
    queryset = _FakeQuerySet([])

    with patch.object(admin_cluster_info.models.ClusterInfo.objects, "all", return_value=queryset):
        result_queryset = admin_cluster_info._build_cluster_info_queryset(
            {"bk_tenant_id": "system", "cluster_id": "12"},
            "system",
        )

    assert result_queryset is queryset
    assert {"bk_tenant_id": "system"} in queryset.filters
    assert {"cluster_id": 12} in queryset.filters


def test_bcs_cluster_detail_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.bcs_cluster.detail")
    assert detail is not None
    assert detail["func_name"] == "admin.bcs_cluster.detail"


def test_kafka_sample_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.datasource.kafka_sample")
    assert detail is not None
    assert detail["func_name"] == "admin.datasource.kafka_sample"
    assert "bk_data_id" in detail["params_schema"]


def test_kafka_sample_v4_uses_data_id_config_by_bk_data_id():
    datasource = SimpleNamespace(
        bk_data_id=1001,
        datalink_version="V4",
        etl_config="bk_standard_v2_time_series",
        data_name="demo",
        mq_cluster=SimpleNamespace(is_auth=False),
        mq_config=SimpleNamespace(topic="origin_topic"),
    )
    data_id_config = SimpleNamespace(namespace="bkmonitor", name="actual_data_id_name")
    data_id_config_queryset = Mock()
    data_id_config_queryset.order_by.return_value.first.return_value = data_id_config

    with (
        patch.object(kafka_sample_module.models.DataSource.objects, "get", return_value=datasource),
        patch.object(
            kafka_sample_module.models.DataSourceResultTable.objects,
            "filter",
            return_value=Mock(first=Mock(return_value=None)),
        ),
        patch.object(kafka_sample_module, "_query_gse_route_topic", return_value=None),
        patch.object(
            kafka_sample_module.DataIdConfig.objects, "filter", return_value=data_id_config_queryset
        ) as data_id_filter,
        patch.object(kafka_sample_module.api.bkdata, "tail_kafka_data", return_value=['{"value": 1}']) as tail_kafka,
    ):
        result = kafka_sample_module.kafka_sample({"bk_tenant_id": "system", "bk_data_id": 1001, "size": 1})

    data_id_filter.assert_called_once_with(bk_tenant_id="system", bk_data_id=1001)
    tail_kafka.assert_called_once_with(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="actual_data_id_name",
        limit=1,
    )
    assert result["data"]["items"] == [{"value": 1}]


def test_custom_report_refresh_metrics_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.custom_report.refresh_metrics")
    assert detail is not None
    assert detail["func_name"] == "admin.custom_report.refresh_metrics"
    assert "write" in detail["description"]
    assert "expired_time" in detail["params_schema"]


def test_custom_report_scope_and_metric_list_functions_registered():
    scope_list = KernelRPCRegistry.get_function_detail("admin.custom_report.scope_list")
    assert scope_list is not None
    assert scope_list["func_name"] == "admin.custom_report.scope_list"
    assert "scope_name" in scope_list["params_schema"]
    assert "create_from" in scope_list["params_schema"]

    metric_list = KernelRPCRegistry.get_function_detail("admin.custom_report.metric_list")
    assert metric_list is not None
    assert "scope_id" in metric_list["params_schema"]
    assert "field_scope" in metric_list["params_schema"]


def test_custom_report_scope_serializer_returns_scope_metadata():
    scope = SimpleNamespace(
        id=2,
        group_id=1001,
        scope_name="checkout-api||production",
        dimension_config={"service_name": {"alias": "服务", "common": True, "hidden": False}},
        auto_rules=["checkout_*"],
        create_from="data",
        last_modify_time=datetime(2026, 4, 26, 10, 40, 0),
    )

    item = admin_custom_report._serialize_time_series_scope(scope, {2: 3})

    assert item == {
        "scope_id": 2,
        "group_id": 1001,
        "scope_name": "checkout-api||production",
        "dimension_config": {"service_name": {"alias": "服务", "common": True, "hidden": False}},
        "auto_rules": ["checkout_*"],
        "metric_count": 3,
        "create_from": "data",
        "last_modify_time": "2026-04-26 10:40:00",
    }


def test_custom_report_metric_serializer_returns_scope_and_field_config():
    scope = SimpleNamespace(id=2, scope_name="checkout-api||production")
    metric = SimpleNamespace(
        field_id=7001,
        field_name="http_request_total",
        table_id="2_bkmonitor_time_series.__default__",
        scope_id=2,
        field_scope="checkout-api||production",
        tag_list=["service_name", "scope_name", "target"],
        field_config={
            "alias": "HTTP 请求数",
            "unit": "none",
            "hidden": False,
            "aggregate_method": "sum",
            "function": "sum",
            "interval": 60,
            "disabled": False,
        },
        is_active=True,
        create_time=datetime(2026, 4, 26, 10, 0, 0),
        last_modify_time=datetime(2026, 4, 26, 10, 30, 0),
    )

    item = admin_custom_report._serialize_time_series_metric(metric, {2: scope})

    assert item["field_id"] == 7001
    assert item["field_name"] == "http_request_total"
    assert item["scope"] == {"id": 2, "name": "checkout-api||production"}
    assert item["field_scope"] == "checkout-api||production"
    assert item["tag_list"] == ["service_name", "scope_name", "target"]
    assert item["field_config"]["alias"] == "HTTP 请求数"
    assert item["description"] == "HTTP 请求数"
    assert item["unit"] == "none"
    assert item["create_time"] == "2026-04-26 10:00:00"
    assert item["update_time"] == "2026-04-26 10:30:00"


def test_es_storage_functions_registered():
    for func_name in [
        "admin.es_storage.list",
        "admin.es_storage.detail",
        "admin.es_storage.runtime_overview",
        "admin.es_storage.sample",
        "admin.es_storage.rotate_aliases",
    ]:
        detail = KernelRPCRegistry.get_function_detail(func_name)
        assert detail is not None
        assert detail["func_name"] == func_name

    runtime_detail = KernelRPCRegistry.get_function_detail("admin.es_storage.runtime_overview")
    assert "inspect" in runtime_detail["description"]
    assert "table_id" in runtime_detail["params_schema"]
    assert "storage_cluster_id" in runtime_detail["params_schema"]
    sample_detail = KernelRPCRegistry.get_function_detail("admin.es_storage.sample")
    assert "storage_cluster_id" in sample_detail["params_schema"]
    rotate_detail = KernelRPCRegistry.get_function_detail("admin.es_storage.rotate_aliases")
    assert "write" in rotate_detail["description"]
    assert "traceback" in rotate_detail["description"]


def test_es_storage_runtime_overview_uses_selected_runtime_cluster_without_mutating_storage():
    storage = SimpleNamespace(
        table_id="system.cpu",
        origin_table_id=None,
        storage_cluster_id=3,
        index_set="system_cpu",
        search_format_v2=lambda: "v2_system_cpu_*",
        search_format_v1=lambda: "system_cpu_*",
    )
    runtime_cluster = SimpleNamespace(
        cluster_id=11,
        cluster_name="history-es",
        display_name="历史 ES",
        cluster_type="elasticsearch",
    )

    with (
        patch.object(admin_es_storage, "_get_es_storage_or_raise", return_value=storage),
        patch.object(
            admin_es_storage,
            "resolve_runtime_storage_cluster",
            return_value=runtime_cluster,
        ) as resolve_cluster,
    ):
        response = admin_es_storage.get_es_storage_runtime_overview(
            {
                "bk_tenant_id": "system",
                "table_id": "system.cpu",
                "storage_cluster_id": 11,
                "include": [],
            }
        )

    resolve_cluster.assert_called_once_with(storage, "system", 11, admin_es_storage.models.ClusterInfo.TYPE_ES)
    assert response["data"]["storage_cluster"]["cluster_id"] == 11
    assert storage.storage_cluster_id == 3


def test_es_storage_sample_uses_selected_runtime_cluster():
    get_raw_data = Mock(return_value={"took": 1, "hits": {"hits": [{"_source": {"value": 1}}]}})
    storage = SimpleNamespace(
        table_id="system.cpu",
        origin_table_id=None,
        storage_cluster_id=3,
        get_raw_data=get_raw_data,
    )
    runtime_cluster = SimpleNamespace(
        cluster_id=11,
        cluster_name="history-es",
        display_name="历史 ES",
        cluster_type="elasticsearch",
    )

    with (
        patch.object(admin_es_storage, "_get_es_storage_or_raise", return_value=storage),
        patch.object(admin_es_storage, "resolve_runtime_storage_cluster", return_value=runtime_cluster),
        patch.object(admin_es_storage, "_is_index_allowed", return_value=True) as is_index_allowed,
    ):
        response = admin_es_storage.get_es_storage_sample(
            {
                "bk_tenant_id": "system",
                "table_id": "system.cpu",
                "storage_cluster_id": 11,
                "index": "v2_system_cpu_20260714_0",
            }
        )

    runtime_storage = is_index_allowed.call_args.args[0]
    assert runtime_storage.storage_cluster_id == 11
    assert runtime_storage._cluster is runtime_cluster
    get_raw_data.assert_called_once_with(index_name="v2_system_cpu_20260714_0", time_field="dtEventTimeStamp")
    assert response["data"]["storage_cluster"]["cluster_id"] == 11
    assert storage.storage_cluster_id == 3


def test_es_storage_runtime_index_item_keeps_stats_values_and_counts_shards():
    item = _build_runtime_index_item(
        index_name="v2_system_cpu_20260521_0",
        stats={"total": {"docs": {"count": 0}, "store": {"size_in_bytes": 0}}},
        cat_meta={"health": "green", "status": "open", "pri": "2", "rep": "1", "docs.count": "99"},
    )

    assert item["docs_count"] == 0
    assert item["store_size"] == 0
    assert item["primary_shards"] == 2
    assert item["replica_shards"] == 2
    assert item["replica_factor"] == 1
    assert item["shards"] == 4

    settings_item = _build_runtime_index_item(
        index_name="v2_system_cpu_20260521_0",
        stats={"total": {"docs": {"count": 3}, "store": {"size_in_bytes": 1024}}},
        cat_meta={},
        settings_meta={"settings": {"index": {"number_of_shards": "3", "number_of_replicas": "2"}}},
    )

    assert settings_item["primary_shards"] == 3
    assert settings_item["replica_shards"] == 6
    assert settings_item["shards"] == 9


def test_storage_functions_registered():
    for func_name in [
        "admin.doris_storage.list",
        "admin.doris_storage.detail",
        "admin.vm_storage.list",
        "admin.vm_storage.detail",
        "admin.kafka_storage.list",
        "admin.kafka_storage.detail",
        "admin.bkbase_result_table.list",
        "admin.bkbase_result_table.detail",
    ]:
        detail = KernelRPCRegistry.get_function_detail(func_name)
        assert detail is not None
        assert detail["func_name"] == func_name

    assert "table_id" in KernelRPCRegistry.get_function_detail("admin.doris_storage.list")["params_schema"]
    assert (
        "storage_cluster_id"
        in KernelRPCRegistry.get_function_detail("admin.doris_storage.physical_metadata")["params_schema"]
    )
    assert (
        "storage_cluster_id"
        in KernelRPCRegistry.get_function_detail("admin.doris_storage.latest_records")["params_schema"]
    )
    assert "id" in KernelRPCRegistry.get_function_detail("admin.vm_storage.detail")["params_schema"]
    assert "vm_cluster_id" in KernelRPCRegistry.get_function_detail("admin.vm_storage.list")["params_schema"]
    assert (
        "data_link_name" in KernelRPCRegistry.get_function_detail("admin.bkbase_result_table.detail")["params_schema"]
    )


@pytest.mark.parametrize(
    ("cluster_type", "storage_type"),
    [("elasticsearch", "es"), ("doris", "doris"), ("kafka", "unknown")],
)
def test_storage_cluster_record_exposes_related_cluster_type(cluster_type, storage_type):
    record = SimpleNamespace(
        table_id="3_bklog.demo",
        cluster_id=7,
        is_current=False,
        is_deleted=False,
        enable_time=None,
        disable_time=None,
        delete_time=None,
        creator="admin",
        create_time=None,
    )
    cluster = SimpleNamespace(
        cluster_id=7,
        cluster_name=f"history-{cluster_type}",
        display_name="历史集群",
        cluster_type=cluster_type,
    )

    item = serialize_storage_cluster_record(record, cluster)

    assert item["storage_type"] == storage_type
    assert item["cluster"]["cluster_type"] == cluster_type


def test_storage_history_uses_origin_table_id_for_virtual_es_and_doris_storage():
    storage = SimpleNamespace(table_id="3_bklog.demo_virtual", origin_table_id="3_bklog.demo")

    assert resolve_storage_history_table_id(storage) == "3_bklog.demo"


def test_runtime_storage_cluster_accepts_current_cluster_without_history_record():
    storage = SimpleNamespace(
        table_id="3_bklog.demo",
        origin_table_id=None,
        storage_cluster_id=40,
    )
    cluster = SimpleNamespace(cluster_id=40, cluster_type="doris")

    with (
        patch.object(admin_storage.models.ClusterInfo.objects, "get", return_value=cluster) as cluster_get,
        patch.object(admin_storage.models.StorageClusterRecord.objects, "filter") as history_filter,
    ):
        result = resolve_runtime_storage_cluster(storage, "system", None, "doris")

    assert result is cluster
    cluster_get.assert_called_once_with(bk_tenant_id="system", cluster_id=40, cluster_type="doris")
    history_filter.assert_not_called()


def test_runtime_storage_cluster_validates_history_against_virtual_storage_origin_table():
    storage = SimpleNamespace(
        table_id="3_bklog.demo_virtual",
        origin_table_id="3_bklog.demo",
        storage_cluster_id=40,
    )
    cluster = SimpleNamespace(cluster_id=41, cluster_type="doris")
    history_queryset = Mock()
    history_queryset.exists.return_value = True

    with (
        patch.object(admin_storage.models.ClusterInfo.objects, "get", return_value=cluster),
        patch.object(
            admin_storage.models.StorageClusterRecord.objects,
            "filter",
            return_value=history_queryset,
        ) as history_filter,
    ):
        result = resolve_runtime_storage_cluster(storage, "system", "41", "doris")

    assert result is cluster
    history_filter.assert_called_once_with(
        bk_tenant_id="system",
        table_id="3_bklog.demo",
        cluster_id=41,
    )


def test_runtime_storage_cluster_rejects_unrelated_cluster():
    storage = SimpleNamespace(
        table_id="3_bklog.demo",
        origin_table_id=None,
        storage_cluster_id=40,
    )
    cluster = SimpleNamespace(cluster_id=41, cluster_type="doris")
    history_queryset = Mock()
    history_queryset.exists.return_value = False

    with (
        patch.object(admin_storage.models.ClusterInfo.objects, "get", return_value=cluster),
        patch.object(
            admin_storage.models.StorageClusterRecord.objects,
            "filter",
            return_value=history_queryset,
        ),
        pytest.raises(CustomException, match="不属于当前实体表的历史存储集群"),
    ):
        resolve_runtime_storage_cluster(storage, "system", 41, "doris")


@pytest.mark.parametrize("storage_cluster_id", [True, 41.0])
def test_runtime_storage_cluster_rejects_non_integer_input(storage_cluster_id):
    storage = SimpleNamespace(
        table_id="3_bklog.demo",
        origin_table_id=None,
        storage_cluster_id=40,
    )

    with pytest.raises(CustomException, match="storage_cluster_id 必须是整数"):
        resolve_runtime_storage_cluster(storage, "system", storage_cluster_id, "doris")


def test_clone_storage_with_runtime_cluster_does_not_mutate_persisted_model_instance():
    storage = SimpleNamespace(storage_cluster_id=40, _cluster=SimpleNamespace(cluster_id=40))
    cluster = SimpleNamespace(cluster_id=41)

    runtime_storage = clone_storage_with_runtime_cluster(storage, cluster)

    assert runtime_storage is not storage
    assert runtime_storage.storage_cluster_id == 41
    assert runtime_storage._cluster is cluster
    assert storage.storage_cluster_id == 40


def test_doris_connection_config_supports_read_only_cluster_override():
    storage = admin_storage.models.DorisStorage(
        bk_tenant_id="system",
        table_id="2_bklog.test",
        storage_cluster_id=40,
    )
    history_cluster = admin_storage.models.ClusterInfo(
        bk_tenant_id="system",
        cluster_id=41,
        cluster_name="doris_history",
        cluster_type=admin_storage.models.ClusterInfo.TYPE_DORIS,
        domain_name="doris-history.service.consul",
        port=9031,
        username="history_user",
        password="history_password",
        version="2.0",
    )

    with patch.object(
        admin_storage.models.ClusterInfo.objects,
        "get",
        return_value=history_cluster,
    ) as cluster_get:
        connection_config = storage.get_doris_connection_config(storage_cluster_id=41)

    cluster_get.assert_called_once_with(
        bk_tenant_id="system",
        cluster_id=41,
        cluster_type=admin_storage.models.ClusterInfo.TYPE_DORIS,
    )
    assert connection_config["cluster_id"] == 41
    assert connection_config["host"] == "doris-history.service.consul"
    assert storage.storage_cluster_id == 40


def test_doris_storage_serializer_parses_field_config_mapping():
    warnings = []
    item = _serialize_doris_storage(
        SimpleNamespace(
            table_id="3_bklog.demo",
            bk_tenant_id="system",
            bkbase_table_id="592_bklog_demo",
            origin_table_id="3_bklog.origin",
            source_type="log",
            index_set="3_bklog_demo",
            table_type="primary_table",
            field_config_mapping='{"ip": {"type": "keyword"}}',
            expire_days=30,
            storage_cluster_id=3,
        ),
        warnings,
    )

    assert item["field_config_mapping"]["ip"]["type"] == "keyword"
    assert item["origin_table_id"] == "3_bklog.origin"
    assert warnings == []


def test_doris_virtual_storage_relation_resolves_physical_table_in_same_tenant():
    physical_storage = SimpleNamespace(
        table_id="3_bklog.demo",
        bk_tenant_id="system",
        bkbase_table_id="592_bklog_demo",
        origin_table_id=None,
        source_type="log",
        index_set="3_bklog_demo",
        table_type="primary_table",
        field_config_mapping=None,
        expire_days=30,
        storage_cluster_id=4,
    )
    virtual_storage = SimpleNamespace(
        **{**physical_storage.__dict__, "table_id": "3_bklog.demo_virtual", "origin_table_id": "3_bklog.demo"}
    )
    queryset = Mock()
    queryset.first.return_value = physical_storage

    with (
        patch.object(_doris_storage_manager(), "filter", return_value=queryset) as storage_filter,
        patch.object(admin_storage, "_load_result_table_map", return_value={}),
        patch.object(admin_storage, "_load_cluster_map", return_value={}),
    ):
        relations = _build_doris_relations(virtual_storage, "system")

    storage_filter.assert_called_once_with(bk_tenant_id="system", table_id="3_bklog.demo")
    assert relations["physical_table"]["doris_storage"]["table_id"] == "3_bklog.demo"
    assert relations["virtual_tables"] == []


def test_doris_physical_storage_relation_lists_virtual_tables_in_same_tenant():
    physical_storage = SimpleNamespace(
        table_id="3_bklog.demo",
        bk_tenant_id="system",
        bkbase_table_id="592_bklog_demo",
        origin_table_id=None,
        source_type="log",
        index_set="3_bklog_demo",
        table_type="primary_table",
        field_config_mapping=None,
        expire_days=30,
        storage_cluster_id=4,
    )
    virtual_storage = SimpleNamespace(
        **{**physical_storage.__dict__, "table_id": "3_bklog.demo_virtual", "origin_table_id": "3_bklog.demo"}
    )
    queryset = Mock()
    queryset.order_by.return_value = [virtual_storage]

    with (
        patch.object(_doris_storage_manager(), "filter", return_value=queryset) as storage_filter,
        patch.object(admin_storage, "_load_result_table_map", return_value={}),
        patch.object(admin_storage, "_load_cluster_map", return_value={}),
    ):
        relations = _build_doris_relations(physical_storage, "system")

    storage_filter.assert_called_once_with(bk_tenant_id="system", origin_table_id="3_bklog.demo")
    queryset.order_by.assert_called_once_with("table_id")
    assert relations["physical_table"] is None
    assert [item["doris_storage"]["table_id"] for item in relations["virtual_tables"]] == ["3_bklog.demo_virtual"]


def test_bkbase_result_table_serializer_keeps_model_fields():
    item = _serialize_bkbase_item(
        SimpleNamespace(
            data_link_name="bk_log",
            bkbase_data_name="bk_log",
            storage_type="elasticsearch",
            monitor_table_id="3_bklog.demo",
            storage_cluster_id=3,
            create_time=None,
            last_modify_time=None,
            status="Ok",
            bkbase_table_id="592_bklog_demo",
            bkbase_rt_name="bklog_demo",
            bk_tenant_id="system",
        ),
        {"3_bklog.demo": SimpleNamespace(table_id="3_bklog.demo", bk_tenant_id="system")},
        {
            3: SimpleNamespace(
                cluster_id=3, cluster_name="default-es", display_name="默认 ES", cluster_type="elasticsearch"
            )
        },
    )

    assert item["bkbase_result_table"]["data_link_name"] == "bk_log"
    assert item["bkbase_result_table"]["monitor_table_id"] == "3_bklog.demo"
    assert item["bkbase_result_table"]["status"] == "Ok"
    assert item["result_table"]["table_id"] == "3_bklog.demo"
    assert item["storage_cluster"]["cluster_id"] == 3


def test_query_route_functions_registered():
    for func_name in ["admin.query_route.query", "admin.query_route.refresh"]:
        detail = KernelRPCRegistry.get_function_detail(func_name)
        assert detail is not None
        assert detail["func_name"] == func_name

    query_detail = KernelRPCRegistry.get_function_detail("admin.query_route.query")
    assert "space_uid" in query_detail["params_schema"]
    assert "hgetall" in query_detail["description"]


def test_cluster_info_list_params_schema():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.list")
    assert detail is not None
    assert "cluster_id" in detail["params_schema"]
    assert "ordering" in detail["params_schema"]


def test_bcs_cluster_list_params_schema():
    detail = KernelRPCRegistry.get_function_detail("admin.bcs_cluster.list")
    assert detail is not None
    assert "bk_data_id" in detail["params_schema"]
    assert "status" in detail["params_schema"]


# ----- admin.token.resolve -----

from kernel_api.rpc.functions.admin import token as admin_token  # noqa: E402


class _TokenFirstQuerySet:
    """简单 stub：只支持 filter().filter().order_by().first()，按 token 精确匹配。"""

    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        items = self._items
        for key, value in kwargs.items():
            if key.endswith("__in"):
                field = key[: -len("__in")]
                expected = set(value)
                items = [item for item in items if getattr(item, field, None) in expected]
                continue
            items = [item for item in items if getattr(item, key, None) == value]
        # Q 对象用于 LogGroup 的 token / bk_data_token 兜底分支
        if args:
            from django.db.models import Q

            def matches(item, query):
                connector = getattr(query, "connector", "AND")
                results = []
                for child in query.children:
                    if isinstance(child, Q):
                        results.append(matches(item, child))
                    else:
                        field, expected = child
                        results.append(getattr(item, field, None) == expected)
                return any(results) if connector == "OR" else all(results)

            for query in args:
                if isinstance(query, Q):
                    items = [item for item in items if matches(item, query)]
        return _TokenFirstQuerySet(items)

    def order_by(self, *fields):
        return self

    def first(self):
        return self._items[0] if self._items else None


def _stub_apm_application(token: str = "apm-token"):
    return SimpleNamespace(
        id=1,
        app_name="checkout",
        app_alias="结算服务",
        bk_tenant_id="system",
        bk_biz_id=2,
        token=token,
        update_time=datetime(2026, 5, 28, 10, 0, 0),
    )


def _stub_time_series_group(token: str = "metric-token"):
    return SimpleNamespace(
        time_series_group_id=1573194,
        time_series_group_name="bkop-k8smetricdataid",
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_data_id=1573194,
        table_id="2_bkop_k8s_metric.__default__",
        is_enable=True,
        is_delete=False,
        token=token,
        last_modify_time=datetime(2026, 5, 28, 10, 0, 0),
    )


def _stub_event_group(token: str = "event-token"):
    return SimpleNamespace(
        event_group_id=2001,
        event_group_name="custom_event_checkout",
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_data_id=50070,
        table_id="2_bkmonitor_event.checkout",
        is_enable=True,
        is_delete=False,
        token=token,
        last_modify_time=datetime(2026, 5, 28, 10, 0, 0),
        STORAGE_FIELD_LIST=[],
    )


def _stub_log_group(token: str = "log-token", *, bk_data_token: str | None = None):
    return SimpleNamespace(
        log_group_id=3001,
        log_group_name="apm_log_checkout",
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_data_id=50020,
        table_id="3_bklog.demo",
        is_enable=True,
        is_delete=False,
        token=token,
        bk_data_token=bk_data_token,
        last_modify_time=datetime(2026, 5, 28, 10, 0, 0),
    )


def _patch_token_models(
    monkeypatch,
    *,
    apm_apps=(),
    ts_groups=(),
    event_groups=(),
    log_groups=(),
    log_datasource=None,
    apm_metric_datasources=(),
    apm_trace_datasources=(),
    apm_log_datasources=(),
    apm_profile_datasources=(),
):
    monkeypatch.setattr(
        admin_token.apm_models,
        "ApmApplication",
        SimpleNamespace(objects=_TokenFirstQuerySet(apm_apps)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.apm_models,
        "MetricDataSource",
        SimpleNamespace(objects=_TokenFirstQuerySet(apm_metric_datasources)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.apm_models,
        "TraceDataSource",
        SimpleNamespace(objects=_TokenFirstQuerySet(apm_trace_datasources)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.apm_models,
        "LogDataSource",
        SimpleNamespace(objects=_TokenFirstQuerySet(apm_log_datasources)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.apm_models,
        "ProfileDataSource",
        SimpleNamespace(objects=_TokenFirstQuerySet(apm_profile_datasources)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.metadata_models,
        "TimeSeriesGroup",
        SimpleNamespace(objects=_TokenFirstQuerySet(ts_groups)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.metadata_models,
        "EventGroup",
        SimpleNamespace(objects=_TokenFirstQuerySet(event_groups)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.metadata_models,
        "LogGroup",
        SimpleNamespace(objects=_TokenFirstQuerySet(log_groups)),
        raising=False,
    )
    monkeypatch.setattr(
        admin_token.metadata_models,
        "DataSource",
        SimpleNamespace(objects=_TokenFirstQuerySet([log_datasource] if log_datasource else [])),
        raising=False,
    )
    # 跳过 datasource / service count 的内部查询，避免触达真实数据库
    monkeypatch.setattr(
        admin_token,
        "_load_apm_datasource_maps",
        lambda apps: {datasource_type: {} for datasource_type in admin_apm.DATASOURCE_TYPES},
    )
    monkeypatch.setattr(admin_token, "_load_service_count_map", lambda apps: {})


def test_admin_token_resolve_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.token.resolve")
    assert detail is not None
    assert "token" in detail["params_schema"]
    assert detail["params_schema"]["bk_tenant_id"]


def test_admin_token_resolve_returns_unmatched_for_blank_token():
    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": ""})

    assert result["meta"]["safety_level"] == "read"
    assert result["data"]["matched"] is False
    assert result["data"]["kind"] is None
    assert result["data"]["apm_application"] is None
    assert result["data"]["custom_report"] is None
    assert "token 为空" in result["data"]["warnings"]


def test_admin_token_resolve_hits_apm_application(monkeypatch):
    apm_app = _stub_apm_application(token="bkapm_1_a1b2c3d4e5f6")
    _patch_token_models(monkeypatch, apm_apps=[apm_app])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": "bkapm_1_a1b2c3d4e5f6"})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "apm"
    assert result["data"]["apm_application"]["application_id"] == 1
    assert result["data"]["apm_application"]["apm_token"] == "bkapm_1_a1b2c3d4e5f6"
    assert result["data"]["custom_report"] is None


def test_admin_token_resolve_hits_time_series_group(monkeypatch):
    ts_group = _stub_time_series_group(token="bkmetric_1573194_a1b2c3d4e5f6")
    _patch_token_models(monkeypatch, ts_groups=[ts_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": "bkmetric_1573194_a1b2c3d4e5f6"})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "custom_metric"
    assert result["data"]["custom_report"]["report_type"] == "custom_metric"
    assert result["data"]["custom_report"]["group_id"] == 1573194
    assert result["data"]["custom_report"]["token"] == "bkmetric_1573194_a1b2c3d4e5f6"
    assert result["data"]["apm_application"] is None


def test_admin_token_resolve_hits_event_group(monkeypatch):
    event_group = _stub_event_group(token="bkevent_2001_e5f6a1b2c3d4")
    _patch_token_models(monkeypatch, event_groups=[event_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": "bkevent_2001_e5f6a1b2c3d4"})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "custom_event"
    assert result["data"]["custom_report"]["report_type"] == "custom_event"
    assert result["data"]["custom_report"]["group_id"] == 2001


def test_admin_token_resolve_falls_back_to_log_group_legacy_field(monkeypatch):
    # 老数据：token 写到了已废弃的 bk_data_token 字段
    log_group = _stub_log_group(token="", bk_data_token="bklog_3001_legacy")
    _patch_token_models(monkeypatch, log_groups=[log_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": "bklog_3001_legacy"})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "custom_log"
    assert result["data"]["custom_report"]["report_type"] == "custom_log"
    assert result["data"]["custom_report"]["token"] == "bklog_3001_legacy"


def test_admin_token_resolve_returns_unmatched_when_nothing_found(monkeypatch):
    _patch_token_models(monkeypatch)

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": "definitely-missing"})

    assert result["data"]["matched"] is False
    assert result["data"]["kind"] is None
    assert result["data"]["token"] == "definitely-missing"
    assert result["data"]["apm_application"] is None
    assert result["data"]["custom_report"] is None


# ----- AES 反向解析 fallback -----


def _build_v0_apm_token(metric_data_id, trace_data_id, log_data_id, bk_biz_id, app_name):
    from bkmonitor.utils.cipher import transform_data_id_to_token

    return transform_data_id_to_token(
        metric_data_id=metric_data_id,
        trace_data_id=trace_data_id,
        log_data_id=log_data_id,
        bk_biz_id=bk_biz_id,
        app_name=app_name,
    )


def _build_v1_apm_token(metric_data_id, trace_data_id, log_data_id, profile_data_id, bk_biz_id, app_name):
    from bkmonitor.utils.cipher import transform_data_id_to_v1_token

    return transform_data_id_to_v1_token(
        metric_data_id=metric_data_id,
        trace_data_id=trace_data_id,
        log_data_id=log_data_id,
        profile_data_id=profile_data_id,
        bk_biz_id=bk_biz_id,
        app_name=app_name,
    )


def test_parse_apm_token_returns_none_for_garbage():
    assert admin_token.parse_apm_token("not-a-token") is None
    assert admin_token.parse_apm_token("") is None


def test_parse_apm_token_handles_v0_token():
    token = _build_v0_apm_token(
        metric_data_id=1001,
        trace_data_id=1002,
        log_data_id=1003,
        bk_biz_id=42,
        app_name="checkout",
    )

    parsed = admin_token.parse_apm_token(token)

    assert parsed is not None
    assert parsed.version == "v0"
    assert parsed.metric_data_id == 1001
    assert parsed.trace_data_id == 1002
    assert parsed.log_data_id == 1003
    assert parsed.profile_data_id == -1
    assert parsed.bk_biz_id == 42
    assert parsed.app_name == "checkout"


def test_parse_apm_token_handles_v1_token():
    token = _build_v1_apm_token(
        metric_data_id=2001,
        trace_data_id=2002,
        log_data_id=2003,
        profile_data_id=2004,
        bk_biz_id=88,
        app_name="payment",
    )

    parsed = admin_token.parse_apm_token(token)

    assert parsed is not None
    assert parsed.version == "v1"
    assert parsed.metric_data_id == 2001
    assert parsed.profile_data_id == 2004
    assert parsed.bk_biz_id == 88
    assert parsed.app_name == "payment"


def test_admin_token_resolve_aes_fallback_finds_app_by_biz_and_name(monkeypatch):
    apm_app = _stub_apm_application(token="bkapm_db_token")
    apm_app.bk_biz_id = 42
    apm_app.app_name = "checkout"
    token = _build_v1_apm_token(
        metric_data_id=50010,
        trace_data_id=56020,
        log_data_id=50020,
        profile_data_id=57020,
        bk_biz_id=42,
        app_name="checkout",
    )
    # DB 字段精确匹配 miss（apm_app.token != AES token），需要走解密 fallback
    _patch_token_models(monkeypatch, apm_apps=[apm_app])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "apm"
    assert result["data"]["apm_application"]["application_id"] == 1
    assert result["data"]["apm_application"]["app_name"] == "checkout"
    assert result["data"]["custom_report"] is None
    assert "AES 反向解析" in result["data"]["warnings"][0]


def test_admin_token_resolve_aes_fallback_finds_app_via_data_id_when_app_name_renamed(monkeypatch):
    """app_name 在 token 加密之后被重命名 → biz+name miss，但 data_id 仍能反查回应用。

    场景前提：token 里含 trace_data_id（v1 完整 APM token），所以走 APM 分支；
    然后 (bk_biz_id, app_name) 精确匹配落空，靠 TraceDataSource.bk_data_id 回查应用。
    """
    apm_app = _stub_apm_application(token="bkapm_db_token")
    apm_app.bk_biz_id = 42
    apm_app.app_name = "checkout-renamed"  # 与 token 中编码的 app_name 不同
    trace_ds = SimpleNamespace(bk_data_id=56020, bk_biz_id=42, app_name="checkout-renamed")
    token = _build_v1_apm_token(
        metric_data_id=50010,
        trace_data_id=56020,
        log_data_id=-1,
        profile_data_id=-1,
        bk_biz_id=42,
        app_name="checkout",  # 旧 app_name
    )

    _patch_token_models(
        monkeypatch,
        apm_apps=[apm_app],
        apm_trace_datasources=[trace_ds],
    )

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "apm"
    assert result["data"]["apm_application"]["app_name"] == "checkout-renamed"


def test_admin_token_resolve_aes_fallback_returns_unmatched_when_decryptable_but_no_app(monkeypatch):
    """解密成功但应用已被删除，返回 unmatched 而非 500。"""
    token = _build_v1_apm_token(
        metric_data_id=99991,
        trace_data_id=99992,
        log_data_id=99993,
        profile_data_id=99994,
        bk_biz_id=999,
        app_name="ghost",
    )
    _patch_token_models(monkeypatch)  # 数据库里啥都没有

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is False
    assert result["data"]["kind"] is None
    assert result["data"]["apm_application"] is None
    assert result["data"]["custom_report"] is None


def test_admin_token_resolve_aes_fallback_metric_only_routes_to_time_series_group(monkeypatch):
    """解密后仅含 metric_data_id（无 trace 无 log）→ 自定义指标。"""
    ts_group = _stub_time_series_group(token="dummy-db-token")
    ts_group.bk_data_id = 1573194
    token = _build_v0_apm_token(
        metric_data_id=1573194,
        trace_data_id=-1,
        log_data_id=-1,
        bk_biz_id=2,
        app_name="bkop-k8smetricdataid",
    )
    _patch_token_models(monkeypatch, ts_groups=[ts_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "custom_metric"
    assert result["data"]["custom_report"]["group_id"] == 1573194
    assert result["data"]["apm_application"] is None
    assert "AES 反向解析" in result["data"]["warnings"][0]


def test_admin_token_resolve_aes_fallback_log_only_routes_to_log_group(monkeypatch):
    """解密后仅含 log_data_id（无 trace 无 metric）→ 自定义日志。"""
    log_group = _stub_log_group(token="dummy-db-token")
    log_group.bk_data_id = 50020
    token = _build_v0_apm_token(
        metric_data_id=-1,
        trace_data_id=-1,
        log_data_id=50020,
        bk_biz_id=2,
        app_name="apm_log_checkout",
    )
    _patch_token_models(monkeypatch, log_groups=[log_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is True
    assert result["data"]["kind"] == "custom_log"
    assert result["data"]["custom_report"]["report_type"] == "custom_log"
    assert result["data"]["apm_application"] is None
    assert "AES 反向解析" in result["data"]["warnings"][0]


def test_admin_token_resolve_aes_fallback_metric_and_log_combo_returns_unmatched(monkeypatch):
    """解密后 metric+log 同时存在但无 trace → 不属于任何明确分类，返回 unmatched。"""
    ts_group = _stub_time_series_group()
    ts_group.bk_data_id = 1573194
    log_group = _stub_log_group()
    log_group.bk_data_id = 50020
    token = _build_v0_apm_token(
        metric_data_id=1573194,
        trace_data_id=-1,
        log_data_id=50020,
        bk_biz_id=2,
        app_name="ambiguous",
    )
    _patch_token_models(monkeypatch, ts_groups=[ts_group], log_groups=[log_group])

    result = admin_token.resolve_token({"bk_tenant_id": "system", "token": token})

    assert result["data"]["matched"] is False
    assert result["data"]["kind"] is None
    assert result["data"]["apm_application"] is None
    assert result["data"]["custom_report"] is None
