"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

本模块用于重建 BKBase V4 DataLink 组件间的关联关系。

背景：
    sync_bkbase_v4_datalink_components 将 BKBase 侧所有组件同步回监控平台后，
    这些组件的 data_link_name 字段均为空，组件间关联关系缺失，无法串成完整的 DataLink。

用途：
    以 DataBus 为单位，通过已有的关联字段（sink_names、bkbase_result_table_name）
    重建组件间关系，补充 data_link_name，并创建/更新 DataLink 记录。

调用方式：
    from metadata.models.data_link.relation import rebuild_bkbase_v4_datalink_relation
    rebuild_bkbase_v4_datalink_relation(bk_tenant_id="system", namespace="bkmonitor")
"""

import logging
from collections.abc import Sequence
from typing import TypeAlias, cast

from django.db import transaction

from bkmonitor.utils.tenant import get_tenant_default_biz_id
from metadata.models import (
    AccessVMRecord,
    BkBaseResultTable,
    ClusterInfo,
    DataSourceResultTable,
    DorisStorage,
    ESStorage,
    ResultTable,
    SurrealDBStorage,
)
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link import utils
from metadata.models.data_link.data_link_configs import (
    BasereportSinkConfig,
    ConditionalSinkConfig,
    DataBusConfig,
    DataIdConfig,
    DataLinkResourceConfigBase,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    GraphRelationBindingConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)

logger = logging.getLogger("metadata")

SimpleStorageBindingConfig: TypeAlias = VMStorageBindingConfig | ESStorageBindingConfig | DorisStorageBindingConfig
REBUILDABLE_DATABUS_STATUSES = {
    DataLinkResourceStatus.OK.value,
    DataLinkResourceStatus.PENDING.value,
}

# sink kind → 对应的 Model 类映射
SINK_KIND_TO_MODEL: dict[str, type[DataLinkResourceConfigBase]] = {
    DataLinkKind.VMSTORAGEBINDING.value: VMStorageBindingConfig,
    DataLinkKind.ESSTORAGEBINDING.value: ESStorageBindingConfig,
    DataLinkKind.DORISBINDING.value: DorisStorageBindingConfig,
    DataLinkKind.SURREALDBBINDING.value: SurrealDBBindingConfig,
    DataLinkKind.CONDITIONALSINK.value: ConditionalSinkConfig,
    DataLinkKind.BASEREPORTSINK.value: BasereportSinkConfig,
}

# 存储绑定类型（需要关联 ResultTableConfig，ConditionalSink 不需要）
STORAGE_BINDING_MODELS = (
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
    SurrealDBBindingConfig,
)

SIMPLE_STORAGE_BINDING_MODELS: dict[str, type[SimpleStorageBindingConfig]] = {
    DataLinkKind.VMSTORAGEBINDING.value: VMStorageBindingConfig,
    DataLinkKind.ESSTORAGEBINDING.value: ESStorageBindingConfig,
    DataLinkKind.DORISBINDING.value: DorisStorageBindingConfig,
}

# Graph dual-write creates separate VM and SurrealDB Databus rows. During rebuild we need to fold sibling rows
# back into one DataLink so GraphRelationBindingConfig can keep the unified write_mode.
def _parse_sink_names(sink_names: Sequence[str], databus_name: str) -> dict[str, list[str]] | None:
    sink_map: dict[str, list[str]] = {}
    for entry in sink_names:
        if ":" not in entry:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] has invalid sink_names entry->[%s], skip",
                databus_name,
                entry,
            )
            return None
        kind, name = entry.split(":", 1)
        sink_map.setdefault(kind, []).append(name)
    return sink_map


def _load_sink_instances(
    databus: DataBusConfig,
    sink_map: dict[str, list[str]],
) -> list[DataLinkResourceConfigBase] | None:
    sink_instances: list[DataLinkResourceConfigBase] = []
    for kind, names in sink_map.items():
        model = SINK_KIND_TO_MODEL.get(kind)
        if model is None:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] has unknown sink kind->[%s], skip",
                databus.name,
                kind,
            )
            return None
        queryset = model.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name__in=names,
        )
        instances_by_name = {instance.name: instance for instance in queryset}
        missing = [name for name in names if name not in instances_by_name]
        if missing:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] sink component kind->[%s] name->[%s] not found in DB, skip",
                databus.name,
                kind,
                ", ".join(missing),
            )
            return None
        sink_instances.extend(instances_by_name[name] for name in names)
    return sink_instances


def _merge_graph_dual_write_sibling_databus(
    databus: DataBusConfig,
    sink_instances: list[DataLinkResourceConfigBase],
    resolved_bk_data_id: int | None = None,
) -> tuple[list[DataBusConfig], list[DataLinkResourceConfigBase]]:
    def graph_result_table_group_key(rt_name: str) -> str:
        if rt_name.endswith("_graph"):
            rt_name = rt_name[: -len("_graph")]
        return f"graph-rt-group:{rt_name}"

    def graph_storage_keys(instances: list[DataLinkResourceConfigBase]) -> set[str]:
        keys: set[str] = set()
        storage_bindings = [
            instance
            for instance in instances
            if isinstance(instance, (VMStorageBindingConfig, SurrealDBBindingConfig))
        ]
        rt_names = [instance.bkbase_result_table_name for instance in storage_bindings if instance.bkbase_result_table_name]
        rt_table_id_map = {
            rt.name: rt.table_id
            for rt in ResultTableConfig.objects.filter(
                bk_tenant_id=databus.bk_tenant_id,
                namespace=databus.namespace,
                name__in=rt_names,
            )
        }
        fallback_bk_data_id = resolved_bk_data_id or databus.bk_data_id
        data_source_result_table_ids = list(
            DataSourceResultTable.objects.filter(
                bk_data_id=fallback_bk_data_id,
                bk_tenant_id=databus.bk_tenant_id,
            )
            .order_by()
            .values_list("table_id", flat=True)
            .distinct()
        )
        data_source_result_table_id = (
            data_source_result_table_ids[0] if len(data_source_result_table_ids) == 1 else ""
        )
        for instance in storage_bindings:
            table_id = (
                instance.table_id
                or rt_table_id_map.get(instance.bkbase_result_table_name, "")
                or data_source_result_table_id
            )
            if table_id:
                keys.add(f"table:{table_id}")
            if instance.bkbase_result_table_name:
                keys.add(f"rt:{instance.bkbase_result_table_name}")
                keys.add(graph_result_table_group_key(instance.bkbase_result_table_name))
        return keys

    current_has_vm = any(isinstance(instance, VMStorageBindingConfig) for instance in sink_instances)
    current_has_surrealdb = any(isinstance(instance, SurrealDBBindingConfig) for instance in sink_instances)
    if current_has_vm and current_has_surrealdb:
        return [databus], sink_instances
    if not (current_has_vm or current_has_surrealdb):
        return [databus], sink_instances

    current_keys = graph_storage_keys(sink_instances)
    if not current_keys:
        return [databus], sink_instances

    candidate_bk_data_ids = [databus.bk_data_id]
    if resolved_bk_data_id and resolved_bk_data_id not in candidate_bk_data_ids:
        candidate_bk_data_ids.append(resolved_bk_data_id)
    candidate_databuses = DataBusConfig.objects.filter(
        bk_tenant_id=databus.bk_tenant_id,
        namespace=databus.namespace,
        bk_data_id__in=candidate_bk_data_ids,
        data_id_name=databus.data_id_name,
        data_link_name="",
    ).exclude(id=databus.id)
    for candidate in candidate_databuses:
        candidate_sink_map = _parse_sink_names(candidate.sink_names, candidate.name)
        if candidate_sink_map is None:
            continue
        candidate_sinks = _load_sink_instances(candidate, candidate_sink_map)
        if candidate_sinks is None:
            continue
        combined_sinks = [*sink_instances, *candidate_sinks]
        has_vm = any(isinstance(instance, VMStorageBindingConfig) for instance in combined_sinks)
        has_surrealdb = any(isinstance(instance, SurrealDBBindingConfig) for instance in combined_sinks)
        if not (has_vm and has_surrealdb):
            continue
        if current_keys & graph_storage_keys(candidate_sinks):
            return [databus, candidate], combined_sinks

    return [databus], sink_instances


# 重建链路名称前缀，便于与正常创建的链路区分，支持回溯和回滚
REBUILT_DATA_LINK_NAME_PREFIX = "rebuilt__"


def _compose_rebuilt_graph_binding_name(data_link_name: str) -> str:
    """Keep rebuilt GraphRelationBindingConfig.name within its 64-char DB limit."""
    return utils.compose_bkdata_table_id(data_link_name)


def _compose_rebuilt_graph_data_link_name(databus: DataBusConfig) -> str:
    raw_name = f"{REBUILT_DATA_LINK_NAME_PREFIX}{databus.bk_tenant_id}__{databus.namespace}__{databus.name}"
    return f"{REBUILT_DATA_LINK_NAME_PREFIX}{utils.compose_bkdata_table_id(raw_name)}"


def _find_databus_name_for_sink(
    databus_instances: list[DataBusConfig],
    sink_kind: str,
    sink_name: str,
) -> str:
    if not sink_name:
        return ""
    target_sink = f"{sink_kind}:{sink_name}"
    for databus in databus_instances:
        if target_sink in (databus.sink_names or []):
            return databus.name
    return sink_name


def _restore_rebuilt_surrealdb_storage(surrealdb_binding: SurrealDBBindingConfig | None) -> None:
    if not surrealdb_binding or not surrealdb_binding.table_id or not surrealdb_binding.surrealdb_cluster_name:
        return

    cluster = ClusterInfo.objects.filter(
        bk_tenant_id=surrealdb_binding.bk_tenant_id,
        cluster_type=ClusterInfo.TYPE_SURREALDB,
        cluster_name=surrealdb_binding.surrealdb_cluster_name,
    ).first()
    if not cluster:
        logger.warning(
            "rebuild_databus_relation: SurrealDB cluster name->[%s] tenant->[%s] not found, "
            "skip local SurrealDBStorage rebuild for table_id->[%s]",
            surrealdb_binding.surrealdb_cluster_name,
            surrealdb_binding.bk_tenant_id,
            surrealdb_binding.table_id,
        )
        return

    SurrealDBStorage.create_table(
        table_id=surrealdb_binding.table_id,
        is_sync_db=False,
        bk_tenant_id=surrealdb_binding.bk_tenant_id,
        table_type=surrealdb_binding.table_type,
        vertices=surrealdb_binding.vertices,
        relations=surrealdb_binding.relations,
        storage_cluster_id=cluster.cluster_id,
    )


def _get_single_data_source_table_id(databus: DataBusConfig, data_source) -> str:
    table_ids = list(
        DataSourceResultTable.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            bk_data_id=data_source.bk_data_id,
        ).values_list("table_id", flat=True)
    )
    table_ids = list(dict.fromkeys(table_id for table_id in table_ids if table_id))
    return table_ids[0] if len(table_ids) == 1 else ""


def _resolve_rebuild_result_table_id(
    binding_instance: DataLinkResourceConfigBase,
    rt_instance: ResultTableConfig,
    vmrt_to_table_id: dict[str, str],
    databus: DataBusConfig,
    data_source,
) -> str:
    table_id = getattr(binding_instance, "table_id", "") or rt_instance.table_id
    if table_id:
        return table_id
    if isinstance(binding_instance, SurrealDBBindingConfig):
        return _get_single_data_source_table_id(databus, data_source)
    if isinstance(binding_instance, VMStorageBindingConfig):
        return vmrt_to_table_id.get(rt_instance.bkbase_table_id, "") or _get_single_data_source_table_id(
            databus, data_source
        )
    return vmrt_to_table_id.get(rt_instance.bkbase_table_id, "")

# etl_config → data_link_strategy 映射
ETL_CONFIG_TO_STRATEGY = {
    "bk_standard_v2_time_series": DataLink.BK_STANDARD_V2_TIME_SERIES,
    "bk_exporter": DataLink.BK_EXPORTER_TIME_SERIES,
    "bk_standard": DataLink.BK_STANDARD_TIME_SERIES,
    "bk_standard_v2_event": DataLink.BK_STANDARD_V2_EVENT,
    "bk_system_basereport": DataLink.BASEREPORT_TIME_SERIES_V1,
    "bk_multi_tenancy_basereport": DataLink.BASEREPORT_TIME_SERIES_V1,
    "bk_multi_tenancy_system_proc_perf": DataLink.SYSTEM_PROC_PERF,
    "bk_multi_tenancy_system_proc_port": DataLink.SYSTEM_PROC_PORT,
    "bk_multi_tenancy_agent_event": DataLink.BASE_EVENT_V1,
    "bk_flat_batch": DataLink.BK_LOG,
}


def rebuild_simple_databus_relation(
    databus: DataBusConfig, dry_run: bool = True
) -> DataLink | dict[str, object] | None:
    """重建简单的 DataBus 关联关系。

    适用场景:
        DataBusConfig的data_link_name为空
        DataSource的类型为bkdata, 关联表仅有一张, 且DataBus.sinks仅为VMStorageBinding/ESStorageBinding/DorisStorageBinding
        完成databus/binding/result_table的关联关系重建

    Args:
        databus: 待处理的 DataBusConfig 实例，其 data_link_name 应为空。
        dry_run: 若为 True，仅解析关联组件信息并以 dict 返回，不写入数据库。

    Returns:
        dry_run=False 时：成功返回创建/更新的 DataLink 对象，失败返回 None。
        dry_run=True 时：成功返回包含关联信息的 dict，失败返回 None。
    """
    from metadata.models.data_source import DataSource

    databus_name = databus.name
    rebuilt_data_link_name = f"{REBUILT_DATA_LINK_NAME_PREFIX}{databus.bk_tenant_id}_{databus_name}"

    # Step 1: 简单链路只处理尚未归属 DataLink 的 DataBus，已有归属直接跳过避免覆盖关系。
    if databus.data_link_name and databus.data_link_name != rebuilt_data_link_name:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] already has data_link_name->[%s], skip",
            databus_name,
            databus.data_link_name,
        )
        return None
    if databus.status not in REBUILDABLE_DATABUS_STATUSES:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] status->[%s] is not Ok/Pending, skip",
            databus_name,
            databus.status,
        )
        return None

    # Step 2: 通过 DataBus.source 指向的 DataIdConfig 解析真实 bk_data_id，并校验 DataBus 记录一致性。
    try:
        data_id_config = DataIdConfig.objects.get(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name=databus.data_id_name,
        )
    except DataIdConfig.DoesNotExist:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] DataIdConfig with data_id_name->[%s] not found, skip",
            databus_name,
            databus.data_id_name,
        )
        return None

    resolved_bk_data_id = data_id_config.bk_data_id
    if not resolved_bk_data_id:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] DataIdConfig name->[%s] has empty bk_data_id->[%s], skip",
            databus_name,
            data_id_config.name,
            resolved_bk_data_id,
        )
        return None

    # Step 3: 简单链路优先限定为 BKDATA 来源；VM 迁移链路允许通过 AccessVMRecord 反查监控侧 DataSource。
    dsrt_from_vm_record = None
    data_source = DataSource.objects.filter(
        bk_tenant_id=databus.bk_tenant_id,
        bk_data_id=resolved_bk_data_id,
    ).first()
    if not data_source:
        if not _is_vm_only_simple_sink_names(databus.sink_names):
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] DataSource with bk_data_id->[%s] not found, skip",
                databus_name,
                resolved_bk_data_id,
            )
            return None

        # v3 迁移 v4 的 VM 链路可能由 BKBase 独立申请 data_id，监控侧 DataSource 中没有这条 bk_data_id。
        # 此时只能先用 AccessVMRecord.bk_base_data_id 找到监控 table_id，再反查真实 DataSource。
        access_vm_records = list(
            AccessVMRecord.objects.filter(
                bk_tenant_id=databus.bk_tenant_id,
                bk_base_data_id=resolved_bk_data_id,
            )
        )
        if len(access_vm_records) != 1:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] bk_base_data_id->[%s] "
                "got AccessVMRecord count->[%s], skip",
                databus_name,
                resolved_bk_data_id,
                len(access_vm_records),
            )
            return None

        dsrt_from_vm_record = DataSourceResultTable.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            table_id=access_vm_records[0].result_table_id,
        ).first()
        if not dsrt_from_vm_record:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] DataSourceResultTable with table_id->[%s] "
                "not found, skip",
                databus_name,
                access_vm_records[0].result_table_id,
            )
            return None

        data_source = DataSource.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            bk_data_id=dsrt_from_vm_record.bk_data_id,
        ).first()
        if not data_source:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] DataSource with bk_data_id->[%s] not found, skip",
                databus_name,
                dsrt_from_vm_record.bk_data_id,
            )
            return None
    elif data_source.created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.info(
            "rebuild_simple_databus_relation: databus->[%s] DataSource bk_data_id->[%s] created_from->[%s] "
            "is not bkdata, skip",
            databus_name,
            data_source.bk_data_id,
            data_source.created_from,
        )
        return None

    # 检查databus的bk_data_id是否与DataIdConfig的bk_data_id一致
    if databus.bk_data_id != 0 and databus.bk_data_id != data_source.bk_data_id:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] bk_data_id->[%s] "
            "is not equal to DataIdConfig bk_data_id->[%s], skip",
            databus_name,
            databus.bk_data_id,
            data_source.bk_data_id,
        )
        return None

    # Step 4: 简单链路要求 data_id 只关联一张监控结果表，该 table_id 是后续回填的唯一真值源。
    if dsrt_from_vm_record:
        dsrt_instances = [dsrt_from_vm_record]
    else:
        dsrt_instances = list(
            DataSourceResultTable.objects.filter(
                bk_tenant_id=databus.bk_tenant_id,
                bk_data_id=data_source.bk_data_id,
            )
        )
    if len(dsrt_instances) != 1:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] bk_data_id->[%s] got DataSourceResultTable count->[%s], "
            "skip",
            databus_name,
            data_source.bk_data_id,
            len(dsrt_instances),
        )
        return None
    table_id = dsrt_instances[0].table_id

    # 获取结果表所属业务ID，对齐apply_datalink的逻辑
    try:
        result_table = ResultTable.objects.get(bk_tenant_id=databus.bk_tenant_id, table_id=table_id)
    except ResultTable.DoesNotExist:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] ResultTable with table_id->[%s] not found, skip",
            databus_name,
            table_id,
        )
        return None

    if result_table.default_storage in [ClusterInfo.TYPE_VM, ClusterInfo.TYPE_INFLUXDB]:
        target_bk_biz_id = result_table.get_target_bk_biz_id()
        if target_bk_biz_id == 0:
            target_bk_biz_id = get_tenant_default_biz_id(bk_tenant_id=result_table.bk_tenant_id)
    else:
        target_bk_biz_id = result_table.bk_biz_id

    # Step 5: 解析 DataBus.sink_names；只接受直接写入 VM / ES / Doris 的存储绑定。
    sink_instances: list[SimpleStorageBindingConfig] = []
    sink_map: dict[str, list[str]] = {}
    for entry in databus.sink_names:
        if ":" not in entry:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] has invalid sink_names entry->[%s], skip",
                databus_name,
                entry,
            )
            return None
        kind, name = entry.split(":", 1)
        model = SIMPLE_STORAGE_BINDING_MODELS.get(kind)
        if model is None:
            logger.info(
                "rebuild_simple_databus_relation: databus->[%s] has non-simple sink kind->[%s], skip",
                databus_name,
                kind,
            )
            return None
        sink_map.setdefault(kind, []).append(name)

    for kind, names in sink_map.items():
        model = SIMPLE_STORAGE_BINDING_MODELS[kind]
        queryset = model.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name__in=names,
        )
        instances_by_name = {instance.name: instance for instance in queryset}
        missing = [name for name in names if name not in instances_by_name]
        if missing:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] sink component kind->[%s] name->[%s] "
                "not found in DB, skip",
                databus_name,
                kind,
                ", ".join(missing),
            )
            return None
        sink_instances.extend(instances_by_name[name] for name in names)

    if not sink_instances:
        logger.warning("rebuild_simple_databus_relation: databus->[%s] has empty sink_names, skip", databus_name)
        return None

    # Step 6: 检查 sink 冲突，避免把已归属其他链路的 binding 拉进来。
    for instance in sink_instances:
        if instance.data_link_name and instance.data_link_name != rebuilt_data_link_name:
            logger.error(
                "rebuild_simple_databus_relation: databus->[%s] sink component kind->[%s] name->[%s] "
                "already has data_link_name->[%s], conflict detected, skip",
                databus_name,
                instance.kind,
                instance.name,
                instance.data_link_name,
            )
            return None

    # Step 7: 通过 binding.bkbase_result_table_name 找到 ResultTableConfig，并校验本地存储记录。
    rt_name_map: dict[str, list[SimpleStorageBindingConfig]] = {}
    for instance in sink_instances:
        if not instance.bkbase_result_table_name:
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] binding kind->[%s] name->[%s] "
                "has empty bkbase_result_table_name, skip",
                databus_name,
                instance.kind,
                instance.name,
            )
            return None
        rt_name_map.setdefault(instance.bkbase_result_table_name, []).append(instance)

    rts_by_name = {
        rt.name: rt
        for rt in ResultTableConfig.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name__in=list(rt_name_map),
        )
    }
    missing_rts = [name for name in rt_name_map if name not in rts_by_name]
    if missing_rts:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] ResultTableConfig name->[%s] not found in DB, skip",
            databus_name,
            ", ".join(missing_rts),
        )
        return None

    rt_instances = [rts_by_name[name] for name in rt_name_map]
    for rt in rt_instances:
        if rt.data_link_name and rt.data_link_name != rebuilt_data_link_name:
            logger.error(
                "rebuild_simple_databus_relation: databus->[%s] ResultTableConfig name->[%s] "
                "already has data_link_name->[%s], conflict detected, skip",
                databus_name,
                rt.name,
                rt.data_link_name,
            )
            return None
        rt.table_id = table_id

    for sink_instance in sink_instances:
        rt = rts_by_name[sink_instance.bkbase_result_table_name]
        if not _simple_storage_exists(sink_instance, table_id, rt.bkbase_table_id):
            logger.warning(
                "rebuild_simple_databus_relation: databus->[%s] binding kind->[%s] name->[%s] "
                "storage relation for table_id->[%s] bkbase_table_id->[%s] not found, skip",
                databus_name,
                sink_instance.kind,
                sink_instance.name,
                table_id,
                rt.bkbase_table_id,
            )
            return None
        sink_instance.table_id = table_id

    # Step 8: 简单链路只通过 DataSource.etl_config 推断 DataLink 策略。
    strategy = ETL_CONFIG_TO_STRATEGY.get(data_source.etl_config)
    if strategy is None:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] etl_config->[%s] not in strategy map, skip",
            databus_name,
            data_source.etl_config,
        )
        return None

    table_ids = [table_id]
    bkbase_result_table = _build_simple_bkbase_result_table(
        data_link_name=rebuilt_data_link_name,
        databus=databus,
        table_id=table_id,
        rt=rts_by_name[sink_instances[0].bkbase_result_table_name],
        binding=sink_instances[0],
    )
    if bkbase_result_table is None:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] cannot build BkBaseResultTable for table_id->[%s], skip",
            databus_name,
            table_id,
        )
        return None

    # Step 9: dry_run 只返回解析结果，实际重建在事务中统一更新 DataLink 和组件归属。
    if dry_run:
        return {
            "data_link_name": rebuilt_data_link_name,
            "strategy": strategy,
            "bk_data_id": data_source.bk_data_id,
            "table_ids": table_ids,
            "sinks": [{"kind": i.kind, "name": i.name, "table_id": getattr(i, "table_id", "")} for i in sink_instances],
            "result_tables": [{"name": rt.name, "table_id": rt.table_id} for rt in rt_instances],
            "components": _serialize_datalink_components(
                [data_id_config, *rt_instances, *sink_instances, databus],
            ),
            "bkbase_result_table": bkbase_result_table,
        }

    with transaction.atomic():
        data_link, created = DataLink.objects.update_or_create(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            data_link_name=rebuilt_data_link_name,
            defaults={
                "bk_data_id": data_source.bk_data_id,
                "table_ids": table_ids,
                "data_link_strategy": strategy,
            },
        )

        databus.bk_biz_id = target_bk_biz_id
        databus.data_link_name = rebuilt_data_link_name
        databus.bk_data_id = data_source.bk_data_id
        databus.save(update_fields=["data_link_name", "bk_data_id", "bk_biz_id"])

        for instance in sink_instances:
            instance.data_link_name = rebuilt_data_link_name
            instance.bk_biz_id = target_bk_biz_id
        _bulk_update_data_link_name(sink_instances)

        for rt in rt_instances:
            rt.data_link_name = rebuilt_data_link_name
            rt.bk_biz_id = target_bk_biz_id
        ResultTableConfig.objects.bulk_update(rt_instances, ["data_link_name", "table_id", "bk_biz_id"])

        BkBaseResultTable.objects.update_or_create(
            bk_tenant_id=databus.bk_tenant_id,
            data_link_name=rebuilt_data_link_name,
            defaults={
                key: value
                for key, value in bkbase_result_table.items()
                if key not in {"bk_tenant_id", "data_link_name"}
            },
        )

    logger.info(
        "rebuild_simple_databus_relation: databus->[%s] relation rebuilt successfully, "
        "strategy->[%s], table_ids->[%s], created->[%s]",
        databus_name,
        strategy,
        table_ids,
        created,
    )
    return data_link


def _is_vm_only_simple_sink_names(sink_names: Sequence[str]) -> bool:
    """判断 sink_names 是否只包含 VMStorageBinding，用于 VM 迁移链路的 DataSource 反查兜底。"""
    if not sink_names:
        return False
    for entry in sink_names:
        if ":" not in entry:
            return False
        kind, _ = entry.split(":", 1)
        if kind != DataLinkKind.VMSTORAGEBINDING.value:
            return False
    return True


def _is_graph_relation_rebuild(
    databus: DataBusConfig,
    sink_map: dict[str, list[str]],
    rt_instances: Sequence[ResultTableConfig],
) -> bool:
    if DataLinkKind.SURREALDBBINDING.value in sink_map:
        return True
    if DataLinkKind.VMSTORAGEBINDING.value not in sink_map:
        return False

    bkbase_rt_names = [rt.name for rt in rt_instances if rt.name]
    if not bkbase_rt_names:
        return False
    existing_datalink_names = list(
        BkBaseResultTable.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            bkbase_rt_name__in=bkbase_rt_names,
        ).values_list("data_link_name", flat=True)
    )
    if not existing_datalink_names:
        return False

    return DataLink.objects.filter(
        bk_tenant_id=databus.bk_tenant_id,
        data_link_name__in=existing_datalink_names,
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    ).exists()


def _build_simple_bkbase_result_table(
    data_link_name: str,
    databus: DataBusConfig,
    table_id: str,
    rt: ResultTableConfig,
    binding: SimpleStorageBindingConfig,
) -> dict[str, object] | None:
    """组装 simple rebuild 需要补写的 BkBaseResultTable 记录。"""
    storage_info = _get_simple_storage_info(binding, table_id, rt.bkbase_table_id)
    if storage_info is None:
        return None
    storage_type, storage_cluster_id = storage_info
    return {
        "bk_tenant_id": databus.bk_tenant_id,
        "data_link_name": data_link_name,
        "bkbase_data_name": databus.data_id_name,
        "storage_type": storage_type,
        "monitor_table_id": table_id,
        "storage_cluster_id": storage_cluster_id,
        "status": DataLinkResourceStatus.OK.value,
        "bkbase_table_id": rt.bkbase_table_id,
        "bkbase_rt_name": rt.name,
    }


def _get_simple_storage_info(
    binding: SimpleStorageBindingConfig,
    table_id: str,
    bkbase_table_id: str,
) -> tuple[str, int | None] | None:
    """返回 simple storage binding 对应的 BkBaseResultTable 存储类型与集群 ID。"""
    if isinstance(binding, VMStorageBindingConfig):
        record = AccessVMRecord.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            result_table_id=table_id,
            vm_result_table_id=bkbase_table_id,
        ).first()
        if record is None:
            return None
        return ClusterInfo.TYPE_VM, record.vm_cluster_id or record.storage_cluster_id
    if isinstance(binding, ESStorageBindingConfig):
        storage = ESStorage.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            table_id=table_id,
        ).first()
        if storage is None:
            return None
        return ClusterInfo.TYPE_ES, storage.storage_cluster_id
    if isinstance(binding, DorisStorageBindingConfig):
        storage = DorisStorage.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            table_id=table_id,
            bkbase_table_id=bkbase_table_id,
        ).first()
        if storage is None:
            return None
        return ClusterInfo.TYPE_DORIS, storage.storage_cluster_id
    return None


def _simple_storage_exists(
    binding: SimpleStorageBindingConfig,
    table_id: str,
    bkbase_table_id: str,
) -> bool:
    """确认简单链路的本地存储侧记录确实存在。

    DataSourceResultTable.table_id 是简单链路回填到 ResultTable / Binding 的唯一真值源；这里按不同
    StorageBinding 的本地落库模型做二次校验，避免只凭 BKBase Binding 关系误建不存在的存储关联。
    """
    if isinstance(binding, VMStorageBindingConfig):
        # VM 需要同时匹配监控 table_id 与 BKBase 侧 ResultTableId，防止同一个 data_id 指到了错误的 VM 表。
        if not bkbase_table_id:
            logger.warning(
                "rebuild_simple_databus_relation: VmStorageBinding name->[%s] has empty bkbase_table_id "
                "for table_id->[%s]",
                binding.name,
                table_id,
            )
            return False
        return AccessVMRecord.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            result_table_id=table_id,
            vm_result_table_id=bkbase_table_id,
        ).exists()
    if isinstance(binding, ESStorageBindingConfig):
        # ES 不依赖 AccessVMRecord，单表链路只要求 ESStorage 中存在对应监控 table_id。
        return ESStorage.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            table_id=table_id,
        ).exists()
    if isinstance(binding, DorisStorageBindingConfig):
        # Doris 需要同时匹配监控 table_id 与 BKBase 侧 table_id，避免同一监控表误挂到其他 Doris 物理表。
        if not bkbase_table_id:
            logger.warning(
                "rebuild_simple_databus_relation: DorisStorageBinding name->[%s] has empty bkbase_table_id "
                "for table_id->[%s]",
                binding.name,
                table_id,
            )
            return False
        return DorisStorage.objects.filter(
            bk_tenant_id=binding.bk_tenant_id,
            table_id=table_id,
            bkbase_table_id=bkbase_table_id,
        ).exists()
    return False


def rebuild_databus_relation(databus: DataBusConfig, dry_run: bool = True) -> DataLink | dict[str, object] | None:
    """以单个 DataBus 为单位重建组件关联关系。

    Args:
        databus: 待处理的 DataBusConfig 实例，其 data_link_name 应为空。
        dry_run: 若为 True，仅解析关联组件信息并以 dict 返回，不写入数据库。

    Returns:
        dry_run=False 时：成功返回创建/更新的 DataLink 对象，失败返回 None。
        dry_run=True 时：成功返回包含关联信息的 dict，失败返回 None。

    跳过条件（仅记录日志，不抛出异常）：
        - sink_names 中引用的组件在 DB 中不存在
        - 任意 sink 组件已有非空 data_link_name（冲突）
        - 存储绑定组件关联的 ResultTableConfig 不存在
        - 任意 ResultTableConfig 已有非空 data_link_name（冲突）
        - DataIdConfig 不存在，或其 bk_data_id 为空/0
        - DataSource 不存在（bk_data_id 无对应记录）
        - etl_config 不在映射表中且不满足特殊规则

    冲突处理：
        若任意关联组件已有 data_link_name，说明该组件已属于另一条链路，
        本次重建可能造成数据错乱，因此跳过整个 DataBus。
    """
    from metadata.models.data_source import DataSource

    databus_name = databus.name

    # Step 1: 根据 data_id_name 获取 DataIdConfig，并解析真实 bk_data_id
    try:
        data_id_config = DataIdConfig.objects.get(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name=databus.data_id_name,
        )
    except DataIdConfig.DoesNotExist:
        logger.warning(
            "rebuild_databus_relation: databus->[%s] DataIdConfig with data_id_name->[%s] not found, skip",
            databus_name,
            databus.data_id_name,
        )
        return None

    resolved_bk_data_id = data_id_config.bk_data_id
    if not resolved_bk_data_id:
        logger.warning(
            "rebuild_databus_relation: databus->[%s] DataIdConfig name->[%s] has empty bk_data_id->[%s], skip",
            databus_name,
            data_id_config.name,
            resolved_bk_data_id,
        )
        return None

    # 如果 databus.bk_data_id 不为 0 且不等于 resolved_bk_data_id，说明 databus 的 bk_data_id 已经存在，需要跳过
    if databus.bk_data_id != 0 and databus.bk_data_id != resolved_bk_data_id:
        logger.warning(
            "rebuild_databus_relation: databus->[%s] bk_data_id->[%s] is not equal to DataIdConfig bk_data_id->[%s], skip",
            databus_name,
            databus.bk_data_id,
            resolved_bk_data_id,
        )
        return None

    # 如果这个dataid在datasource中不存在，可能是bkdata额外申请的dataid，需要通过AccessVMRecord的bk_base_data_id查找对应的result_table_id进而找到真正的dataid
    data_source = DataSource.objects.filter(bk_data_id=resolved_bk_data_id).first()
    if not data_source:
        access_vm_record = AccessVMRecord.objects.filter(bk_base_data_id=resolved_bk_data_id).first()
        if not access_vm_record:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] AccessVMRecord with bk_base_data_id->[%s] not found, skip",
                databus_name,
                resolved_bk_data_id,
            )
            return None
        dsrt = DataSourceResultTable.objects.filter(table_id=access_vm_record.result_table_id).first()
        if not dsrt:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] DataSourceResultTable with table_id->[%s] not found, skip",
                databus_name,
                access_vm_record.result_table_id,
            )
            return None
        data_source = DataSource.objects.filter(bk_data_id=dsrt.bk_data_id).first()
        if not data_source:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] DataSource with bk_data_id->[%s] not found, skip",
                databus_name,
                dsrt.bk_data_id,
            )
            return None

    # Step 2: 解析 sink_names → {kind: [name, ...]}，格式为 "kind:name"
    sink_map = _parse_sink_names(databus.sink_names, databus_name)
    if sink_map is None:
        return None

    # Step 3: 查询各 sink 组件实例（批量查询，避免 N+1）
    sink_instances = _load_sink_instances(databus, sink_map)
    if sink_instances is None:
        return None
    databus_instances, sink_instances = _merge_graph_dual_write_sibling_databus(
        databus,
        sink_instances,
        resolved_bk_data_id=resolved_bk_data_id,
    )
    sink_map = {}
    for instance in sink_instances:
        sink_map.setdefault(instance.kind, []).append(instance.name)

    # BasereportSink 是二级路由组件，需要继续从已记录的 VMStorageBinding 名称展开下游绑定。
    basereport_sink_instances = [instance for instance in sink_instances if isinstance(instance, BasereportSinkConfig)]
    if basereport_sink_instances:
        vm_binding_names = []
        for basereport_sink in basereport_sink_instances:
            vm_binding_names.extend(basereport_sink.vm_storage_binding_names)
        vm_binding_names = list(dict.fromkeys(vm_binding_names))
        vm_bindings_by_name = {
            binding.name: binding
            for binding in VMStorageBindingConfig.objects.filter(
                bk_tenant_id=databus.bk_tenant_id,
                namespace=databus.namespace,
                name__in=vm_binding_names,
            )
        }
        missing_vm_bindings = [name for name in vm_binding_names if name not in vm_bindings_by_name]
        if missing_vm_bindings:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] BasereportSink referenced VmStorageBinding name->[%s] "
                "not found in DB, skip",
                databus_name,
                ", ".join(missing_vm_bindings),
            )
            return None
        sink_instances.extend(vm_bindings_by_name[name] for name in vm_binding_names)

    # Step 4: 冲突检测 —— 若任意 sink 组件已有 data_link_name，说明已属于其他链路，跳过
    for instance in sink_instances:
        if instance.data_link_name:
            logger.error(
                "rebuild_databus_relation: databus->[%s] sink component kind->[%s] name->[%s] "
                "already has data_link_name->[%s], conflict detected, skip",
                databus_name,
                instance.kind,
                instance.name,
                instance.data_link_name,
            )
            return None

    # Step 5: 对存储绑定类型，通过 bkbase_result_table_name 查找对应的 ResultTableConfig（批量查询，避免 N+1）
    rt_name_map: dict[str, DataLinkResourceConfigBase] = {}
    for instance in sink_instances:
        if not isinstance(instance, STORAGE_BINDING_MODELS):
            continue
        rt_name = instance.bkbase_result_table_name
        if not rt_name:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] binding kind->[%s] name->[%s] "
                "has empty bkbase_result_table_name, skip",
                databus_name,
                instance.kind,
                instance.name,
            )
            return None
        rt_name_map[rt_name] = instance

    rts_by_name = {
        rt.name: rt
        for rt in ResultTableConfig.objects.filter(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            name__in=list(rt_name_map),
        )
    }
    missing_rts = [name for name in rt_name_map if name not in rts_by_name]
    if missing_rts:
        logger.warning(
            "rebuild_databus_relation: databus->[%s] ResultTableConfig name->[%s] not found in DB, skip",
            databus_name,
            ", ".join(missing_rts),
        )
        return None
    rt_instances: list[ResultTableConfig] = [rts_by_name[name] for name in rt_name_map]
    vmrt_to_table_id = {
        record.vm_result_table_id: record.result_table_id
        for record in AccessVMRecord.objects.filter(vm_result_table_id__in=[rt.bkbase_table_id for rt in rt_instances])
    }
    result_table_name_to_table_id = {}
    for rt_instance in rt_instances:
        binding_instance = rt_name_map[rt_instance.name]
        rt_instance.table_id = _resolve_rebuild_result_table_id(
            binding_instance=binding_instance,
            rt_instance=rt_instance,
            vmrt_to_table_id=vmrt_to_table_id,
            databus=databus,
            data_source=data_source,
        )
        if not rt_instance.table_id:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] ResultTableConfig name->[%s] has empty table_id, skip",
                databus_name,
                rt_instance.name,
            )
            return None
        result_table_name_to_table_id[rt_instance.name] = rt_instance.table_id

    # 反补sink的table_id
    for sink_instance in sink_instances:
        if not isinstance(sink_instance, STORAGE_BINDING_MODELS):
            continue
        sink_instance.table_id = result_table_name_to_table_id[sink_instance.bkbase_result_table_name]
    for basereport_sink in basereport_sink_instances:
        basereport_sink.result_table_ids = [
            result_table_name_to_table_id[binding.bkbase_result_table_name]
            for binding in sink_instances
            if isinstance(binding, VMStorageBindingConfig)
            and binding.name in basereport_sink.vm_storage_binding_names
            and binding.bkbase_result_table_name in result_table_name_to_table_id
        ]

    # Step 6: 冲突检测 —— 若任意 ResultTableConfig 已有 data_link_name，跳过
    for rt in rt_instances:
        if rt.data_link_name:
            logger.error(
                "rebuild_databus_relation: databus->[%s] ResultTableConfig name->[%s] "
                "already has data_link_name->[%s], conflict detected, skip",
                databus_name,
                rt.name,
                rt.data_link_name,
            )
            return None

    # Step 7: 推断 data_link_strategy
    # 特殊规则：同时存在 ES 和 Doris 存储绑定 → BK_LOG（日志链路），优先于 etl_config 映射
    has_es = DataLinkKind.ESSTORAGEBINDING.value in sink_map
    has_doris = DataLinkKind.DORISBINDING.value in sink_map
    if has_es and has_doris:
        strategy = DataLink.BK_LOG
    elif _is_graph_relation_rebuild(databus, sink_map, rt_instances):
        strategy = DataLink.GRAPH_RELATION_TIME_SERIES
    else:
        strategy = ETL_CONFIG_TO_STRATEGY.get(data_source.etl_config)
        if strategy is None:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] etl_config->[%s] not in strategy map, skip",
                databus_name,
                data_source.etl_config,
            )
            return None

    # Step 8: graph rebuild 使用短 data_link_name，避免写入 64 字符的组件外键时超长。
    if strategy == DataLink.GRAPH_RELATION_TIME_SERIES:
        data_link_name = _compose_rebuilt_graph_data_link_name(databus)
    else:
        data_link_name = f"{REBUILT_DATA_LINK_NAME_PREFIX}{databus.bk_tenant_id}__{databus.namespace}__{databus_name}"

    # Step 9: 收集 table_ids（来自 ResultTableConfig.table_id，过滤空值）
    table_ids = [rt.table_id for rt in rt_instances if rt.table_id]

    # dry_run 模式：返回关联信息 dict，不写入数据库
    if dry_run:
        return {
            "data_link_name": data_link_name,
            "strategy": strategy,
            "bk_data_id": data_source.bk_data_id,
            "table_ids": table_ids,
            "sinks": [{"kind": i.kind, "name": i.name, "table_id": getattr(i, "table_id", "")} for i in sink_instances],
            "result_tables": [{"name": rt.name, "table_id": rt.table_id} for rt in rt_instances],
            "components": _serialize_datalink_components(
                [data_id_config, *rt_instances, *sink_instances, *databus_instances],
            ),
        }

    # Step 10-11: 在事务中批量更新组件 data_link_name 并创建/更新 DataLink 记录
    with transaction.atomic():
        # 先创建/更新 DataLink 记录，确保主记录存在后再关联组件
        data_link, created = DataLink.objects.update_or_create(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            data_link_name=data_link_name,
            defaults={
                # 这里需要关联监控平台真正的dataid，而不是bkdata的dataid
                "bk_data_id": data_source.bk_data_id,
                "table_ids": table_ids,
                "data_link_strategy": strategy,
            },
        )

        # 更新 DataBusConfig 自身；graph dual-write rebuild 会同时认领 VM/SurrealDB 两条 sibling Databus。
        for databus_instance in databus_instances:
            databus_instance.data_link_name = data_link_name
            databus_instance.bk_data_id = resolved_bk_data_id
            databus_instance.save(update_fields=["data_link_name", "bk_data_id"])

        # 批量更新 sink 组件（按 model 类型分组，减少 DB 操作次数）
        for instance in sink_instances:
            instance.data_link_name = data_link_name
        _bulk_update_data_link_name(sink_instances)

        # 批量更新 ResultTableConfig
        for rt in rt_instances:
            rt.data_link_name = data_link_name
        ResultTableConfig.objects.bulk_update(rt_instances, ["data_link_name", "table_id"])

        if strategy == DataLink.GRAPH_RELATION_TIME_SERIES:
            vm_binding = next((i for i in sink_instances if isinstance(i, VMStorageBindingConfig)), None)
            surrealdb_binding = next((i for i in sink_instances if isinstance(i, SurrealDBBindingConfig)), None)
            graph_binding_name = _compose_rebuilt_graph_binding_name(data_link_name)
            write_mode = GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
            if vm_binding and not surrealdb_binding:
                write_mode = GraphRelationBindingConfig.WRITE_MODE_VM
            elif surrealdb_binding and not vm_binding:
                write_mode = GraphRelationBindingConfig.WRITE_MODE_SURREALDB

            _restore_rebuilt_surrealdb_storage(surrealdb_binding)
            GraphRelationBindingConfig.objects.update_or_create(
                bk_tenant_id=databus.bk_tenant_id,
                namespace=databus.namespace,
                name=graph_binding_name,
                defaults={
                    "data_link_name": data_link_name,
                    "bk_biz_id": databus.bk_biz_id,
                    "status": databus.status,
                    "write_mode": write_mode,
                    "vm_cluster_name": getattr(vm_binding, "vm_cluster_name", ""),
                    "surrealdb_cluster_name": getattr(surrealdb_binding, "surrealdb_cluster_name", ""),
                    "table_id": table_ids[0] if table_ids else "",
                    "bkbase_result_table_name": getattr(vm_binding, "bkbase_result_table_name", ""),
                    "graph_result_table_name": getattr(surrealdb_binding, "bkbase_result_table_name", ""),
                    "vm_storage_binding_name": getattr(vm_binding, "name", ""),
                    "vm_databus_name": _find_databus_name_for_sink(
                        databus_instances,
                        DataLinkKind.VMSTORAGEBINDING.value,
                        getattr(vm_binding, "name", ""),
                    ),
                    "surrealdb_binding_name": getattr(surrealdb_binding, "name", ""),
                    "graph_databus_name": _find_databus_name_for_sink(
                        databus_instances,
                        DataLinkKind.SURREALDBBINDING.value,
                        getattr(surrealdb_binding, "name", ""),
                    ),
                    "table_type": getattr(surrealdb_binding, "table_type", "temporary"),
                    "vertices": getattr(surrealdb_binding, "vertices", []),
                    "relations": getattr(surrealdb_binding, "relations", []),
                },
            )

    logger.info(
        "rebuild_databus_relation: databus->[%s] relation rebuilt successfully, "
        "strategy->[%s], table_ids->[%s], created->[%s]",
        databus_name,
        strategy,
        table_ids,
        created,
    )
    return data_link


def _serialize_datalink_components(instances: Sequence[DataLinkResourceConfigBase]) -> list[dict[str, object]]:
    """序列化 dry_run 匹配到的 DataLink 组件，便于人工 review 重建范围。"""
    components = []
    for instance in instances:
        component = {
            "kind": instance.kind,
            "name": instance.name,
            "namespace": instance.namespace,
            "bk_tenant_id": instance.bk_tenant_id,
            "data_link_name": instance.data_link_name,
            "bk_biz_id": instance.bk_biz_id,
        }
        for field in ("table_id", "bk_data_id", "data_id_name", "sink_names", "result_table_ids"):
            value = getattr(instance, field, None)
            if value not in (None, "", []):
                component[field] = value
        components.append(component)
    return components


def _bulk_update_data_link_name(instances: Sequence[DataLinkResourceConfigBase]) -> None:
    """按 model 类型分组，批量更新 data_link_name 和 table_id 字段，减少 DB 操作次数。"""
    if not instances:
        return
    model_groups: dict[type[DataLinkResourceConfigBase], list[DataLinkResourceConfigBase]] = {}
    for instance in instances:
        model_cls = type(instance)
        model_groups.setdefault(model_cls, []).append(instance)
    for model_cls, group in model_groups.items():
        if model_cls is VMStorageBindingConfig:
            VMStorageBindingConfig.objects.bulk_update(
                cast(list[VMStorageBindingConfig], group),
                ["data_link_name", "table_id", "bk_biz_id"],
            )
        elif model_cls is ESStorageBindingConfig:
            ESStorageBindingConfig.objects.bulk_update(
                cast(list[ESStorageBindingConfig], group),
                ["data_link_name", "table_id", "bk_biz_id"],
            )
        elif model_cls is DorisStorageBindingConfig:
            DorisStorageBindingConfig.objects.bulk_update(
                cast(list[DorisStorageBindingConfig], group),
                ["data_link_name", "table_id", "bk_biz_id"],
            )
        elif model_cls is SurrealDBBindingConfig:
            SurrealDBBindingConfig.objects.bulk_update(
                cast(list[SurrealDBBindingConfig], group),
                ["data_link_name", "table_id"],
            )
        elif model_cls is BasereportSinkConfig:
            BasereportSinkConfig.objects.bulk_update(
                cast(list[BasereportSinkConfig], group),
                ["data_link_name", "result_table_ids", "bk_biz_id"],
            )
        else:
            ConditionalSinkConfig.objects.bulk_update(
                cast(list[ConditionalSinkConfig], group),
                ["data_link_name", "bk_biz_id"],
            )


def rebuild_bkbase_v4_datalink_relation(bk_tenant_id: str, namespace: str, dry_run: bool = True) -> list[dict] | None:
    """批量重建指定租户和命名空间下所有 data_link_name 为空的 DataBus 的关联关系。

    以 DataBus 为原子单元，逐一调用 rebuild_databus_relation 进行重建。
    单个 DataBus 失败不影响其他 DataBus 的处理。

    适用场景：
        sync_bkbase_v4_datalink_components 同步完成后，组件 data_link_name 均为空，
        需要调用本函数补全 data_link_name 并创建 DataLink 记录。

    Args:
        bk_tenant_id: 租户 ID，例如 "system"。
        namespace: 命名空间，例如 "bkmonitor"。
        dry_run: 若为 True，仅解析关联信息并返回 list[dict]，不写入数据库。

    Returns:
        dry_run=False 时返回 None；dry_run=True 时返回所有可成功重建的 DataBus 信息列表。
    """
    databuses = DataBusConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        namespace=namespace,
        data_link_name="",
    )
    total = databuses.count()
    logger.info(
        "rebuild_bkbase_v4_datalink_relation: found %d DataBus(es) with empty data_link_name "
        "for bk_tenant_id->[%s] namespace->[%s] dry_run->[%s]",
        total,
        bk_tenant_id,
        namespace,
        dry_run,
    )

    success, skipped = 0, 0
    dry_run_results: list[dict] = []
    seen_databuses: set[tuple[str, str, str]] = set()
    for databus in databuses:
        databus_key = (databus.bk_tenant_id, databus.namespace, databus.name)
        if databus_key in seen_databuses:
            skipped += 1
            continue
        if not dry_run and DataBusConfig.objects.filter(pk=databus.pk).exclude(data_link_name="").exists():
            skipped += 1
            continue
        result = rebuild_databus_relation(databus, dry_run=dry_run)
        if result is not None:
            success += 1
            if dry_run and isinstance(result, dict):
                dry_run_results.append(result)
                for component in result.get("components", []):
                    if component.get("kind") == DataLinkKind.DATABUS.value:
                        seen_databuses.add(
                            (
                                component.get("bk_tenant_id", ""),
                                component.get("namespace", ""),
                                component.get("name", ""),
                            )
                        )
            elif isinstance(result, DataLink):
                seen_databuses.update(
                    DataBusConfig.objects.filter(
                        bk_tenant_id=bk_tenant_id,
                        namespace=namespace,
                        data_link_name=result.data_link_name,
                    ).values_list("bk_tenant_id", "namespace", "name")
                )
        else:
            skipped += 1

    logger.info(
        "rebuild_bkbase_v4_datalink_relation: finished. total->[%d], success->[%d], skipped->[%d] dry_run->[%s]",
        total,
        success,
        skipped,
        dry_run,
    )

    if dry_run:
        return dry_run_results
    return None


# simple rebuild 会回填业务 ID 的组件模型；DataIdConfig 不在 simple rebuild 的归属处理范围内，故此处不修复。
SIMPLE_REBUILD_BK_BIZ_ID_MODELS: tuple[type[DataLinkResourceConfigBase], ...] = (
    DataBusConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
)


def _resolve_simple_rebuild_target_bk_biz_id(bk_tenant_id: str, table_id: str) -> int | None:
    """解析 simple rebuild 链路组件应归属的目标业务 ID。

    分两类存储场景处理：
        - VM / InfluxDB 指标链路：沿用 get_target_bk_biz_id，必要时从自定义时序/事件 group 反查业务字段。
        - log / event 等其余链路：直接复用结果表自身的 bk_biz_id。

    Args:
        bk_tenant_id: 租户 ID。
        table_id: 链路关联的监控结果表 ID。

    Returns:
        解析到的目标业务 ID；当结果表不存在时返回 None，由调用方据此跳过。
    """
    try:
        result_table = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except ResultTable.DoesNotExist:
        return None

    if result_table.default_storage in [ClusterInfo.TYPE_VM, ClusterInfo.TYPE_INFLUXDB]:
        target_bk_biz_id = result_table.get_target_bk_biz_id()
        if target_bk_biz_id == 0:
            target_bk_biz_id = get_tenant_default_biz_id(bk_tenant_id=result_table.bk_tenant_id)
        return target_bk_biz_id

    # log / event 等非指标链路直接使用结果表自身的业务 ID
    return result_table.bk_biz_id


def backfill_simple_rebuild_relation_bk_biz_id(
    bk_tenant_id: str, namespace: str, dry_run: bool = True
) -> list[dict[str, object]]:
    """检查并补全 rebuild_simple_databus_relation 历史重建链路下组件的业务 ID。

    背景：
        早期 rebuild_simple_databus_relation 未处理 bk_biz_id，导致以 "rebuilt__" 前缀重建的链路下，
        DataBus / StorageBinding / ResultTable 组件的 bk_biz_id 残留为 0。本脚本用于离线巡检并修复。

    处理逻辑：
        以 "rebuilt__" 前缀的 DataLink 为单位，按链路关联的唯一 table_id 重新解析目标业务 ID
        （口径与 rebuild_simple_databus_relation 完全一致），并回填到 bk_biz_id 不一致的组件。
        多结果表 / 无结果表的 DataLink 不属于 simple rebuild 场景，直接跳过避免误改。

    调用方式：
        from metadata.models.data_link.relation import backfill_simple_rebuild_relation_bk_biz_id
        # 先 dry_run 巡检
        backfill_simple_rebuild_relation_bk_biz_id(bk_tenant_id="system", namespace="bkmonitor", dry_run=True)
        # 确认无误后执行写库
        backfill_simple_rebuild_relation_bk_biz_id(bk_tenant_id="system", namespace="bkmonitor", dry_run=False)

    Args:
        bk_tenant_id: 租户 ID，例如 "system"。
        namespace: 命名空间，例如 "bkmonitor"。
        dry_run: 若为 True，仅统计并返回待更新组件信息，不写入数据库。

    Returns:
        待更新（dry_run=True）或已更新（dry_run=False）的链路组件信息列表，
        每个元素描述一条 DataLink 及其下需要修正 bk_biz_id 的组件。
    """
    data_links = DataLink.objects.filter(
        bk_tenant_id=bk_tenant_id,
        namespace=namespace,
        data_link_name__startswith=REBUILT_DATA_LINK_NAME_PREFIX,
    )
    total = data_links.count()
    logger.info(
        "backfill_simple_rebuild_relation_bk_biz_id: found %d rebuilt DataLink(s) for "
        "bk_tenant_id->[%s] namespace->[%s] dry_run->[%s]",
        total,
        bk_tenant_id,
        namespace,
        dry_run,
    )

    results: list[dict[str, object]] = []
    updated_link_count, skipped_link_count, updated_component_count = 0, 0, 0
    for data_link in data_links:
        # 简单链路只关联一张结果表；多表或无表说明不是 simple rebuild 场景，跳过避免误判。
        if len(data_link.table_ids) != 1:
            logger.info(
                "backfill_simple_rebuild_relation_bk_biz_id: data_link->[%s] table_ids->[%s] is not single-table, skip",
                data_link.data_link_name,
                data_link.table_ids,
            )
            skipped_link_count += 1
            continue

        table_id = data_link.table_ids[0]
        target_bk_biz_id = _resolve_simple_rebuild_target_bk_biz_id(bk_tenant_id, table_id)
        if target_bk_biz_id is None:
            logger.warning(
                "backfill_simple_rebuild_relation_bk_biz_id: data_link->[%s] ResultTable with table_id->[%s] "
                "not found, skip",
                data_link.data_link_name,
                table_id,
            )
            skipped_link_count += 1
            continue

        # 防御：解析出的目标业务 ID 仍为 0 时无法修复（0->0 无意义），跳过避免误判与无效写入。
        if not target_bk_biz_id:
            logger.info(
                "backfill_simple_rebuild_relation_bk_biz_id: data_link->[%s] table_id->[%s] resolved "
                "target_bk_biz_id is 0, skip",
                data_link.data_link_name,
                table_id,
            )
            skipped_link_count += 1
            continue

        # 防御：只修复历史残留为 0 的组件配置，已有非 0 业务 ID 的组件保持原值不动。
        # 先固化明细便于 dry_run review 与执行后审计。
        link_components: list[dict[str, object]] = []
        mismatched_by_model: list[tuple[type[DataLinkResourceConfigBase], list[int]]] = []
        for model in SIMPLE_REBUILD_BK_BIZ_ID_MODELS:
            zero_biz_components = list(
                model.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    data_link_name=data_link.data_link_name,
                    bk_biz_id=0,
                )
            )
            if not zero_biz_components:
                continue
            mismatched_by_model.append((model, [component.id for component in zero_biz_components]))
            link_components.extend(
                {
                    "kind": component.kind,
                    "name": component.name,
                    "old_bk_biz_id": component.bk_biz_id,
                }
                for component in zero_biz_components
            )

        if not link_components:
            continue

        if dry_run:
            # dry_run 仅巡检，逐条打印将被更新的链路与组件，便于人工确认影响范围。
            for component in link_components:
                logger.info(
                    "backfill_simple_rebuild_relation_bk_biz_id[dry_run]: data_link->[%s] component kind->[%s] "
                    "name->[%s] bk_biz_id will be updated [%s]->[%s]",
                    data_link.data_link_name,
                    component["kind"],
                    component["name"],
                    component["old_bk_biz_id"],
                    target_bk_biz_id,
                )
        else:
            with transaction.atomic():
                for model, component_ids in mismatched_by_model:
                    model.objects.filter(id__in=component_ids).update(bk_biz_id=target_bk_biz_id)

        updated_link_count += 1
        updated_component_count += len(link_components)
        results.append(
            {
                "data_link_name": data_link.data_link_name,
                "table_id": table_id,
                "target_bk_biz_id": target_bk_biz_id,
                "components": link_components,
            }
        )

    logger.info(
        "backfill_simple_rebuild_relation_bk_biz_id: finished. total->[%d], updated_link->[%d], "
        "skipped_link->[%d], updated_component->[%d], dry_run->[%s]",
        total,
        updated_link_count,
        skipped_link_count,
        updated_component_count,
        dry_run,
    )
    return results
