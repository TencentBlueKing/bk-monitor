"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ResolvedVmResultTableConfig(TypedDict):
    """VMRT 对应的 bkbase ResultTable 与 VM storage 快照。"""

    result_table_id: str
    vm_result_table_id: str
    bkbase_result_table_name: str
    vm_storage_name: str


def resolve_vm_result_table_configs(
    *,
    bk_tenant_id: str,
    vm_result_table_ids: list[str],
) -> list[ResolvedVmResultTableConfig]:
    """批量把 VMRT 解析成 V4 Flow source 需要的 ResultTable.name。

    查询优先级：
    1. `ResultTableConfig.bkbase_table_id == vm_rt` 直接命中真实 bkbase ResultTable。
    2. 未命中时，用 `AccessVMRecord.vm_result_table_id -> result_table_id` 回退查询 ResultTableConfig。

    无论哪种命中方式，都需要 AccessVMRecord 提供 VM storage 归属。
    """

    vm_table_ids = list(dict.fromkeys(vm_result_table_ids))
    if not vm_table_ids:
        return []

    direct_configs = _latest_result_table_configs_by_bkbase_table_id(bk_tenant_id, vm_table_ids)
    access_records = _latest_access_vm_records_by_vm_table_id(bk_tenant_id, vm_table_ids)
    fallback_configs = _latest_result_table_configs_by_table_id(
        bk_tenant_id,
        [record.result_table_id for record in access_records.values()],
    )
    cluster_names = _cluster_names_by_id(
        bk_tenant_id,
        [record.vm_cluster_id for record in access_records.values() if record.vm_cluster_id],
    )

    result: list[ResolvedVmResultTableConfig] = []
    missing_access_records: list[str] = []
    missing_result_table_configs: list[str] = []
    missing_clusters: list[str] = []
    for vm_table_id in vm_table_ids:
        access_record = access_records.get(vm_table_id)
        if access_record is None:
            missing_access_records.append(vm_table_id)
            continue

        result_table_config = direct_configs.get(vm_table_id) or fallback_configs.get(access_record.result_table_id)
        if result_table_config is None:
            missing_result_table_configs.append(vm_table_id)
            continue

        vm_cluster_id = access_record.vm_cluster_id
        vm_storage_name = cluster_names.get(vm_cluster_id or 0)
        if not vm_storage_name:
            missing_clusters.append(vm_table_id)
            continue

        result.append(
            {
                "result_table_id": result_table_config.table_id,
                "vm_result_table_id": vm_table_id,
                "bkbase_result_table_name": result_table_config.name,
                "vm_storage_name": vm_storage_name,
            }
        )

    if missing_access_records:
        raise ValueError(f"source vm result tables are not found in AccessVMRecord: {missing_access_records}")
    if missing_result_table_configs:
        raise ValueError(f"source vm result tables are not found in ResultTableConfig: {missing_result_table_configs}")
    if missing_clusters:
        raise ValueError(f"source vm result tables are not found in ClusterInfo: {missing_clusters}")
    return result


def _latest_result_table_configs_by_bkbase_table_id(bk_tenant_id: str, vm_table_ids: list[str]) -> dict[str, Any]:
    """按 bkbase_table_id 批量查最新 ResultTableConfig。"""

    from metadata import models as metadata_models

    result: dict[str, Any] = {}
    queryset = metadata_models.ResultTableConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        bkbase_table_id__in=vm_table_ids,
    ).order_by("-last_modify_time", "-id")
    for result_table_config in queryset:
        result.setdefault(result_table_config.bkbase_table_id, result_table_config)
    return result


def _latest_result_table_configs_by_table_id(bk_tenant_id: str, table_ids: list[str]) -> dict[str, Any]:
    """按 metadata table_id 批量查最新 ResultTableConfig。"""

    from metadata import models as metadata_models

    result: dict[str, Any] = {}
    queryset = metadata_models.ResultTableConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id__in=list(dict.fromkeys(table_ids)),
    ).order_by("-last_modify_time", "-id")
    for result_table_config in queryset:
        result.setdefault(result_table_config.table_id, result_table_config)
    return result


def _latest_access_vm_records_by_vm_table_id(bk_tenant_id: str, vm_table_ids: list[str]) -> dict[str, Any]:
    """按 VMRT 批量查最新 AccessVMRecord。"""

    from metadata import models as metadata_models

    result: dict[str, Any] = {}
    queryset = metadata_models.AccessVMRecord.objects.filter(
        bk_tenant_id=bk_tenant_id,
        vm_result_table_id__in=vm_table_ids,
    ).order_by("-id")
    for access_record in queryset:
        result.setdefault(access_record.vm_result_table_id, access_record)
    return result


def _cluster_names_by_id(bk_tenant_id: str, cluster_ids: list[int]) -> dict[int, str]:
    """批量查询 VM storage 集群名称。"""

    from metadata import models as metadata_models

    result: dict[int, str] = {}
    queryset = metadata_models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        cluster_type=metadata_models.ClusterInfo.TYPE_VM,
        cluster_id__in=list(dict.fromkeys(cluster_ids)),
    )
    for cluster in queryset:
        result[cluster.cluster_id] = cluster.cluster_name
    return result
