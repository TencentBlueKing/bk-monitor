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

from kernel_api.rpc.functions.admin.bcs_cluster import _serialize_bcs_cluster
from kernel_api.rpc.functions.admin.cluster_info import _serialize_cluster_info
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
from kernel_api.rpc.registry import KernelRPCRegistry


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
        "admin.query_route.query",
        "admin.query_route.refresh",
    } <= func_names

    detail = KernelRPCRegistry.get_function_detail("admin.result_table.detail")
    assert detail is not None
    assert detail["params_schema"]["include"].find("fields") != -1


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


def test_es_storage_functions_registered():
    for func_name in [
        "admin.es_storage.list",
        "admin.es_storage.detail",
        "admin.es_storage.runtime_overview",
        "admin.es_storage.sample",
    ]:
        detail = KernelRPCRegistry.get_function_detail(func_name)
        assert detail is not None
        assert detail["func_name"] == func_name

    runtime_detail = KernelRPCRegistry.get_function_detail("admin.es_storage.runtime_overview")
    assert "inspect" in runtime_detail["description"]
    assert "table_id" in runtime_detail["params_schema"]


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
    assert "status" in detail["params_schema"]
