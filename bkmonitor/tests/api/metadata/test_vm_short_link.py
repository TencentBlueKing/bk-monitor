"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

import pytest

import metadata.service.vm_short_link as short_link_service
from metadata import models
from metadata.models.space.constants import RESULT_TABLE_DETAIL_KEY, SpaceTypes
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources import vm as vm_resources
from metadata.service.vm_short_link import (
    apply_vm_short_links,
    delete_vm_short_links,
    switch_vm_short_links,
    update_vm_short_links,
)

pytestmark = pytest.mark.django_db(databases="__all__")

BK_TENANT_ID = "system"
VMRT = "315_idip_fail_cnt_for_bkmonitor_v1"
TABLE_ID = f"{VMRT}.__default__"


def create_space(space_id: str) -> models.Space:
    return models.Space.objects.create(
        creator="system",
        updater="system",
        space_type_id=SpaceTypes.BKCC.value,
        space_id=space_id,
        space_name=f"biz-{space_id}",
        bk_tenant_id=BK_TENANT_ID,
    )


def create_vm_cluster(cluster_name: str = "vm_cluster", cluster_id: int = 10001) -> models.ClusterInfo:
    return models.ClusterInfo.objects.create(
        bk_tenant_id=BK_TENANT_ID,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
        port=80,
        is_default_cluster=False,
    )


def test_apply_vm_short_link_resource_use_explicit_tenant_id(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        vm_resources,
        "apply_vm_short_links",
        lambda **kwargs: calls.append(kwargs) or [{"table_id": TABLE_ID}],
    )

    result = vm_resources.ApplyVMShortLinkResource().perform_request(
        {
            "bk_tenant_id": "tenant-from-field",
            "bk_biz_id": 315,
            "vmrts": [VMRT],
            "is_global": False,
            "query_router_config": {},
            "operator": "tester",
            "refresh_router": True,
            "overwrite": True,
        }
    )

    assert result == [{"table_id": TABLE_ID}]
    assert calls[0]["bk_tenant_id"] == "tenant-from-field"
    assert calls[0]["bk_biz_id"] == 315


def test_delete_vm_short_link_resource_use_explicit_tenant_id(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        vm_resources,
        "delete_vm_short_links",
        lambda **kwargs: calls.append(kwargs) or {"deleted_count": 1},
    )

    result = vm_resources.DeleteVMShortLinkResource().perform_request(
        {
            "bk_tenant_id": "tenant-from-field",
            "bk_biz_id": 315,
            "table_ids": [TABLE_ID],
            "operator": "tester",
            "refresh_router": True,
        }
    )

    assert result == {"deleted_count": 1}
    assert calls[0]["bk_tenant_id"] == "tenant-from-field"
    assert calls[0]["bk_biz_id"] == 315


def test_update_vm_short_link_resource_use_explicit_tenant_id(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        vm_resources,
        "update_vm_short_links",
        lambda **kwargs: calls.append(kwargs) or [{"table_id": TABLE_ID}],
    )

    result = vm_resources.UpdateVMShortLinkResource().perform_request(
        {
            "bk_tenant_id": "tenant-from-field",
            "bk_biz_id": 315,
            "table_ids": [TABLE_ID],
            "is_global": True,
            "query_router_config": {},
            "refresh_bkbase": False,
            "operator": "tester",
            "refresh_router": True,
        }
    )

    assert result == [{"table_id": TABLE_ID}]
    assert calls[0]["bk_tenant_id"] == "tenant-from-field"
    assert calls[0]["bk_biz_id"] == 315


def test_switch_vm_short_link_resource_use_explicit_tenant_id(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        vm_resources,
        "switch_vm_short_links",
        lambda **kwargs: calls.append(kwargs) or {"updated_count": 1},
    )

    result = vm_resources.SwitchVMShortLinkResource().perform_request(
        {
            "bk_tenant_id": "tenant-from-field",
            "bk_biz_id": 315,
            "table_ids": [TABLE_ID],
            "is_enabled": False,
            "operator": "tester",
            "refresh_router": True,
        }
    )

    assert result == {"updated_count": 1}
    assert calls[0]["bk_tenant_id"] == "tenant-from-field"
    assert calls[0]["bk_biz_id"] == 315


def test_apply_vm_short_link_without_datasource(monkeypatch):
    create_space("315")
    create_vm_cluster()
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 315,
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
        bk_biz_id=315,
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
        "filter_value": "bk_biz_id",
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


