"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet

from core.drf_resource import api
from metadata import models
from metadata.models.space.constants import RESULT_TABLE_DETAIL_KEY, SpaceTypes
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import reformat_table_id
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")

# 短链路没有监控侧 DataSource，统一使用 0 标识“无数据源”。
SHORT_LINK_BK_DATA_ID = 0
DEFAULT_OPERATOR = "system"


def _get_space_info_by_biz_id(bk_tenant_id: str, bk_biz_id: int) -> tuple[str, str]:
    """通过 bk_biz_id 获取短链路归属空间，所有入口统一使用业务 ID 表达归属关系。"""
    if bk_biz_id <= 0:
        raise ValueError(f"bk_biz_id must be greater than 0: {bk_biz_id}")

    space_type = SpaceTypes.BKCC.value
    space_id = str(bk_biz_id)
    if not models.Space.objects.filter(
        bk_tenant_id=bk_tenant_id,
        space_type_id=space_type,
        space_id=space_id,
    ).exists():
        raise ValueError(f"space not found by bk_biz_id: {bk_biz_id}")
    return space_type, space_id


def _get_vmrt_info(bk_tenant_id: str, vmrt: str) -> tuple[int, str, int]:
    """从 BKBase RT 元信息中提取短链路需要持久化的 VM 集群和名称。"""
    table_info = api.bkdata.get_result_table(bk_tenant_id=bk_tenant_id, result_table_id=vmrt)
    try:
        cluster_name = table_info["storages"]["vm"]["storage_cluster"]["cluster_name"]
    except KeyError as err:
        raise ValueError(f"vmrt: {vmrt} not found vm storage cluster") from err

    vm_cluster_id = models.ClusterInfo.objects.get(
        bk_tenant_id=bk_tenant_id,
        cluster_name=cluster_name,
        cluster_type=models.ClusterInfo.TYPE_VM,
    ).cluster_id
    vm_result_table_name = table_info.get("result_table_name_alias") or table_info.get("result_table_name") or vmrt
    return vm_cluster_id, vm_result_table_name, int(table_info["bk_biz_id"])


def _validate_vmrt_biz_id(vmrt: str, actual_bk_biz_id: int, expected_bk_biz_id: int) -> None:
    """只允许业务自身的 VMRT 接入或刷新，避免把其他业务的 BKBase 表挂到当前空间。"""
    if actual_bk_biz_id != expected_bk_biz_id:
        raise ValueError(
            f"vmrt: {vmrt} bk_biz_id mismatch, expected: {expected_bk_biz_id}, actual: {actual_bk_biz_id}"
        )


def _upsert_result_table_option(table_id: str, bk_tenant_id: str, name: str, value: bool, operator: str) -> None:
    """短链路可重复执行，RT option 使用 upsert 保持幂等。"""
    option_value, option_value_type = models.ResultTableOption._parse_value(value)
    models.ResultTableOption.objects.update_or_create(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        name=name,
        defaults={
            "value": option_value,
            "value_type": option_value_type,
            "creator": operator,
        },
    )


def _upsert_result_table(
    table_id: str,
    vm_result_table_name: str,
    bk_biz_id: int,
    bk_tenant_id: str,
    operator: str,
) -> tuple[models.ResultTable, bool]:
    """创建短链路虚拟 RT；它只参与查询路由和指标发现，不对应监控侧 DataSource。"""
    return models.ResultTable.objects.update_or_create(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        defaults={
            "table_name_zh": vm_result_table_name,
            "is_custom_table": False,
            "schema_type": models.ResultTable.SCHEMA_TYPE_FIXED,
            "default_storage": models.ClusterInfo.TYPE_VM,
            "creator": operator,
            "last_modify_user": operator,
            "bk_biz_id": bk_biz_id,
            "is_deleted": False,
            "is_enable": True,
        },
    )


