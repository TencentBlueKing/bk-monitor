import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from kernel_api.rpc.functions.admin.metric_migration import list_metric_migration_datasources
from kernel_api.rpc.registry import KernelRPCRegistry
from metadata import models
from monitor_web.models.plugin import CollectorPluginMeta

pytestmark = pytest.mark.django_db


def _create_datasource(
    bk_data_id: int,
    *,
    data_name: str,
    created_from: str = "bkgse",
    type_label: str = "time_series",
    tenant_id: str = "system",
    enabled: bool = True,
) -> models.DataSource:
    return models.DataSource.objects.create(
        bk_data_id=bk_data_id,
        bk_tenant_id=tenant_id,
        data_name=data_name,
        data_description=data_name,
        mq_cluster_id=1,
        mq_config_id=bk_data_id,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=True,
        creator="admin",
        last_modify_user="admin",
        type_label=type_label,
        source_label="custom",
        is_enable=enabled,
        transfer_cluster_id="default",
        created_from=created_from,
    )


def _create_result_table(
    bk_data_id: int,
    table_id: str,
    *,
    bk_biz_id: int = 2,
    is_enable: bool = True,
    is_deleted: bool = False,
    tenant_id: str = "system",
) -> models.ResultTable:
    result_table = models.ResultTable.objects.create(
        table_id=table_id,
        bk_tenant_id=tenant_id,
        table_name_zh=table_id,
        is_custom_table=True,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage="influxdb",
        creator="admin",
        last_modify_user="admin",
        bk_biz_id=bk_biz_id,
        is_enable=is_enable,
        is_deleted=is_deleted,
        label="other",
        data_label=table_id.split(".", 1)[0],
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=tenant_id,
        bk_data_id=bk_data_id,
        table_id=table_id,
        creator="admin",
    )
    return result_table


def _create_custom_group(bk_data_id: int, table_id: str, *, bk_biz_id: int = 2) -> None:
    models.TimeSeriesGroup.objects.create(
        bk_tenant_id="system",
        bk_data_id=bk_data_id,
        bk_biz_id=bk_biz_id,
        table_id=table_id,
        time_series_group_name=f"group_{bk_data_id}",
        label="other",
        creator="admin",
        last_modify_user="admin",
    )


def test_metric_migration_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.datasource.metric_migration_list")

    assert detail is not None
    assert "pagination_mode" in detail["params_schema"]


def test_metric_migration_list_filters_scope_and_loads_overlapping_categories():
    custom = _create_datasource(71001, data_name="custom_metric_demo")
    _create_result_table(custom.bk_data_id, "custom_metric_demo.__default__")
    _create_custom_group(custom.bk_data_id, "custom_metric_demo.__default__")

    plugin_ds = _create_datasource(71002, data_name="exporter_demo_plugin")
    CollectorPluginMeta.objects.create(
        bk_tenant_id="system",
        plugin_id="demo_plugin",
        plugin_type="Exporter",
        bk_biz_id=2,
        tag="os",
        label="other",
    )
    _create_result_table(plugin_ds.bk_data_id, "exporter_demo_plugin.__default__")

    bcs_ds = _create_datasource(71003, data_name="bcs_metric_demo")
    _create_custom_group(bcs_ds.bk_data_id, "bcs_metric_demo.__default__")
    models.BCSClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id="BCS-K8S-TEST",
        bcs_api_cluster_id="BCS-K8S-TEST",
        bk_biz_id=2,
        project_id="project",
        domain_name="example.com",
        port=443,
        server_address_path="/",
        api_key_content="masked",
        K8sMetricDataID=bcs_ds.bk_data_id,
        creator="admin",
        last_modify_user="admin",
    )

    _create_datasource(71004, data_name="v4_metric", created_from="bkdata")
    _create_datasource(71005, data_name="bkgse_log", type_label="log")

    response = list_metric_migration_datasources(
        {"bk_tenant_id": "system", "page": 1, "page_size": 100, "include_summary": False}
    )["data"]
    items = {item["datasource"]["bk_data_id"]: item for item in response["items"]}

    assert set(items) == {71001, 71002, 71003}
    assert items[71001]["categories"] == ["custom_metric"]
    assert items[71002]["categories"] == ["plugin_metric"]
    assert items[71002]["plugins"][0]["plugin_id"] == "demo_plugin"
    assert items[71003]["categories"] == ["custom_metric", "bcs_metric"]
    assert items[71003]["bcs_clusters"][0]["cluster_id"] == "BCS-K8S-TEST"


def test_metric_migration_relation_filter_runs_before_pagination():
    _create_datasource(71101, data_name="enabled_rt")
    _create_result_table(71101, "demo.enabled", is_enable=True)
    _create_datasource(71102, data_name="deleted_rt")
    _create_result_table(71102, "demo.deleted", is_enable=False, is_deleted=True)

    response = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "result_table_is_deleted": True,
            "page": 1,
            "page_size": 1,
            "include_summary": False,
        }
    )["data"]

    assert response["total"] == 1
    assert response["items"][0]["datasource"]["bk_data_id"] == 71102
    assert {warning["code"] for warning in response["items"][0]["warnings"]} >= {"RESULT_TABLE_DELETED"}