def test_apply_vm_short_link_deduplicate_vmrts(monkeypatch):
    create_space("315")
    create_vm_cluster()
    calls: list[str] = []

    def get_result_table(**kwargs):
        calls.append(kwargs["result_table_id"])
        return {
            "bk_biz_id": 315,
            "result_table_name": "idip_fail_cnt_for_bkmonitor_v1",
            "result_table_name_alias": "idip_fail_cnt_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
        }

    monkeypatch.setattr(short_link_service.api.bkdata, "get_result_table", get_result_table)
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: False)

    result = apply_vm_short_links(
        vmrts=[VMRT, VMRT],
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        refresh_router=False,
    )

    assert len(result) == 1
    assert calls == [VMRT]
    assert models.VMShortLinkRecord.objects.filter(table_id=TABLE_ID).count() == 1


def test_apply_vm_short_link_existing_vmrt_requires_overwrite(monkeypatch):
    create_space("315")
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="existing",
        vm_cluster_id=10001,
        is_global=True,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("existing vmrt should not be fetched from bkbase"),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda *args, **kwargs: pytest.fail("skipped vmrt should not refresh table detail"),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda *args, **kwargs: pytest.fail("skipped vmrt should not refresh space route"),
    )

    with pytest.raises(ValueError, match="use overwrite=True to overwrite"):
        apply_vm_short_links(
            vmrts=[VMRT],
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=315,
            is_global=False,
        )

    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.vm_result_table_name == "existing"
    assert short_link.is_global is True


def test_apply_vm_short_link_reject_non_positive_biz_id_before_bkbase(monkeypatch):
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="existing",
        vm_cluster_id=10001,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("invalid bk_biz_id should fail before fetching bkbase"),
    )

    with pytest.raises(ValueError, match="bk_biz_id must be greater than 0"):
        apply_vm_short_links(
            vmrts=[VMRT],
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=0,
            refresh_router=False,
        )


def test_apply_vm_short_link_overwrite_reject_out_of_biz_scope_before_bkbase(monkeypatch):
    create_space("316")
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="existing",
        vm_cluster_id=10001,
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("out-of-scope overwrite should fail before fetching bkbase"),
    )

    with pytest.raises(ValueError, match="not in bk_biz_id scope"):
        apply_vm_short_links(
            vmrts=[VMRT],
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=316,
            is_global=True,
            refresh_router=False,
            overwrite=True,
        )

    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.space_id == "315"
    assert short_link.is_global is False


def test_apply_vm_short_link_overwrite_existing_vmrt(monkeypatch):
    create_space("315")
    create_vm_cluster(cluster_name="new_vm_cluster", cluster_id=10002)
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="existing",
        vm_cluster_id=10001,
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 315,
            "result_table_name": "new_name",
            "result_table_name_alias": "new_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "new_vm_cluster"}}},
        },
    )
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: False)

    result = apply_vm_short_links(
        vmrts=[VMRT],
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        is_global=True,
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "appid",
            "filter_value": "space_id",
        },
        refresh_router=False,
        overwrite=True,
    )[0]

    assert result["created"] is False
    assert result["vm_cluster_id"] == 10002
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.vm_result_table_name == "new_alias"
    assert short_link.vm_cluster_id == 10002
    assert short_link.is_global is True
    assert short_link.query_router_config == {
        "space_type": SpaceTypes.BKCC.value,
        "filter_key": "appid",
        "filter_value": "space_id",
    }
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE_ID).bk_base_data_name == "new_alias"


def test_apply_vm_short_link_reuse_deleted_record(monkeypatch):
    create_space("315")
    create_vm_cluster(cluster_name="old_vm_cluster", cluster_id=10001)
    create_vm_cluster(cluster_name="new_vm_cluster", cluster_id=10002)
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="deleted",
        vm_cluster_id=10001,
        is_enabled=False,
        is_deleted=True,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 315,
            "result_table_name": "new_name",
            "result_table_name_alias": "new_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "new_vm_cluster"}}},
        },
    )
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: False)

    result = apply_vm_short_links(
        vmrts=[VMRT],
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        is_global=True,
        refresh_router=False,
    )

    assert result[0]["table_id"] == TABLE_ID
    assert result[0]["created"] is False
    assert result[0]["vm_cluster_id"] == 10002
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.is_deleted is False
    assert short_link.is_enabled is True
    assert short_link.vm_result_table_name == "new_alias"
    assert short_link.vm_cluster_id == 10002
    assert short_link.is_global is True


