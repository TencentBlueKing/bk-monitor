"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

import metadata.service.vm_short_link as short_link_service
from metadata import models
from metadata.models.space.constants import RESULT_TABLE_DETAIL_KEY, SpaceTypes
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.service.vm_short_link import apply_vm_short_links, delete_vm_short_links

pytestmark = pytest.mark.django_db(databases="__all__")

BK_TENANT_ID = "system"
VMRT = "315_idip_fail_cnt_for_bkmonitor_v1"
TABLE_ID = f"{VMRT}.__default__"


def create_space(space_id: str):
    return models.Space.objects.create(
        creator="system",
        updater="system",
        space_type_id=SpaceTypes.BKCC.value,
        space_id=space_id,
        space_name=f"biz-{space_id}",
        bk_tenant_id=BK_TENANT_ID,
    )


def create_vm_cluster(cluster_name: str = "vm_cluster", cluster_id: int = 10001):
    return models.ClusterInfo.objects.create(
        bk_tenant_id=BK_TENANT_ID,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
        port=80,
    )


def test_apply_vm_short_link_without_datasource(monkeypatch):
    create_vm_cluster()
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "result_table_name": "idip_fail_cnt_for_bkmonitor_v1",
            "result_table_name_alias": "idip_fail_cnt_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
        },
    )
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: False)

    result = apply_vm_short_links(
        vmrts=[VMRT],
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        refresh_router=False,
    )[0]

    assert result["table_id"] == TABLE_ID
    assert result["space_id"] == "315"
    assert not models.DataSource.objects.filter(bk_data_id=0).exists()
    assert not models.DataSourceResultTable.objects.filter(table_id=TABLE_ID).exists()
    assert not models.SpaceDataSource.objects.filter(bk_data_id=0).exists()
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=BK_TENANT_ID)
    assert short_link.is_global is False
    assert short_link.vm_result_table_name == "idip_fail_cnt_alias"
    assert short_link.query_router_config == {
        "space_type": SpaceTypes.BKCC.value,
        "filter_key": "bk_biz_id",
        "filter_value": "space_id",
    }
    vm_record = models.AccessVMRecord.objects.get(result_table_id=TABLE_ID)
    assert vm_record.bk_base_data_id == 0
    assert vm_record.bk_base_data_name == "idip_fail_cnt_alias"
    ts_group = models.TimeSeriesGroup.objects.get(table_id=TABLE_ID)
    assert ts_group.bk_data_id == 0
    assert ts_group.time_series_group_name == "idip_fail_cnt_alias"

    options = models.ResultTableOption.batch_result_table_option([TABLE_ID], bk_tenant_id=BK_TENANT_ID)[TABLE_ID]
    assert options[models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT] is True
    assert options[models.ResultTableOption.OPTION_IS_VIRTUAL_TABLE] is True


