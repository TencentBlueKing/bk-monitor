"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kernel_api.rpc.functions.admin.bcs_cluster import _serialize_bcs_cluster
from kernel_api.rpc.functions.admin.api_auth_token import (
    _normalize_biz_ids,
    _normalize_namespaces,
    _serialize_api_auth_token,
)
from kernel_api.rpc.functions.admin.cluster_info import _build_es_cluster_overview, _serialize_cluster_info
from kernel_api.rpc.functions.admin.datasource import _serialize_datasource
from kernel_api.rpc.functions.admin.es_storage import (
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
from kernel_api.rpc.functions.admin import storage as admin_storage
from kernel_api.rpc.functions.admin.storage import (
    get_doris_storage_latest_records,
    get_doris_storage_physical_metadata,
    _serialize_bkbase_item,
    _serialize_doris_storage,
)
from kernel_api.rpc.functions.admin.uptime_check import _summarize_subscription
from kernel_api.rpc.registry import KernelRPCRegistry


def _doris_storage_manager():
    return admin_storage.models.DorisStorage.objects


def test_admin_rpc_functions_registered_by_builtin_loader():
    func_names = {function["func_name"] for function in KernelRPCRegistry.list_functions()}

    assert {
        "admin.datasource.list",
        "admin.datasource.detail",
        "admin.result_table.list",
        "admin.result_table.detail",
        "admin.result_table.field_list",
        "admin.result_table.field_options",
        "admin.cluster_info.list",
        "admin.cluster_info.detail",
        "admin.bcs_cluster.list",
        "admin.bcs_cluster.detail",
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
    } <= func_names

    detail = KernelRPCRegistry.get_function_detail("admin.result_table.detail")
    assert detail is not None
    assert detail["params_schema"]["include"].find("fields") != -1


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
                                "target_host_list": ["30.167.62.75"],
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
    storage = SimpleNamespace(
        query_physical_storage_metadata=lambda: {
            "physical_metadata": {
                "tables": [{"CREATE_TIME": datetime(2026, 5, 12, 10, 30, 0), "TABLE_ROWS": Decimal("3")}]
            },
            "warnings": [],
            "errors": [],
        }
    )

    with patch.object(_doris_storage_manager(), "get", return_value=storage):
        response = get_doris_storage_physical_metadata({"bk_tenant_id": "system", "table_id": "2_bklog.demo"})

    assert response["meta"]["safety_level"] == "inspect"
    assert response["meta"]["requested_safety_level"] == "inspect"
    assert response["data"]["physical_metadata"]["tables"][0]["CREATE_TIME"] == "2026-05-12 10:30:00"
    assert response["data"]["physical_metadata"]["tables"][0]["TABLE_ROWS"] == "3"


def test_doris_storage_latest_records_rpc_passes_limit_and_order_field():
    calls = []

    def query_latest_physical_storage_records(*, limit, order_field):
        calls.append({"limit": limit, "order_field": order_field})
        return {"records": [{"value": "latest"}], "warnings": [], "errors": []}

    storage = SimpleNamespace(query_latest_physical_storage_records=query_latest_physical_storage_records)

    with patch.object(_doris_storage_manager(), "get", return_value=storage):
        response = get_doris_storage_latest_records(
            {"bk_tenant_id": "system", "table_id": "2_bklog.demo", "limit": "200", "order_field": "time"}
        )

    assert calls == [{"limit": 100, "order_field": "time"}]
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
        default_settings={},
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
    assert "custom_option" not in item


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


def test_cluster_info_list_supports_lightweight_include():
    detail = KernelRPCRegistry.get_function_detail("admin.cluster_info.list")
    assert detail is not None
    assert "include" in detail["params_schema"]
    assert "associated_counts" in detail["params_schema"]["include"]


def test_bcs_cluster_detail_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.bcs_cluster.detail")
    assert detail is not None
    assert detail["func_name"] == "admin.bcs_cluster.detail"


def test_kafka_sample_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.datasource.kafka_sample")
    assert detail is not None
    assert detail["func_name"] == "admin.datasource.kafka_sample"
    assert "bk_data_id" in detail["params_schema"]


def test_custom_report_refresh_metrics_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.custom_report.refresh_metrics")
    assert detail is not None
    assert detail["func_name"] == "admin.custom_report.refresh_metrics"
    assert "write" in detail["description"]
    assert "expired_time" in detail["params_schema"]


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
    rotate_detail = KernelRPCRegistry.get_function_detail("admin.es_storage.rotate_aliases")
    assert "write" in rotate_detail["description"]
    assert "traceback" in rotate_detail["description"]


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
    assert "id" in KernelRPCRegistry.get_function_detail("admin.vm_storage.detail")["params_schema"]
    assert (
        "data_link_name" in KernelRPCRegistry.get_function_detail("admin.bkbase_result_table.detail")["params_schema"]
    )


def test_doris_storage_serializer_parses_field_config_mapping():
    warnings = []
    item = _serialize_doris_storage(
        SimpleNamespace(
            table_id="3_bklog.demo",
            bk_tenant_id="system",
            bkbase_table_id="592_bklog_demo",
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
    assert warnings == []


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
    assert "ordering" in detail["params_schema"]


def test_bcs_cluster_list_params_schema():
    detail = KernelRPCRegistry.get_function_detail("admin.bcs_cluster.list")
    assert detail is not None
    assert "bk_data_id" in detail["params_schema"]
    assert "status" in detail["params_schema"]