def test_apply_vm_short_link_reject_vmrt_biz_id_mismatch_before_write(monkeypatch):
    create_space("315")
    create_vm_cluster()
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 316,
            "result_table_name": "wrong_biz",
            "result_table_name_alias": "wrong_biz_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
        },
    )

    with pytest.raises(ValueError, match="bk_biz_id mismatch"):
        apply_vm_short_links(
            vmrts=[VMRT],
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=315,
            refresh_router=False,
        )

    assert not models.VMShortLinkRecord.objects.filter(table_id=TABLE_ID).exists()
    assert not models.ResultTable.objects.filter(table_id=TABLE_ID).exists()


def test_apply_vm_short_link_batch_precheck_before_write(monkeypatch):
    create_space("315")
    create_vm_cluster()
    invalid_vmrt = "316_wrong_biz_metric"
    invalid_table_id = f"{invalid_vmrt}.__default__"

    def get_result_table(**kwargs):
        if kwargs["result_table_id"] == VMRT:
            return {
                "bk_biz_id": 315,
                "result_table_name": "valid",
                "result_table_name_alias": "valid_alias",
                "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
            }
        return {
            "bk_biz_id": 316,
            "result_table_name": "invalid",
            "result_table_name_alias": "invalid_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
        }

    monkeypatch.setattr(short_link_service.api.bkdata, "get_result_table", get_result_table)

    with pytest.raises(ValueError, match="bk_biz_id mismatch"):
        apply_vm_short_links(
            vmrts=[VMRT, invalid_vmrt],
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=315,
            refresh_router=False,
        )

    assert not models.VMShortLinkRecord.objects.filter(table_id__in=[TABLE_ID, invalid_table_id]).exists()
    assert not models.ResultTable.objects.filter(table_id__in=[TABLE_ID, invalid_table_id]).exists()


def test_apply_global_vm_short_link_only_refresh_owner_space(monkeypatch):
    create_space("315")
    create_space("316")
    create_vm_cluster()
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 315,
            "result_table_name": "idip_fail_cnt_for_bkmonitor_v1",
            "result_table_name_alias": "idip_fail_cnt_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "vm_cluster"}}},
        },
    )
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: False)

    detail_calls: list[dict[str, Any]] = []
    push_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda self, table_id_list, is_publish=False, bk_tenant_id=BK_TENANT_ID, **kwargs: detail_calls.append(
            {"table_id_list": table_id_list, "is_publish": is_publish, "bk_tenant_id": bk_tenant_id}
        ),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda self, space_type, space_id, is_publish=False: push_calls.append((space_type, space_id, is_publish)),
    )

    apply_vm_short_links(
        vmrts=[VMRT],
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        is_global=True,
    )

    assert detail_calls == [{"table_id_list": [TABLE_ID], "is_publish": True, "bk_tenant_id": BK_TENANT_ID}]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]


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


def test_delete_global_vm_short_link_soft_delete_and_only_refresh_owner_space(monkeypatch):
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
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
        is_global=True,
    )

    hdel_calls: list[dict[str, Any]] = []
    push_calls: list[tuple[str, str, bool]] = []
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

    result = delete_vm_short_links(bk_tenant_id=BK_TENANT_ID, bk_biz_id=315, table_ids=[TABLE_ID], operator="tester")

    assert result["deleted_count"] == 1
    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_deleted is True
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_deleted is True
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).is_delete is True
    assert hdel_calls == [{"key": RESULT_TABLE_DETAIL_KEY, "fields": [TABLE_ID]}]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]


def test_delete_vm_short_link_reject_out_of_biz_scope(monkeypatch):
    create_space("315")
    create_space("316")
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
    monkeypatch.setattr(
        short_link_service.RedisTools,
        "hdel",
        lambda *args, **kwargs: pytest.fail("out-of-scope delete should fail before cleaning redis"),
    )

    with pytest.raises(ValueError, match="not in bk_biz_id scope"):
        delete_vm_short_links(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=316,
            table_ids=[TABLE_ID],
            operator="tester",
        )

    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_deleted is False