def _sync_vm_short_link_metadata(
    vmrt: str,
    table_id: str,
    vm_cluster_id: int,
    vm_result_table_name: str,
    bk_biz_id: int,
    bk_tenant_id: str,
    operator: str,
) -> tuple[bool, bool]:
    """同步短链路依赖的 RT / VM / 指标配置，供新接入和配置刷新复用。"""
    _, rt_created = _upsert_result_table(
        table_id=table_id,
        vm_result_table_name=vm_result_table_name,
        bk_biz_id=bk_biz_id,
        bk_tenant_id=bk_tenant_id,
        operator=operator,
    )

    models.AccessVMRecord.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        result_table_id=table_id,
        defaults={
            "data_type": models.AccessVMRecord.ACCESS_VM,
            "storage_cluster_id": vm_cluster_id,
            "vm_cluster_id": vm_cluster_id,
            "bk_base_data_id": SHORT_LINK_BK_DATA_ID,
            "bk_base_data_name": vm_result_table_name,
            "vm_result_table_id": vmrt,
        },
    )

    ts_group, _ = models.TimeSeriesGroup.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        defaults={
            # TimeSeriesGroup.data_source 会将 0 识别为无监控侧 DataSource，并直接走 BKBase 指标发现。
            "bk_data_id": SHORT_LINK_BK_DATA_ID,
            "time_series_group_name": vm_result_table_name,
            "bk_biz_id": bk_biz_id,
            "is_enable": True,
            "is_delete": False,
            "is_split_measurement": True,
            "creator": operator,
            "last_modify_user": operator,
        },
    )

    _upsert_result_table_option(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        name=models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT,
        value=True,
        operator=operator,
    )
    _upsert_result_table_option(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        name=models.ResultTableOption.OPTION_IS_VIRTUAL_TABLE,
        value=True,
        operator=operator,
    )

    metrics_info = ts_group.get_metrics_from_redis()
    return rt_created, ts_group.update_metrics(metrics_info)


def _refresh_short_link_spaces(
    bk_tenant_id: str,
    refresh_spaces: set[tuple[str, str]],
    table_ids: list[str] | None = None,
) -> None:
    """刷新短链路归属空间；非归属空间由 BMW 自然刷新。"""
    redis = SpaceTableIDRedis()
    if table_ids:
        redis.push_table_id_detail(table_id_list=table_ids, is_publish=True, bk_tenant_id=bk_tenant_id)

    for space_type, space_id in refresh_spaces:
        redis.push_space_table_ids(space_type=space_type, space_id=str(space_id), is_publish=True)


