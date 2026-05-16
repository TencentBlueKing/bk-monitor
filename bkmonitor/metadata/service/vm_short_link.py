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
DEFAULT_SPACE_TYPE = SpaceTypes.BKCC.value


def make_short_link_table_id(vmrt: str) -> str:
    """将真实 VMRT 转成监控侧用于查询路由的虚拟 RT。"""
    return f"{vmrt}.__default__".lower()


def get_vm_result_table_name(table_info: dict[str, Any], vmrt: str) -> str:
    """优先使用 BKBase 返回的别名作为展示名，避免从 VMRT 字符串反推。"""
    return table_info.get("result_table_name_alias") or table_info.get("result_table_name") or vmrt


def parse_space_id_from_vmrt(vmrt: str) -> str:
    """默认从 VMRT 前缀推导归属业务，支持调用方显式传入 space_id 覆盖。"""
    space_id = vmrt.split("_", 1)[0]
    if not space_id:
        raise ValueError(f"invalid vmrt: {vmrt}")
    return space_id


def _get_vmrt_info(bk_tenant_id: str, vmrt: str) -> tuple[int, str]:
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
    return vm_cluster_id, get_vm_result_table_name(table_info, vmrt)


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
    table_id: str, vm_result_table_name: str, space_id: str, bk_tenant_id: str, operator: str
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
            "bk_biz_id": int(space_id) if str(space_id).lstrip("-").isdigit() else 0,
            "is_deleted": False,
            "is_enable": True,
        },
    )


def _get_router_space_types(bk_tenant_id: str, query_router_config: dict[str, Any]) -> set[str]:
    """根据查询路由配置计算需要刷新的空间类型集合。"""
    router_space_type = query_router_config[models.VMShortLinkRecord.QUERY_ROUTER_SPACE_TYPE]
    if router_space_type != SpaceTypes.ALL.value:
        return {router_space_type}

    return set(
        models.Space.objects.filter(bk_tenant_id=bk_tenant_id, space_type_id__in=SpaceTableIDRedis.SUPPORT_SPACE_TYPES)
        .values_list("space_type_id", flat=True)
        .distinct()
    )


def _refresh_short_link_router(
    bk_tenant_id: str,
    owner_space_type: str,
    space_ids: set[str],
    table_ids: list[str],
    is_global: bool,
    query_router_config: dict[str, Any],
) -> None:
    """刷新短链路相关查询路由；全局短链路会影响 query_router_config 命中的空间。"""
    redis = SpaceTableIDRedis()
    redis.push_table_id_detail(table_id_list=table_ids, is_publish=True, bk_tenant_id=bk_tenant_id)

    refresh_spaces = {(owner_space_type, space_id) for space_id in space_ids}
    if is_global:
        for router_space_type in _get_router_space_types(bk_tenant_id, query_router_config):
            refresh_spaces.update(
                (router_space_type, space_id)
                for space_id in models.Space.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    space_type_id=router_space_type,
                ).values_list("space_id", flat=True)
            )

    for space_type, space_id in refresh_spaces:
        redis.push_space_table_ids(space_type=space_type, space_id=str(space_id), is_publish=True)


def apply_vm_short_links(
    vmrts: list[str],
    bk_tenant_id: str,
    space_type: str = DEFAULT_SPACE_TYPE,
    space_id: str | None = None,
    is_global: bool = False,
    query_router_config: dict[str, Any] | None = None,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    refreshed_space_ids: set[str] = set()
    refreshed_table_ids: list[str] = []
    normalized_query_router_config = models.VMShortLinkRecord.normalize_query_router_config(
        query_router_config, space_type
    )

    for vmrt in vmrts:
        # space_type + space_id 始终表示短链路归属空间，全局表也保留这个归属关系。
        current_space_id = str(space_id or parse_space_id_from_vmrt(vmrt))
        table_id = make_short_link_table_id(vmrt)
        vm_cluster_id, vm_result_table_name = _get_vmrt_info(bk_tenant_id=bk_tenant_id, vmrt=vmrt)

        with transaction.atomic():
            _, rt_created = _upsert_result_table(
                table_id=table_id,
                vm_result_table_name=vm_result_table_name,
                space_id=current_space_id,
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

            short_link, short_link_created = models.VMShortLinkRecord.objects.update_or_create(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                defaults={
                    "space_type": space_type,
                    "space_id": current_space_id,
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

            ts_group, _ = models.TimeSeriesGroup.objects.update_or_create(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                defaults={
                    # TimeSeriesGroup.data_source 会将 0 识别为无监控侧 DataSource，并直接走 BKBase 指标发现。
                    "bk_data_id": SHORT_LINK_BK_DATA_ID,
                    "time_series_group_name": vm_result_table_name,
                    "bk_biz_id": int(current_space_id) if current_space_id.lstrip("-").isdigit() else 0,
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
            is_updated = ts_group.update_metrics(metrics_info)

        refreshed_space_ids.add(current_space_id)
        refreshed_table_ids.append(table_id)
        results.append(
            {
                "vmrt": vmrt,
                "table_id": table_id,
                "space_type": short_link.space_type,
                "space_id": short_link.space_id,
                "bk_tenant_id": bk_tenant_id,
                "vm_cluster_id": vm_cluster_id,
                "created": rt_created or short_link_created,
                "is_updated_metrics": is_updated,
            }
        )

    if refresh_router and refreshed_table_ids:
        _refresh_short_link_router(
            bk_tenant_id=bk_tenant_id,
            owner_space_type=space_type,
            space_ids=refreshed_space_ids,
            table_ids=refreshed_table_ids,
            is_global=is_global,
            query_router_config=normalized_query_router_config,
        )

    return results


def _compose_detail_redis_fields(table_ids: list[str], bk_tenant_id: str) -> list[str]:
    """按 result_table_detail 的真实 Redis field 形态组装待清理字段。"""
    fields = [reformat_table_id(table_id) for table_id in table_ids]
    if settings.ENABLE_MULTI_TENANT_MODE:
        fields = [f"{field}|{bk_tenant_id}" for field in fields]
    return fields


def delete_vm_short_links(
    bk_tenant_id: str,
    table_ids: list[str] | None = None,
    vmrts: list[str] | None = None,
    operator: str = DEFAULT_OPERATOR,
    refresh_router: bool = True,
) -> dict[str, Any]:
    if not table_ids and not vmrts:
        raise ValueError("table_ids and vmrts cannot both be empty")

    qs = models.VMShortLinkRecord.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    if table_ids:
        qs = qs.filter(table_id__in=table_ids)
    if vmrts:
        qs = qs.filter(vm_result_table_id__in=vmrts)

    records = list(qs)
    deleted_table_ids = [record.table_id for record in records]
    # 删除全局短链路时，需要额外刷新 query_router_config 命中的空间，否则非归属空间会残留旧路由。
    refresh_spaces: set[tuple[str, str]] = set()
    for record in records:
        refresh_spaces.add((record.space_type, record.space_id))
        if record.is_global:
            for router_space_type in _get_router_space_types(bk_tenant_id, record.normalized_query_router_config):
                refresh_spaces.update(
                    (router_space_type, space_id)
                    for space_id in models.Space.objects.filter(
                        bk_tenant_id=bk_tenant_id,
                        space_type_id=router_space_type,
                    ).values_list("space_id", flat=True)
                )

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
        redis = SpaceTableIDRedis()
        for current_space_type, current_space_id in refresh_spaces:
            redis.push_space_table_ids(space_type=current_space_type, space_id=str(current_space_id), is_publish=True)

    return {
        "deleted_count": len(records),
        "table_ids": deleted_table_ids,
    }