def test_update_vm_short_link_refresh_bkbase_and_router_config(monkeypatch):
    create_space("315")
    create_vm_cluster(cluster_name="old_vm_cluster", cluster_id=10001)
    create_vm_cluster(cluster_name="new_vm_cluster", cluster_id=10002)
    models.ResultTable.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=BK_TENANT_ID,
        table_name_zh="old",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_VM,
        bk_biz_id=315,
    )
    models.AccessVMRecord.objects.create(
        bk_tenant_id=BK_TENANT_ID,
        result_table_id=TABLE_ID,
        data_type=models.AccessVMRecord.ACCESS_VM,
        storage_cluster_id=10001,
        vm_cluster_id=10001,
        bk_base_data_id=0,
        bk_base_data_name="old",
        vm_result_table_id=VMRT,
    )
    models.TimeSeriesGroup.objects.create(
        bk_tenant_id=BK_TENANT_ID,
        bk_data_id=0,
        table_id=TABLE_ID,
        time_series_group_name="old",
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
        vm_result_table_name="old",
        vm_cluster_id=10001,
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: {
            "bk_biz_id": 315,
            "result_table_name": "new_name",
            "result_table_name_alias": "new_alias",
            "storages": {"vm": {"storage_cluster": {"cluster_name": "new_vm_cluster"}}},
        },
    )
    monkeypatch.setattr(models.TimeSeriesGroup, "get_metrics_from_redis", lambda self: [])
    monkeypatch.setattr(models.TimeSeriesGroup, "update_metrics", lambda self, metrics_info: True)

    detail_calls: list[list[str]] = []
    push_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda self, table_id_list, is_publish=False, bk_tenant_id=BK_TENANT_ID, **kwargs: detail_calls.append(
            table_id_list
        ),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda self, space_type, space_id, is_publish=False: push_calls.append((space_type, space_id, is_publish)),
    )

    result = update_vm_short_links(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        vmrts=[VMRT],
        is_global=True,
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "appid",
            "filter_value": "space_id",
        },
        operator="tester",
    )[0]

    assert result["vm_cluster_id"] == 10002
    assert result["vmrt"] == VMRT
    assert result["table_id"] == TABLE_ID
    assert result["space_id"] == "315"
    assert result["is_global"] is True
    assert result["query_router_config"] == {
        "space_type": SpaceTypes.BKCC.value,
        "filter_key": "appid",
        "filter_value": "space_id",
    }
    assert result["is_updated_metrics"] is True

    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.space_id == "315"
    assert short_link.vm_result_table_name == "new_alias"
    assert short_link.vm_cluster_id == 10002
    assert short_link.is_global is True
    assert models.ResultTable.objects.get(table_id=TABLE_ID).table_name_zh == "new_alias"
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE_ID).vm_cluster_id == 10002
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE_ID).bk_base_data_name == "new_alias"
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).time_series_group_name == "new_alias"
    assert detail_calls == [[TABLE_ID]]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]


def test_update_vm_short_link_without_refresh_bkbase_only_update_config(monkeypatch):
    create_space("315")
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="old",
        vm_cluster_id=10001,
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("refresh_bkbase=False should not fetch bkbase"),
    )
    detail_calls: list[list[str]] = []
    push_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda self, table_id_list, is_publish=False, bk_tenant_id=BK_TENANT_ID, **kwargs: detail_calls.append(
            table_id_list
        ),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda self, space_type, space_id, is_publish=False: push_calls.append((space_type, space_id, is_publish)),
    )

    result = update_vm_short_links(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        table_ids=[TABLE_ID],
        is_global=True,
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "appid",
            "filter_value": "space_id",
        },
        refresh_bkbase=False,
        operator="tester",
    )[0]

    assert result["vm_cluster_id"] == 10001
    assert result["is_global"] is True
    assert result["query_router_config"] == {
        "space_type": SpaceTypes.BKCC.value,
        "filter_key": "appid",
        "filter_value": "space_id",
    }
    assert result["is_updated_metrics"] is False
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.vm_result_table_name == "old"
    assert short_link.vm_cluster_id == 10001
    assert short_link.is_global is True
    assert detail_calls == [[TABLE_ID]]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]


def test_update_vm_short_link_reject_owner_space_change_before_bkbase_and_write(monkeypatch, caplog):
    create_space("316")
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="old",
        vm_cluster_id=10001,
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("owner space mismatch should fail before fetching bkbase"),
    )

    with caplog.at_level(logging.ERROR, logger="metadata"):
        with pytest.raises(ValueError, match="not in bk_biz_id scope"):
            update_vm_short_links(
                bk_tenant_id=BK_TENANT_ID,
                bk_biz_id=316,
                vmrts=[VMRT],
                is_global=True,
                refresh_bkbase=True,
            )

    assert "owner space mismatch" in caplog.text
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.space_id == "315"
    assert short_link.is_global is False
    assert short_link.vm_result_table_name == "old"