def test_time_series_group_zero_data_id_fallback_to_bkdata(monkeypatch):
    group = models.TimeSeriesGroup(
        bk_data_id=0,
        bk_tenant_id=BK_TENANT_ID,
        table_id=TABLE_ID,
        time_series_group_name="idip_fail_cnt_for_bkmonitor_v1",
        bk_biz_id=315,
    )
    monkeypatch.setattr("metadata.models.custom_report.time_series.RedisTools.get_list", lambda *args, **kwargs: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metric_from_bkdata", lambda self: [{"field_name": "metric"}])

    assert group.data_source is None
    assert group.get_metrics_from_redis() == [{"field_name": "metric"}]


def test_time_series_group_non_zero_data_id_keeps_original_exception():
    group = models.TimeSeriesGroup(
        bk_data_id=987654321,
        bk_tenant_id=BK_TENANT_ID,
        table_id="315_missing.__default__",
        time_series_group_name="missing",
        bk_biz_id=315,
    )

    with pytest.raises(models.DataSource.DoesNotExist):
        _ = group.data_source


def test_compose_vm_short_link_table_ids_global_and_owner_filters():
    create_space("315")
    create_space("316")
    models.ResultTable.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=BK_TENANT_ID,
        table_name_zh="single",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_VM,
        bk_biz_id=315,
    )
    global_table_id = "315_global_metric.__default__"
    models.ResultTable.objects.create(
        table_id=global_table_id,
        bk_tenant_id=BK_TENANT_ID,
        table_name_zh="global",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_VM,
        bk_biz_id=315,
        bk_biz_id_alias="appid",
    )
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="single",
        vm_cluster_id=10001,
        is_global=False,
    )
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=global_table_id,
        vm_result_table_id="315_global_metric",
        vm_result_table_name="global",
        vm_cluster_id=10001,
        query_router_config={"space_type": SpaceTypes.BKCC.value, "filter_key": "appid", "filter_value": "space_id"},
        is_global=True,
    )

    owner_values = SpaceTableIDRedis()._compose_vm_short_link_table_ids(SpaceTypes.BKCC.value, "315", BK_TENANT_ID)
    other_values = SpaceTableIDRedis()._compose_vm_short_link_table_ids(SpaceTypes.BKCC.value, "316", BK_TENANT_ID)

    assert owner_values[TABLE_ID] == {"filters": []}
    assert owner_values[global_table_id] == {"filters": []}
    assert TABLE_ID not in other_values
    assert other_values[global_table_id] == {"filters": [{"appid": "316"}]}


def test_compose_vm_short_link_table_ids_use_bk_biz_id_filter_value():
    create_space("315")
    bksaas_space = models.Space.objects.create(
        creator="system",
        updater="system",
        space_type_id=SpaceTypes.BKSAAS.value,
        space_id="app-code",
        space_name="app-code",
        bk_tenant_id=BK_TENANT_ID,
    )
    global_table_id = "315_global_metric.__default__"
    models.ResultTable.objects.create(
        table_id=global_table_id,
        bk_tenant_id=BK_TENANT_ID,
        table_name_zh="global",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_VM,
        bk_biz_id=315,
    )
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=global_table_id,
        vm_result_table_id="315_global_metric",
        vm_result_table_name="global",
        vm_cluster_id=10001,
        query_router_config={
            "space_type": SpaceTypes.ALL.value,
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
        is_global=True,
    )

    values = SpaceTableIDRedis()._compose_vm_short_link_table_ids(
        SpaceTypes.BKSAAS.value, bksaas_space.space_id, BK_TENANT_ID
    )

    assert values[global_table_id] == {"filters": [{"bk_biz_id": -bksaas_space.id}]}


def test_delete_vm_short_link_soft_delete_and_clean_detail(monkeypatch):
    create_space("315")
    models.ResultTable.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=BK_TENANT_ID,
        table_name_zh="single",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_VM,
        bk_biz_id=315,
    )
    models.TimeSeriesGroup.objects.create(
        bk_tenant_id=BK_TENANT_ID,
        bk_data_id=0,
        table_id=TABLE_ID,
        time_series_group_name="single",
        bk_biz_id=315,
        creator="system",
        last_modify_user="system",
    )
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="single",
        vm_cluster_id=10001,
    )

    hdel_calls = []
    push_calls = []
    monkeypatch.setattr(
        short_link_service.RedisTools,
        "hdel",
        lambda key, fields: hdel_calls.append({"key": key, "fields": fields}),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda self, space_type, space_id, is_publish=False: push_calls.append((space_type, space_id, is_publish)),
    )

    result = delete_vm_short_links(bk_tenant_id=BK_TENANT_ID, table_ids=[TABLE_ID], operator="tester")

    assert result["deleted_count"] == 1
    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_deleted is True
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_deleted is True
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).is_delete is True
    assert hdel_calls == [{"key": RESULT_TABLE_DETAIL_KEY, "fields": [TABLE_ID]}]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]