def apply_vm_short_links(
    vmrts: list[str],
    bk_tenant_id: str,
    bk_biz_id: int,
    is_global: bool = False,
    query_router_config: dict[str, Any] | None = None,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """接入 VM 短链路。

    接入一定从 BKBase 刷新元信息；未显式 overwrite 时，遇到已接入 VMRT 直接报错。
    """
    # apply 是“接入”语义，重复 VMRT 只执行一次，避免同一批次内第二次命中已存在记录。
    vmrts = list(dict.fromkeys(vmrts))
    results: list[dict[str, Any]] = []
    refresh_spaces: set[tuple[str, str]] = set()
    refreshed_table_ids: list[str] = []
    space_type, space_id = _get_space_info_by_biz_id(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    normalized_query_router_config = models.VMShortLinkRecord.normalize_query_router_config(
        query_router_config, space_type
    )
    existing_records = {
        record.vm_result_table_id: record
        for record in models.VMShortLinkRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            vm_result_table_id__in=vmrts,
        )
    }
    _validate_vm_short_link_records_in_biz(
        records=list(existing_records.values()),
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        action="apply_vm_short_links",
    )
    active_existing_vmrts = sorted(
        vmrt for vmrt, record in existing_records.items() if not record.is_deleted
    )
    # overwrite 是显式破坏性开关：默认发现已接入未删除记录就提前失败，避免误覆盖路由配置。
    if active_existing_vmrts and not overwrite:
        raise ValueError(
            f"vm short link already exists: {', '.join(active_existing_vmrts)}, "
            "use overwrite=True to overwrite"
        )
    # 先拉取并校验整批 VMRT，避免部分短链路已经写入后才发现后续 VMRT 不属于当前业务。
    vmrt_infos: dict[str, tuple[int, str]] = {}
    for vmrt in vmrts:
        vm_cluster_id, vm_result_table_name, vmrt_bk_biz_id = _get_vmrt_info(bk_tenant_id=bk_tenant_id, vmrt=vmrt)
        _validate_vmrt_biz_id(vmrt=vmrt, actual_bk_biz_id=vmrt_bk_biz_id, expected_bk_biz_id=bk_biz_id)
        vmrt_infos[vmrt] = (vm_cluster_id, vm_result_table_name)

    for vmrt in vmrts:
        table_id = f"{vmrt}.__default__".lower()
        vm_cluster_id, vm_result_table_name = vmrt_infos[vmrt]
        # 覆盖或复用软删除记录时，旧归属空间也需要刷新；新接入则只刷新当前归属空间。
        old_space = None
        if vmrt in existing_records:
            old_space = (existing_records[vmrt].space_type, existing_records[vmrt].space_id)

        with transaction.atomic():
            _, is_updated = _sync_vm_short_link_metadata(
                vmrt=vmrt,
                table_id=table_id,
                vm_cluster_id=vm_cluster_id,
                vm_result_table_name=vm_result_table_name,
                bk_biz_id=bk_biz_id,
                bk_tenant_id=bk_tenant_id,
                operator=operator,
            )

            short_link, short_link_created = models.VMShortLinkRecord.objects.update_or_create(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                defaults={
                    "space_type": space_type,
                    "space_id": space_id,
                    "vm_result_table_id": vmrt,
                    "vm_result_table_name": vm_result_table_name,
                    "vm_cluster_id": vm_cluster_id,
                    "query_router_config": normalized_query_router_config,
                    "is_global": is_global,
                    "is_enabled": True,
                    "is_deleted": False,
                    "creator": operator,
                    "updater": operator,
                },
            )

        if old_space:
            refresh_spaces.add(old_space)
        refresh_spaces.add((space_type, space_id))
        refreshed_table_ids.append(table_id)
        results.append(
            {
                "vmrt": vmrt,
                "table_id": table_id,
                "space_type": short_link.space_type,
                "space_id": short_link.space_id,
                "bk_tenant_id": bk_tenant_id,
                "vm_cluster_id": vm_cluster_id,
                "created": short_link_created,
                "is_updated_metrics": is_updated,
            }
        )

    if refresh_router and refreshed_table_ids:
        _refresh_short_link_spaces(
            bk_tenant_id=bk_tenant_id,
            refresh_spaces=refresh_spaces,
            table_ids=refreshed_table_ids,
        )

    return results


def _compose_detail_redis_fields(table_ids: list[str], bk_tenant_id: str) -> list[str]:
    """按 result_table_detail 的真实 Redis field 形态组装待清理字段。"""
    fields = [reformat_table_id(table_id) for table_id in table_ids]
    if settings.ENABLE_MULTI_TENANT_MODE:
        fields = [f"{field}|{bk_tenant_id}" for field in fields]
    return fields


def _filter_vm_short_links(
    bk_tenant_id: str,
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
) -> QuerySet[models.VMShortLinkRecord]:
    """按虚拟 RT 或 VMRT 查找未删除的短链路记录。"""
    if not table_ids and not vmrts:
        raise ValueError("table_ids and vmrts cannot both be empty")

    qs = models.VMShortLinkRecord.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    if table_ids:
        qs = qs.filter(table_id__in=table_ids)
    if vmrts:
        qs = qs.filter(vm_result_table_id__in=vmrts)
    return qs


def _owner_spaces(records: list[models.VMShortLinkRecord]) -> set[tuple[str, str]]:
    """短链路服务层只主动刷新归属空间，非归属空间交给 BMW 自然刷新。"""
    return {(record.space_type, record.space_id) for record in records}


def _validate_vm_short_link_records_exist(
    records: list[models.VMShortLinkRecord],
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
) -> None:
    """批量操作不允许静默忽略不存在目标，避免调用方误以为已处理成功。"""
    found_table_ids = {record.table_id for record in records}
    found_vmrts = {record.vm_result_table_id for record in records}
    if table_ids:
        missing_table_ids = sorted(set(table_ids) - found_table_ids)
        if missing_table_ids:
            raise ValueError(f"vm short link not found by table_ids: {', '.join(missing_table_ids)}")
    if vmrts:
        missing_vmrts = sorted(set(vmrts) - found_vmrts)
        if missing_vmrts:
            raise ValueError(f"vm short link not found by vmrts: {', '.join(missing_vmrts)}")


def _validate_vm_short_link_records_in_biz(
    records: list[models.VMShortLinkRecord],
    bk_tenant_id: str,
    bk_biz_id: int,
    action: str,
) -> tuple[str, str]:
    """delete / switch / update 都只能操作请求业务所属空间内的短链路记录。"""
    space_type, space_id = _get_space_info_by_biz_id(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    mismatched_spaces = [
        {
            "table_id": record.table_id,
            "vmrt": record.vm_result_table_id,
            "current_space": (record.space_type, record.space_id),
            "request_space": (space_type, space_id),
        }
        for record in records
        if space_type != record.space_type or space_id != record.space_id
    ]
    if mismatched_spaces:
        logger.error(
            "%s: owner space mismatch, bk_tenant_id: %s, bk_biz_id: %s, mismatched_spaces: %s",
            action,
            bk_tenant_id,
            bk_biz_id,
            json.dumps(mismatched_spaces),
        )
        raise ValueError("vm short link not in bk_biz_id scope")
    return space_type, space_id


def update_vm_short_links(
    bk_tenant_id: str,
    bk_biz_id: int,
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
    is_global: bool | None = None,
    query_router_config: dict[str, Any] | None = None,
    refresh_bkbase: bool = True,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
) -> list[dict[str, Any]]:
    """更新已有短链路配置；可选择是否从 BKBase 刷新 VMRT 相关配置。"""
    records = list(_filter_vm_short_links(bk_tenant_id=bk_tenant_id, table_ids=table_ids, vmrts=vmrts))
    # update 是“修改已有记录”语义，目标不完整时必须在任何外部请求或写库前失败。
    _validate_vm_short_link_records_exist(records=records, table_ids=table_ids, vmrts=vmrts)
    _validate_vm_short_link_records_in_biz(
        records=records,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        action="update_vm_short_links",
    )

    vmrt_infos: dict[str, tuple[int, str]] = {}
    if refresh_bkbase:
        # 先统一拉取 BKBase 元信息，避免前半批已写库、后半批才因 BKBase 异常失败。
        for record in records:
            vm_cluster_id, vm_result_table_name, vmrt_bk_biz_id = _get_vmrt_info(
                bk_tenant_id=bk_tenant_id,
                vmrt=record.vm_result_table_id,
            )
            _validate_vmrt_biz_id(
                vmrt=record.vm_result_table_id,
                actual_bk_biz_id=vmrt_bk_biz_id,
                expected_bk_biz_id=bk_biz_id,
            )
            vmrt_infos[record.vm_result_table_id] = (vm_cluster_id, vm_result_table_name)

    results: list[dict[str, Any]] = []
    refresh_spaces: set[tuple[str, str]] = set()
    refreshed_table_ids: list[str] = []

    for short_link in records:
        # 所属空间由 apply 时确定，update 只允许校验一致性，不承担迁移空间语义。
        current_space_type = short_link.space_type
        current_is_global = short_link.is_global if is_global is None else is_global
        current_query_router_config = (
            models.VMShortLinkRecord.normalize_query_router_config(query_router_config, current_space_type)
            if query_router_config is not None
            else short_link.normalized_query_router_config
        )
        vm_cluster_id = short_link.vm_cluster_id
        vm_result_table_name = short_link.vm_result_table_name
        is_updated = False

        if refresh_bkbase:
            vm_cluster_id, vm_result_table_name = vmrt_infos[short_link.vm_result_table_id]

        with transaction.atomic():
            if refresh_bkbase:
                _, is_updated = _sync_vm_short_link_metadata(
                    vmrt=short_link.vm_result_table_id,
                    table_id=short_link.table_id,
                    vm_cluster_id=vm_cluster_id,
                    vm_result_table_name=vm_result_table_name,
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=bk_tenant_id,
                    operator=operator,
                )

            short_link.vm_result_table_name = vm_result_table_name
            short_link.vm_cluster_id = vm_cluster_id
            short_link.query_router_config = current_query_router_config
            short_link.is_global = current_is_global
            short_link.updater = operator
            short_link.save(
                update_fields=[
                    "vm_result_table_name",
                    "vm_cluster_id",
                    "query_router_config",
                    "is_global",
                    "updater",
                    "update_time",
                ]
            )

        refresh_spaces.add((short_link.space_type, short_link.space_id))
        refreshed_table_ids.append(short_link.table_id)
        results.append(
            {
                "vmrt": short_link.vm_result_table_id,
                "table_id": short_link.table_id,
                "space_type": short_link.space_type,
                "space_id": short_link.space_id,
                "bk_tenant_id": bk_tenant_id,
                "vm_cluster_id": short_link.vm_cluster_id,
                "is_global": short_link.is_global,
                "query_router_config": short_link.query_router_config,
                "is_updated_metrics": is_updated,
            }
        )

    if refresh_router and refreshed_table_ids:
        _refresh_short_link_spaces(
            bk_tenant_id=bk_tenant_id,
            refresh_spaces=refresh_spaces,
            table_ids=refreshed_table_ids,
        )

    return results


def switch_vm_short_links(
    bk_tenant_id: str,
    bk_biz_id: int,
    is_enabled: bool,
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
) -> dict[str, Any]:
    """启用或停用短链路，不改变删除态。"""
    qs = _filter_vm_short_links(bk_tenant_id=bk_tenant_id, table_ids=table_ids, vmrts=vmrts)
    records = list(qs)
    _validate_vm_short_link_records_exist(records=records, table_ids=table_ids, vmrts=vmrts)
    _validate_vm_short_link_records_in_biz(
        records=records,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        action="switch_vm_short_links",
    )
    updated_table_ids = [record.table_id for record in records]
    refresh_spaces = _owner_spaces(records)

    with transaction.atomic():
        qs.update(is_enabled=is_enabled, updater=operator)
        models.ResultTable.objects.filter(table_id__in=updated_table_ids, bk_tenant_id=bk_tenant_id).update(
            is_enable=is_enabled, last_modify_user=operator
        )
        models.TimeSeriesGroup.objects.filter(table_id__in=updated_table_ids, bk_tenant_id=bk_tenant_id).update(
            is_enable=is_enabled, last_modify_user=operator
        )

    if refresh_router and updated_table_ids:
        _refresh_short_link_spaces(
            bk_tenant_id=bk_tenant_id,
            refresh_spaces=refresh_spaces,
            table_ids=updated_table_ids,
        )

    return {
        "updated_count": len(records),
        "table_ids": updated_table_ids,
        "is_enabled": is_enabled,
    }


def delete_vm_short_links(
    bk_tenant_id: str,
    bk_biz_id: int,
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
) -> dict[str, Any]:
    qs = _filter_vm_short_links(bk_tenant_id=bk_tenant_id, table_ids=table_ids, vmrts=vmrts)
    records = list(qs)
    _validate_vm_short_link_records_exist(records=records, table_ids=table_ids, vmrts=vmrts)
    _validate_vm_short_link_records_in_biz(
        records=records,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        action="delete_vm_short_links",
    )
    deleted_table_ids = [record.table_id for record in records]
    refresh_spaces = _owner_spaces(records)

    with transaction.atomic():
        qs.update(is_enabled=False, is_deleted=True, updater=operator)
        models.ResultTable.objects.filter(table_id__in=deleted_table_ids, bk_tenant_id=bk_tenant_id).update(
            is_enable=False, is_deleted=True, last_modify_user=operator
        )
        models.TimeSeriesGroup.objects.filter(table_id__in=deleted_table_ids, bk_tenant_id=bk_tenant_id).update(
            is_enable=False, is_delete=True, last_modify_user=operator
        )

    if deleted_table_ids:
        RedisTools.hdel(RESULT_TABLE_DETAIL_KEY, _compose_detail_redis_fields(deleted_table_ids, bk_tenant_id))
        logger.info(
            "delete_vm_short_links: deleted result table detail redis fields: %s",
            json.dumps(deleted_table_ids),
        )

    if refresh_router:
        _refresh_short_link_spaces(bk_tenant_id=bk_tenant_id, refresh_spaces=refresh_spaces)

    return {
        "deleted_count": len(records),
        "table_ids": deleted_table_ids,
    }
