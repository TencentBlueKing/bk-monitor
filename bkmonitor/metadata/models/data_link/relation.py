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

from metadata.models import (
    AccessVMRecord,
    BkBaseResultTable,
    ClusterInfo,
    DataSourceResultTable,
    DorisStorage,
    ESStorage,
)
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import (
    BasereportSinkConfig,
    ConditionalSinkConfig,
    DataBusConfig,
    DataIdConfig,
    DataLinkResourceConfigBase,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
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
    DataLinkKind.CONDITIONALSINK.value: ConditionalSinkConfig,
    DataLinkKind.BASEREPORTSINK.value: BasereportSinkConfig,
}

# 存储绑定类型（需要关联 ResultTableConfig，ConditionalSink 不需要）
STORAGE_BINDING_MODELS = (
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
)

SIMPLE_STORAGE_BINDING_MODELS: dict[str, type[SimpleStorageBindingConfig]] = {
    DataLinkKind.VMSTORAGEBINDING.value: VMStorageBindingConfig,
    DataLinkKind.ESSTORAGEBINDING.value: ESStorageBindingConfig,
    DataLinkKind.DORISBINDING.value: DorisStorageBindingConfig,
}

# 重建链路名称前缀，便于与正常创建的链路区分，支持回溯和回滚
REBUILT_DATA_LINK_NAME_PREFIX = "rebuilt__"

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

    # Step 1: 简单链路只处理尚未归属 DataLink 的 DataBus，已有归属直接跳过避免覆盖关系。
    if databus.data_link_name:
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
    if databus.bk_data_id != 0 and databus.bk_data_id != resolved_bk_data_id:
        logger.warning(
            "rebuild_simple_databus_relation: databus->[%s] bk_data_id->[%s] "
            "is not equal to DataIdConfig bk_data_id->[%s], skip",
            databus_name,
            databus.bk_data_id,
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
        if instance.data_link_name:
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
        if rt.data_link_name:
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

    data_link_name = f"{REBUILT_DATA_LINK_NAME_PREFIX}_{databus_name}"
    table_ids = [table_id]
    bkbase_result_table = _build_simple_bkbase_result_table(
        data_link_name=data_link_name,
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
            "data_link_name": data_link_name,
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
            data_link_name=data_link_name,
            defaults={
                "bk_data_id": data_source.bk_data_id,
                "table_ids": table_ids,
                "data_link_strategy": strategy,
            },
        )

        databus.data_link_name = data_link_name
        databus.bk_data_id = resolved_bk_data_id
        databus.save(update_fields=["data_link_name", "bk_data_id"])

        for instance in sink_instances:
            instance.data_link_name = data_link_name
        _bulk_update_data_link_name(sink_instances)

        for rt in rt_instances:
            rt.data_link_name = data_link_name
        ResultTableConfig.objects.bulk_update(rt_instances, ["data_link_name", "table_id"])

        BkBaseResultTable.objects.update_or_create(
            bk_tenant_id=databus.bk_tenant_id,
            data_link_name=data_link_name,
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
    sink_map: dict[str, list[str]] = {}
    for entry in databus.sink_names:
        if ":" not in entry:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] has invalid sink_names entry->[%s], skip",
                databus_name,
                entry,
            )
            return None
        kind, name = entry.split(":", 1)
        sink_map.setdefault(kind, []).append(name)

    # Step 3: 查询各 sink 组件实例（批量查询，避免 N+1）
    sink_instances: list[DataLinkResourceConfigBase] = []
    for kind, names in sink_map.items():
        model = SINK_KIND_TO_MODEL.get(kind)
        if model is None:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] has unknown sink kind->[%s], skip",
                databus_name,
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
                databus_name,
                kind,
                ", ".join(missing),
            )
            return None
        sink_instances.extend(instances_by_name[name] for name in names)

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
        rt_instance.table_id = vmrt_to_table_id.get(rt_instance.bkbase_table_id, "")
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
    else:
        strategy = ETL_CONFIG_TO_STRATEGY.get(data_source.etl_config)
        if strategy is None:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] etl_config->[%s] not in strategy map, skip",
                databus_name,
                data_source.etl_config,
            )
            return None

    # Step 8: data_link_name 使用 "rebuilt__" 前缀 + 租户/命名空间/DataBus name，确保跨租户唯一
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
                [data_id_config, *rt_instances, *sink_instances, databus],
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

        # 更新 DataBusConfig 自身
        databus.data_link_name = data_link_name
        databus.bk_data_id = resolved_bk_data_id
        databus.save(update_fields=["data_link_name", "bk_data_id"])

        # 批量更新 sink 组件（按 model 类型分组，减少 DB 操作次数）
        for instance in sink_instances:
            instance.data_link_name = data_link_name
        _bulk_update_data_link_name(sink_instances)

        # 批量更新 ResultTableConfig
        for rt in rt_instances:
            rt.data_link_name = data_link_name
        ResultTableConfig.objects.bulk_update(rt_instances, ["data_link_name", "table_id"])

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
                ["data_link_name", "table_id"],
            )
        elif model_cls is ESStorageBindingConfig:
            ESStorageBindingConfig.objects.bulk_update(
                cast(list[ESStorageBindingConfig], group),
                ["data_link_name", "table_id"],
            )
        elif model_cls is DorisStorageBindingConfig:
            DorisStorageBindingConfig.objects.bulk_update(
                cast(list[DorisStorageBindingConfig], group),
                ["data_link_name", "table_id"],
            )
        elif model_cls is BasereportSinkConfig:
            BasereportSinkConfig.objects.bulk_update(
                cast(list[BasereportSinkConfig], group),
                ["data_link_name", "result_table_ids"],
            )
        else:
            ConditionalSinkConfig.objects.bulk_update(
                cast(list[ConditionalSinkConfig], group),
                ["data_link_name"],
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
    for databus in databuses:
        result = rebuild_databus_relation(databus, dry_run=dry_run)
        if result is not None:
            success += 1
            if dry_run and isinstance(result, dict):
                dry_run_results.append(result)
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