def test_metric_migration_table_filter_keeps_relation_with_missing_result_table():
    _create_datasource(71103, data_name="missing_rt")
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=71103,
        table_id="missing.__default__",
        creator="admin",
    )

    response = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "table_ids": ["missing.__default__"],
            "page": 1,
            "page_size": 20,
            "include_summary": False,
        }
    )["data"]

    assert response["total"] == 1
    assert response["items"][0]["result_tables"] == [
        {
            "table_id": "missing.__default__",
            "bk_tenant_id": "system",
            "table_name_zh": None,
            "bk_biz_id": None,
            "data_label": None,
            "label": None,
            "default_storage": None,
            "is_enable": None,
            "is_deleted": None,
            "record_exists": False,
        }
    ]


def test_metric_migration_keeps_zero_and_multiple_result_tables():
    _create_datasource(71104, data_name="without_rt")
    _create_datasource(71105, data_name="multiple_rt")
    _create_result_table(71105, "multiple.first")
    _create_result_table(71105, "multiple.second")

    response = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "bk_data_ids": [71104, 71105],
            "page": 1,
            "page_size": 20,
            "include_summary": False,
        }
    )["data"]
    items = {item["datasource"]["bk_data_id"]: item for item in response["items"]}

    assert items[71104]["result_tables"] == []
    assert "RESULT_TABLE_RELATION_MISSING" in {warning["code"] for warning in items[71104]["warnings"]}
    assert [item["table_id"] for item in items[71105]["result_tables"]] == [
        "multiple.first",
        "multiple.second",
    ]


def test_metric_migration_associations_are_tenant_isolated():
    _create_datasource(71106, data_name="system_metric")
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=71106,
        table_id="shared.metric",
        creator="admin",
    )
    _create_datasource(71107, data_name="tenant_metric", tenant_id="tenant-a")
    _create_result_table(71107, "shared.metric", tenant_id="tenant-a")

    response = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "bk_data_ids": [71106, 71107],
            "page": 1,
            "page_size": 20,
            "include_summary": False,
        }
    )["data"]

    assert [item["datasource"]["bk_data_id"] for item in response["items"]] == [71106]
    assert response["items"][0]["result_tables"][0]["record_exists"] is False


def test_metric_migration_maps_shared_process_and_missing_space():
    _create_datasource(71108, data_name="2_custom_time_series_process_perf")
    CollectorPluginMeta.objects.create(
        bk_tenant_id="system",
        plugin_id="process_demo",
        plugin_type="Process",
        bk_biz_id=2,
        tag="os",
        label="other",
    )
    models.SpaceDataSource.objects.create(
        bk_tenant_id="system",
        bk_data_id=71108,
        space_type_id="bkcc",
        space_id="2",
    )

    response = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "bk_data_ids": [71108],
            "page": 1,
            "page_size": 20,
            "include_summary": False,
        }
    )["data"]
    item = response["items"][0]

    assert item["categories"] == ["plugin_metric"]
    assert item["plugins"][0]["relation_kind"] == "shared_process"
    assert item["spaces"][0]["record_exists"] is False
    assert "SPACE_RECORD_MISSING" in {warning["code"] for warning in item["warnings"]}


def test_metric_migration_cursor_honors_snapshot_upper_bound():
    for data_id in (71201, 71202, 71203):
        _create_datasource(data_id, data_name=f"metric_{data_id}")

    first = list_metric_migration_datasources(
        {
            "bk_tenant_id": "system",
            "pagination_mode": "cursor",
            "cursor": 0,
            "page_size": 1,
        }
    )["data"]
    assert first["items"][0]["datasource"]["bk_data_id"] == 71201
    assert first["snapshot_max_bk_data_id"] == 71203

    _create_datasource(71204, data_name="created_during_export")
    seen = [71201]
    cursor = first["next_cursor"]
    while first["has_more"]:
        first = list_metric_migration_datasources(
            {
                "bk_tenant_id": "system",
                "pagination_mode": "cursor",
                "cursor": cursor,
                "snapshot_max_bk_data_id": 71203,
                "page_size": 1,
            }
        )["data"]
        seen.extend(item["datasource"]["bk_data_id"] for item in first["items"])
        cursor = first["next_cursor"]

    assert seen == [71201, 71202, 71203]


def test_metric_migration_page_associations_do_not_query_per_datasource():
    for data_id in range(71301, 71306):
        _create_datasource(data_id, data_name=f"batch_{data_id}")
        _create_result_table(data_id, f"batch.{data_id}")

    with CaptureQueriesContext(connection) as queries:
        response = list_metric_migration_datasources(
            {"bk_tenant_id": "system", "page": 1, "page_size": 100, "include_summary": False}
        )

    assert len(response["data"]["items"]) == 5
    assert len(queries) <= 16