def test_update_vm_short_link_keep_config_when_optional_params_omitted(monkeypatch):
    create_space("315")
    original_query_router_config = {
        "space_type": SpaceTypes.BKCC.value,
        "filter_key": "bk_biz_id",
        "filter_value": "bk_biz_id",
    }
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="old",
        vm_cluster_id=10001,
        query_router_config=original_query_router_config,
        is_global=True,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("refresh_bkbase=False should not fetch bkbase"),
    )

    result = update_vm_short_links(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        vmrts=[VMRT],
        refresh_bkbase=False,
        refresh_router=False,
        operator="tester",
    )[0]

    assert result["space_type"] == SpaceTypes.BKCC.value
    assert result["space_id"] == "315"
    assert result["vm_cluster_id"] == 10001
    assert result["is_global"] is True
    assert result["query_router_config"] == original_query_router_config
    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.space_id == "315"
    assert short_link.vm_result_table_name == "old"
    assert short_link.vm_cluster_id == 10001
    assert short_link.is_global is True
    assert short_link.query_router_config == original_query_router_config


def test_update_vm_short_link_missing_record_fails_before_bkbase(monkeypatch):
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("missing vmrt should fail before fetching bkbase"),
    )

    with pytest.raises(ValueError, match="vm short link not found by vmrts"):
        update_vm_short_links(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=315,
            vmrts=[VMRT],
            refresh_bkbase=True,
        )


def test_update_vm_short_link_partial_missing_fails_before_bkbase_and_write(monkeypatch):
    models.VMShortLinkRecord.objects.create(
        creator="system",
        updater="system",
        bk_tenant_id=BK_TENANT_ID,
        space_type=SpaceTypes.BKCC.value,
        space_id="315",
        table_id=TABLE_ID,
        vm_result_table_id=VMRT,
        vm_result_table_name="old",
        vm_cluster_id=10001,
        is_global=False,
    )
    monkeypatch.setattr(
        short_link_service.api.bkdata,
        "get_result_table",
        lambda **kwargs: pytest.fail("partial missing table should fail before fetching bkbase"),
    )

    with pytest.raises(ValueError, match="vm short link not found by table_ids"):
        update_vm_short_links(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=315,
            table_ids=[TABLE_ID, "315_missing.__default__"],
            is_global=True,
            refresh_bkbase=True,
        )

    short_link = models.VMShortLinkRecord.objects.get(table_id=TABLE_ID)
    assert short_link.is_global is False
    assert short_link.vm_result_table_name == "old"


def test_switch_vm_short_link_enable_and_disable_only_refresh_owner_space(monkeypatch):
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
        query_router_config={
            "space_type": SpaceTypes.BKCC.value,
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
        is_global=True,
    )

    detail_calls: list[list[str]] = []
    push_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda self, table_id_list, is_publish=False, bk_tenant_id=BK_TENANT_ID, **kwargs: detail_calls.append(
            table_id_list
        ),
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_space_table_ids",
        lambda self, space_type, space_id, is_publish=False: push_calls.append((space_type, space_id, is_publish)),
    )

    disabled = switch_vm_short_links(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        table_ids=[TABLE_ID],
        is_enabled=False,
        operator="tester",
    )

    assert disabled == {"updated_count": 1, "table_ids": [TABLE_ID], "is_enabled": False}
    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_deleted is False
    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_enabled is False
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_deleted is False
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_enable is False
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).is_delete is False
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).is_enable is False
    assert detail_calls == [[TABLE_ID]]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True)]

    enabled = switch_vm_short_links(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=315,
        table_ids=[TABLE_ID],
        is_enabled=True,
        operator="tester",
    )

    assert enabled == {"updated_count": 1, "table_ids": [TABLE_ID], "is_enabled": True}
    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_enabled is True
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_enable is True
    assert models.TimeSeriesGroup.objects.get(table_id=TABLE_ID).is_enable is True
    assert detail_calls == [[TABLE_ID], [TABLE_ID]]
    assert push_calls == [(SpaceTypes.BKCC.value, "315", True), (SpaceTypes.BKCC.value, "315", True)]


def test_switch_vm_short_link_reject_out_of_biz_scope(monkeypatch):
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
        is_enabled=True,
    )
    monkeypatch.setattr(
        short_link_service.SpaceTableIDRedis,
        "push_table_id_detail",
        lambda *args, **kwargs: pytest.fail("out-of-scope switch should fail before refreshing route"),
    )

    with pytest.raises(ValueError, match="not in bk_biz_id scope"):
        switch_vm_short_links(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=316,
            table_ids=[TABLE_ID],
            is_enabled=False,
            operator="tester",
        )

    assert models.VMShortLinkRecord.objects.get(table_id=TABLE_ID).is_enabled is True
    assert models.ResultTable.objects.get(table_id=TABLE_ID).is_enable is True
