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

from django.db import transaction
from django.db.models import Model

from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    DataLinkResourceConfigBase,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)

logger = logging.getLogger("metadata")

# sink kind → 对应的 Model 类映射
SINK_KIND_TO_MODEL: dict[str, type[DataLinkResourceConfigBase]] = {
    DataLinkKind.VMSTORAGEBINDING.value: VMStorageBindingConfig,
    DataLinkKind.ESSTORAGEBINDING.value: ESStorageBindingConfig,
    DataLinkKind.DORISBINDING.value: DorisStorageBindingConfig,
    DataLinkKind.CONDITIONALSINK.value: ConditionalSinkConfig,
}

# 存储绑定类型（需要关联 ResultTableConfig，ConditionalSink 不需要）
STORAGE_BINDING_MODELS = (
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
)

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
}


def rebuild_databus_relation(databus: DataBusConfig, dry_run: bool = False) -> DataLink | dict[str, object] | None:
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
        - DataSource 不存在（bk_data_id 无对应记录）
        - etl_config 不在映射表中且不满足特殊规则

    冲突处理：
        若任意关联组件已有 data_link_name，说明该组件已属于另一条链路，
        本次重建可能造成数据错乱，因此跳过整个 DataBus。
    """
    from metadata.models.data_source import DataSource

    databus_name = databus.name

    # Step 1: 解析 sink_names → {kind: [name, ...]}，格式为 "kind:name"
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

    # Step 2: 查询各 sink 组件实例（批量查询，避免 N+1）
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

    # Step 3: 冲突检测 —— 若任意 sink 组件已有 data_link_name，说明已属于其他链路，跳过
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

    # Step 4: 对存储绑定类型，通过 bkbase_result_table_name 查找对应的 ResultTableConfig（批量查询，避免 N+1）
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

    # Step 5: 冲突检测 —— 若任意 ResultTableConfig 已有 data_link_name，跳过
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

    # Step 6: 推断 data_link_strategy
    # 特殊规则：同时存在 ES 和 Doris 存储绑定 → BK_LOG（日志链路），优先于 etl_config 映射
    has_es = DataLinkKind.ESSTORAGEBINDING.value in sink_map
    has_doris = DataLinkKind.DORISBINDING.value in sink_map
    if has_es and has_doris:
        strategy = DataLink.BK_LOG
    else:
        # 通过 bk_data_id 查找 DataSource，获取 etl_config 后映射到 strategy
        try:
            data_source = DataSource.objects.get(bk_data_id=databus.bk_data_id)
        except DataSource.DoesNotExist:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] DataSource with bk_data_id->[%s] not found, skip",
                databus_name,
                databus.bk_data_id,
            )
            return None

        strategy = ETL_CONFIG_TO_STRATEGY.get(data_source.etl_config)
        if strategy is None:
            logger.warning(
                "rebuild_databus_relation: databus->[%s] etl_config->[%s] not in strategy map, skip",
                databus_name,
                data_source.etl_config,
            )
            return None

    # Step 7: data_link_name 使用 "rebuilt__" 前缀 + 租户/命名空间/DataBus name，确保跨租户唯一
    data_link_name = f"{REBUILT_DATA_LINK_NAME_PREFIX}{databus.bk_tenant_id}__{databus.namespace}__{databus_name}"

    # Step 8: 收集 table_ids（来自 ResultTableConfig.table_id，过滤空值）
    table_ids = [rt.table_id for rt in rt_instances if rt.table_id]

    # dry_run 模式：返回关联信息 dict，不写入数据库
    if dry_run:
        return {
            "data_link_name": data_link_name,
            "strategy": strategy,
            "bk_data_id": databus.bk_data_id,
            "table_ids": table_ids,
            "sinks": [{"kind": i.kind, "name": i.name} for i in sink_instances],
            "result_tables": [{"name": rt.name, "table_id": rt.table_id} for rt in rt_instances],
        }

    # Step 9-10: 在事务中批量更新组件 data_link_name 并创建/更新 DataLink 记录
    with transaction.atomic():
        # 先创建/更新 DataLink 记录，确保主记录存在后再关联组件
        data_link, created = DataLink.objects.update_or_create(
            bk_tenant_id=databus.bk_tenant_id,
            namespace=databus.namespace,
            data_link_name=data_link_name,
            defaults={
                "bk_data_id": databus.bk_data_id,
                "table_ids": table_ids,
                "data_link_strategy": strategy,
            },
        )

        # 批量更新 DataBus 自身
        databus.data_link_name = data_link_name
        databus.save(update_fields=["data_link_name"])

        # 批量更新 sink 组件（按 model 类型分组，减少 DB 操作次数）
        for instance in sink_instances:
            instance.data_link_name = data_link_name
        _bulk_update_data_link_name(sink_instances)

        # 批量更新 ResultTableConfig
        for rt in rt_instances:
            rt.data_link_name = data_link_name
        _bulk_update_data_link_name(rt_instances)

    logger.info(
        "rebuild_databus_relation: databus->[%s] relation rebuilt successfully, "
        "strategy->[%s], table_ids->[%s], created->[%s]",
        databus_name,
        strategy,
        table_ids,
        created,
    )
    return data_link


def _bulk_update_data_link_name(instances: Sequence[DataLinkResourceConfigBase]) -> None:
    """按 model 类型分组，批量更新 data_link_name 字段，减少 DB 操作次数。"""
    if not instances:
        return
    model_groups: dict[type[Model], list[Model]] = {}
    for instance in instances:
        model_cls = type(instance)
        model_groups.setdefault(model_cls, []).append(instance)
    for model_cls, group in model_groups.items():
        model_cls.objects.bulk_update(group, ["data_link_name"])


def rebuild_bkbase_v4_datalink_relation(bk_tenant_id: str, namespace: str, dry_run: bool = False) -> list[dict] | None:
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
