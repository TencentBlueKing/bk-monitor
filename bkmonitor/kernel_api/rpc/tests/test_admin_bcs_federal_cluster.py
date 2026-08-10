"""BCS 联邦集群 Admin RPC 测试。"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin import bcs_federal_cluster as admin_federal
from metadata import models

pytestmark = pytest.mark.django_db


def _create_cluster(cluster_id: str, *, tenant: str = "system", biz_id: int = 2, metric_data_id: int = 0):
    return models.BCSClusterInfo.objects.create(
        cluster_id=cluster_id,
        bcs_api_cluster_id=cluster_id,
        bk_tenant_id=tenant,
        bk_biz_id=biz_id,
        project_id=f"project-{biz_id}",
        status="RUNNING",
        domain_name="bcs-api.example.com",
        port=443,
        server_address_path="/clusters",
        api_key_content="test-token",
        K8sMetricDataID=metric_data_id,
        K8sEventDataID=metric_data_id + 1 if metric_data_id else 0,
    )


def _create_topology(
    fed_cluster_id: str,
    sub_cluster_id: str,
    *,
    host_cluster_id: str = "BCS-K8S-HOST",
    namespaces: list[str] | None = None,
    is_deleted: bool = False,
):
    return models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id=fed_cluster_id,
        host_cluster_id=host_cluster_id,
        sub_cluster_id=sub_cluster_id,
        fed_namespaces=namespaces or [],
        fed_builtin_metric_table_id=f"{fed_cluster_id}.metric",
        fed_builtin_event_table_id=f"{fed_cluster_id}.event",
        is_deleted=is_deleted,
    )


def test_federal_cluster_list_uses_bcs_cluster_tenant_scope():
    _create_cluster("FED-SYSTEM", tenant="system", biz_id=2)
    _create_cluster("FED-OTHER", tenant="tenant-b", biz_id=3)
    _create_cluster("FED-DELETED", tenant="system", biz_id=4)
    _create_topology("FED-SYSTEM", "SUB-1")
    _create_topology("FED-OTHER", "SUB-2")
    _create_topology("FED-DELETED", "SUB-3", is_deleted=True)

    result = admin_federal.list_bcs_federal_clusters({"bk_tenant_id": "system", "page": 1, "page_size": 20})

    assert result["data"]["total"] == 1
    assert result["data"]["items"][0]["fed_cluster_id"] == "FED-SYSTEM"
    assert result["data"]["items"][0]["bk_tenant_id"] == "system"
    assert result["meta"]["safety_level"] == "read"


def test_federal_cluster_list_filters_host_and_sub_cluster():
    _create_cluster("FED-A")
    _create_cluster("FED-B")
    _create_topology("FED-A", "SUB-A", host_cluster_id="HOST-A")
    _create_topology("FED-B", "SUB-B", host_cluster_id="HOST-B")

    host_result = admin_federal.list_bcs_federal_clusters({"host_cluster_id": "HOST-B", "page": 1, "page_size": 20})
    sub_result = admin_federal.list_bcs_federal_clusters({"sub_cluster_id": "SUB-A", "page": 1, "page_size": 20})

    assert [item["fed_cluster_id"] for item in host_result["data"]["items"]] == ["FED-B"]
    assert [item["fed_cluster_id"] for item in sub_result["data"]["items"]] == ["FED-A"]


def test_federal_cluster_detail_checks_tenant_before_topology():
    _create_cluster("FED-A", tenant="tenant-a")
    _create_topology("FED-A", "SUB-A")

    with pytest.raises(CustomException, match="未找到租户 tenant-b"):
        admin_federal.get_bcs_federal_cluster_detail({"bk_tenant_id": "tenant-b", "fed_cluster_id": "FED-A"})


def test_federal_cluster_detail_returns_database_summary():
    _create_cluster("FED-A", metric_data_id=1000)
    _create_cluster("HOST-A", metric_data_id=2000)
    _create_topology("FED-A", "SUB-A", host_cluster_id="HOST-A")
    _create_topology("FED-A", "SUB-B", host_cluster_id="HOST-A")

    result = admin_federal.get_bcs_federal_cluster_detail({"bk_tenant_id": "system", "fed_cluster_id": "FED-A"})

    assert result["data"]["sub_cluster_count"] == 2
    assert result["data"]["proxy_cluster"]["K8sMetricDataID"] == 1000
    assert result["data"]["host_cluster"]["cluster_id"] == "HOST-A"
    assert result["data"]["builtin_result_tables"]["metric_table_id"] == "FED-A.metric"


def test_federal_sub_cluster_list_batches_cluster_info_and_limits_namespace_preview(django_assert_num_queries):
    _create_cluster("FED-A")
    _create_cluster("SUB-A", metric_data_id=3000)
    _create_topology("FED-A", "SUB-A", namespaces=["zeta", "alpha", "beta", "gamma"])
    _create_topology("FED-A", "SUB-MISSING", namespaces=["default"])

    with django_assert_num_queries(5):
        result = admin_federal.list_bcs_federal_sub_clusters(
            {"bk_tenant_id": "system", "fed_cluster_id": "FED-A", "page": 1, "page_size": 20}
        )

    item = result["data"]["items"][0]
    assert item["namespace_count"] == 4
    assert item["namespace_preview"] == ["alpha", "beta", "gamma"]
    assert item["cluster_info"]["K8sMetricDataID"] == 3000
    assert result["data"]["items"][1]["cluster_info"] is None


def test_federal_sub_cluster_namespace_list_searches_and_paginates_one_cluster():
    _create_cluster("FED-A")
    _create_topology("FED-A", "SUB-A", namespaces=["prod-b", "dev", "prod-a"])
    _create_topology("FED-A", "SUB-B", namespaces=["prod-other"])

    result = admin_federal.list_bcs_federal_sub_cluster_namespaces(
        {
            "bk_tenant_id": "system",
            "fed_cluster_id": "FED-A",
            "sub_cluster_id": "SUB-A",
            "namespace": "prod",
            "page": 2,
            "page_size": 1,
        }
    )

    assert result["data"] == {
        "items": [{"namespace": "prod-b"}],
        "page": 2,
        "page_size": 1,
        "total": 2,
    }


def test_federal_list_and_detail_do_not_select_namespace_payload():
    _create_cluster("FED-A")
    _create_topology("FED-A", "SUB-A", namespaces=[f"namespace-{index}" for index in range(100)])

    with CaptureQueriesContext(connection) as captured_queries:
        admin_federal.list_bcs_federal_clusters({"bk_tenant_id": "system", "page": 1, "page_size": 20})
        admin_federal.get_bcs_federal_cluster_detail({"bk_tenant_id": "system", "fed_cluster_id": "FED-A"})

    assert all("fed_namespaces" not in query["sql"] for query in captured_queries.captured_queries)


def test_federal_cluster_operations_expose_schema_and_examples():
    operation_names = [
        admin_federal.FUNC_BCS_FEDERAL_CLUSTER_LIST,
        admin_federal.FUNC_BCS_FEDERAL_CLUSTER_DETAIL,
        admin_federal.FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_LIST,
        admin_federal.FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_NAMESPACE_LIST,
    ]

    for operation_name in operation_names:
        detail = KernelRPCRegistry.get_function_detail(operation_name)
        assert detail is not None
        assert detail["params_schema"]
        assert detail["example_params"]
