"""
``QueryDataLinkMetadataResource`` 真实租户解析回归测试.
"""

from unittest import mock

import pytest

from metadata import models
from metadata.resources.bkdata_link import QueryDataLinkMetadataResource


pytestmark = pytest.mark.django_db(databases="__all__")


def _create_query_metadata_record(
    *,
    bk_tenant_id="tenant-real",
    bk_data_id=600100,
    table_id="600100_bkmonitor_time_series.__default__",
    data_name="tenant_real_data",
    vm_result_table_id=None,
    created_from="bkgse",
):
    ds = models.DataSource.objects.create(
        bk_data_id=bk_data_id,
        bk_tenant_id=bk_tenant_id,
        data_name=data_name,
        data_description="tenant test data",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        creator="admin",
        last_modify_user="admin",
        created_from=created_from,
    )
    rt = models.ResultTable.objects.create(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        table_name_zh="tenant test table",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_INFLUXDB,
        creator="admin",
        last_modify_user="admin",
        bk_biz_id=0,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=bk_data_id,
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        creator="admin",
    )
    if vm_result_table_id:
        models.AccessVMRecord.objects.create(
            result_table_id=table_id,
            bk_base_data_id=bk_data_id + 100000,
            vm_result_table_id=vm_result_table_id,
            bk_tenant_id=bk_tenant_id,
        )
    return ds, rt


def test_bk_data_id_uses_data_source_tenant_when_request_tenant_is_wrong():
    _create_query_metadata_record(bk_tenant_id="tenant-real", bk_data_id=600101)

    with mock.patch.object(QueryDataLinkMetadataResource, "_enrich_with_runtime"):
        rows = QueryDataLinkMetadataResource().perform_request({"bk_tenant_id": "tenant-wrong", "bk_data_id": "600101"})

    assert len(rows) == 1
    assert rows[0]["bk_tenant_id"] == "tenant-real"
    assert rows[0]["data_id"] == 600101


def test_result_table_id_uses_dsrt_tenant_when_request_tenant_is_wrong():
    table_id = "600102_bkmonitor_time_series.__default__"
    _create_query_metadata_record(bk_tenant_id="tenant-real", bk_data_id=600102, table_id=table_id)

    with mock.patch.object(QueryDataLinkMetadataResource, "_enrich_with_runtime"):
        rows = QueryDataLinkMetadataResource().perform_request(
            {"bk_tenant_id": "tenant-wrong", "result_table_id": table_id}
        )

    assert len(rows) == 1
    assert rows[0]["bk_tenant_id"] == "tenant-real"
    assert rows[0]["result_table_id"] == table_id


def test_vm_result_table_id_uses_vm_record_tenant_when_request_tenant_is_wrong():
    table_id = "600103_bkmonitor_time_series.__default__"
    _create_query_metadata_record(
        bk_tenant_id="tenant-real",
        bk_data_id=600103,
        table_id=table_id,
        vm_result_table_id="vm_600103",
    )

    with mock.patch.object(QueryDataLinkMetadataResource, "_enrich_with_runtime"):
        rows = QueryDataLinkMetadataResource().perform_request(
            {"bk_tenant_id": "tenant-wrong", "vm_result_table_id": "vm_600103"}
        )

    assert len(rows) == 1
    assert rows[0]["bk_tenant_id"] == "tenant-real"
    assert rows[0]["vm_rt_name"] == "vm_600103"


def test_component_name_uses_datalink_tenant_when_request_tenant_is_wrong():
    table_id = "600104_bkmonitor_time_series.__default__"
    _create_query_metadata_record(
        bk_tenant_id="tenant-real",
        bk_data_id=600104,
        table_id=table_id,
        created_from="bkdata",
    )
    models.DataLink.objects.create(
        bk_tenant_id="tenant-real",
        namespace="bkmonitor",
        data_link_name="tenant_link",
        bk_data_id=600104,
        table_ids=[table_id],
        data_link_strategy="bk_standard_v2_time_series",
    )

    with mock.patch.object(QueryDataLinkMetadataResource, "_enrich_with_runtime"):
        rows = QueryDataLinkMetadataResource().perform_request(
            {"bk_tenant_id": "tenant-wrong", "component_name": "bkmonitor-tenant_link"}
        )

    assert len(rows) == 1
    assert rows[0]["bk_tenant_id"] == "tenant-real"
    assert rows[0]["data_id"] == 600104


def test_component_name_uses_config_tenant_when_request_tenant_is_wrong():
    table_id = "600105_bkmonitor_time_series.__default__"
    _create_query_metadata_record(
        bk_tenant_id="tenant-real",
        bk_data_id=600105,
        table_id=table_id,
        created_from="bkdata",
    )
    models.DataLink.objects.create(
        bk_tenant_id="tenant-real",
        namespace="bkmonitor",
        data_link_name="tenant_link_from_config",
        bk_data_id=600105,
        table_ids=[table_id],
        data_link_strategy="bk_standard_v2_time_series",
    )
    models.ConditionalSinkConfig.objects.create(
        bk_tenant_id="tenant-real",
        namespace="bkmonitor",
        name="tenant_config",
        data_link_name="tenant_link_from_config",
        status="created",
        bk_biz_id=0,
    )

    with mock.patch.object(QueryDataLinkMetadataResource, "_enrich_with_runtime"):
        rows = QueryDataLinkMetadataResource().perform_request(
            {"bk_tenant_id": "tenant-wrong", "component_name": "bkmonitor-tenant_config"}
        )

    assert len(rows) == 1
    assert rows[0]["bk_tenant_id"] == "tenant-real"
    assert rows[0]["data_id"] == 600105
