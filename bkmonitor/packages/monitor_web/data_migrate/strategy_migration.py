"""内置告警策略迁移通用处理模块。

汇总各类内置告警策略在多租户改造下的存量迁移逻辑，目前包含：

- ``migrate_system_event_strategy_config``：GSE 系统事件策略迁移到多租户内置 custom event 链路。
- ``migrate_gather_up_strategy_config``：gather_up 采集任务状态策略从全局结果表改为分业务自定义时序引用。

各迁移函数彼此独立、可单独调用；``migrate_builtin_strategy_config`` 为统一入口，按业务依次执行全部
内置策略迁移并返回聚合结果。所有迁移仅在多租户模式（``ENABLE_MULTI_TENANT_MODE``）下生效。
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from bk_monitor_base.strategy import get_metric_id
from django.conf import settings
from django.db import transaction

from bkmonitor.models import AlgorithmModel, DetectModel, ItemModel, QueryConfigModel, StrategyModel
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.strategies.default_settings.datalink.v1 import (
    DEFAULT_DATALINK_COLLECTING_FLAG,
    GATHER_UP_DATA_LABEL,
    GATHER_UP_METRIC_FIELD,
    get_gather_up_result_table_id,
)

# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------


def _normalize_ids(ids: int | str | Iterable[int] | None) -> list[int] | None:
    """将业务 ID 入参规整为去重有序列表；``None``/空串表示不限定业务。"""
    if ids is None:
        return None
    if isinstance(ids, int):
        return [ids]
    if isinstance(ids, str):
        ids = ids.strip()
        if not ids:
            return None
        return [int(ids)]
    return sorted({int(value) for value in ids})


def _build_empty_report(
    *,
    dry_run: bool,
    bk_biz_ids: list[int] | None,
    message: str,
    include_skipped: bool = False,
) -> dict[str, Any]:
    """构造空迁移报告（如未开启多租户时直接跳过的场景）。"""
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "changed_count": 0,
        "applied_count": 0,
        "stale_count": 0,
        "changes": [],
        "message": message,
    }
    if include_skipped:
        report["skipped_count"] = 0
        report["skipped"] = []
    return report


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


def migrate_builtin_strategy_config(
    bk_biz_id: int | Iterable[int] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    内置策略迁移统一入口：按业务依次执行全部内置策略迁移并返回聚合结果。

    当前覆盖 GSE 系统事件策略与 gather_up 采集状态策略；``results`` 中保留各迁移的完整明细，
    顶层字段汇总各迁移的变更/落库/失效计数，便于统一巡检与观测。

    Args:
        bk_biz_id: 可选业务 ID 或业务 ID 列表；不传时各迁移扫描全量策略。
        dry_run: 为 ``True`` 时仅返回计划变更，不落库。
    """
    results = {
        "system_event": migrate_system_event_strategy_config(bk_biz_id=bk_biz_id, dry_run=dry_run),
        "gather_up": migrate_gather_up_strategy_config(bk_biz_id=bk_biz_id, dry_run=dry_run),
    }
    return {
        "dry_run": dry_run,
        "bk_biz_ids": _normalize_ids(bk_biz_id),
        "changed_count": sum(result["changed_count"] for result in results.values()),
        "applied_count": sum(result["applied_count"] for result in results.values()),
        "stale_count": sum(result["stale_count"] for result in results.values()),
        "results": results,
    }


# ---------------------------------------------------------------------------
# 系统事件策略迁移
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemEventTargetConfig:
    old_metric_id: str
    old_event_name: str
    custom_event_name: str
    agg_dimension: list[str]
    trigger_config: dict[str, int]
    recovery_config: dict[str, Any]


@dataclass(frozen=True)
class SystemEventMetric:
    bk_biz_id: int
    custom_event_name: str
    result_table_id: str
    agg_interval: int
    data_label: str


# 多租户内置系统事件（custom 源）采集周期固定为 1 分钟，与 os_loader 用 collect_interval(=1)*60
# 推出的聚合周期保持一致；这里直接按固定值推导 agg_interval，避免再回查 MetricListCache。
SYSTEM_EVENT_AGG_INTERVAL = 60


SYSTEM_EVENT_TARGET_CONFIGS: dict[str, SystemEventTargetConfig] = {
    "bk_monitor.agent-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.agent-gse",
        old_event_name="agent-gse",
        custom_event_name="AgentLost",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "bk_agent_id"],
        trigger_config={"count": 1 if "GSE_VERSION_1" in os.environ else 3, "check_window": 10},
        recovery_config={"check_window": 10, "status_setter": "close"},
    ),
    "bk_monitor.disk-readonly-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.disk-readonly-gse",
        old_event_name="disk-readonly-gse",
        custom_event_name="DiskReadonly",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "position", "type", "fs"],
        trigger_config={"count": 1, "check_window": 20},
        recovery_config={"check_window": 20, "status_setter": "close"},
    ),
    "bk_monitor.disk-full-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.disk-full-gse",
        old_event_name="disk-full-gse",
        custom_event_name="DiskFull",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "disk", "fstype", "file_system"],
        trigger_config={"count": 1, "check_window": 20},
        recovery_config={"check_window": 20, "status_setter": "close"},
    ),
    "bk_monitor.corefile-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.corefile-gse",
        old_event_name="corefile-gse",
        custom_event_name="CoreFile",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "executable_path", "executable", "signal"],
        trigger_config={"count": 1, "check_window": 5},
        recovery_config={"check_window": 5, "status_setter": "close"},
    ),
    "bk_monitor.oom-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.oom-gse",
        old_event_name="oom-gse",
        custom_event_name="OOM",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "process", "constraint"],
        trigger_config={"count": 1, "check_window": 5},
        recovery_config={"check_window": 5, "status_setter": "close"},
    ),
}

TARGET_ALGORITHM_CONFIG = [[{"threshold": 1, "method": "gte"}]]


def migrate_system_event_strategy_config(
    bk_biz_id: int | Iterable[int] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    将存量 GSE 系统事件策略迁移到多租户内置自定义事件链路。

    多租户下 GSE 系统事件不再走 ``bk_monitor`` 的 ``system.event`` / Kafka 告警链路，
    而是由业务内置 custom event 表承载。该函数只调整系统事件链路相关字段：
    查询配置、监控项类型、检测算法和恢复语义；策略启停、通知组、目标范围等存量配置保持不变。

    目标结果表按业务与租户直接推导（``base_{bk_tenant_id}_{bk_biz_id}_event``），不再回查
    MetricListCache；负数/零业务没有内置分业务 custom event 表，直接跳过。

    Args:
        bk_biz_id: 可选业务 ID 或业务 ID 列表；不传时扫描全量策略。
        dry_run: 为 ``True`` 时仅返回计划变更，不落库。
    """
    bk_biz_ids = _normalize_ids(bk_biz_id)
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return _build_empty_report(
            dry_run=dry_run,
            bk_biz_ids=bk_biz_ids,
            message="ENABLE_MULTI_TENANT_MODE is disabled, system event strategy migration skipped",
            include_skipped=True,
        )

    change_records, skipped_records = _system_event_collect_change_records(bk_biz_ids=bk_biz_ids)
    if not dry_run:
        _system_event_apply_change_records(change_records)

    return {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "changed_count": len(change_records),
        "applied_count": len([record for record in change_records if record.get("applied")]),
        "stale_count": len([record for record in change_records if record.get("stale")]),
        "skipped_count": len(skipped_records),
        "changes": deepcopy(change_records),
        "skipped": deepcopy(skipped_records),
    }


def _system_event_collect_change_records(
    bk_biz_ids: list[int] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strategy_queryset = StrategyModel.objects.all()
    if bk_biz_ids is not None:
        strategy_queryset = strategy_queryset.filter(bk_biz_id__in=bk_biz_ids)

    query_configs = list(
        QueryConfigModel.objects.filter(
            strategy_id__in=strategy_queryset.values("id"),
            metric_id__in=SYSTEM_EVENT_TARGET_CONFIGS.keys(),
        )
        .only(
            "id",
            "strategy_id",
            "item_id",
            "alias",
            "metric_id",
            "data_source_label",
            "data_type_label",
            "config",
        )
        .order_by("strategy_id", "id")
    )
    if not query_configs:
        return [], []

    strategies = _system_event_get_strategy_map({query_config.strategy_id for query_config in query_configs})
    # 仅 cmdb 业务（bk_biz_id > 0）才有内置的分业务 custom event 结果表，负数/零业务直接跳过。
    tenant_map = _system_event_get_bk_tenant_map(
        {strategy.bk_biz_id for strategy in strategies.values() if strategy.bk_biz_id > 0}
    )

    change_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    for query_config in query_configs:
        target_config = SYSTEM_EVENT_TARGET_CONFIGS[query_config.metric_id]
        strategy = strategies.get(query_config.strategy_id)
        if strategy is None:
            skipped_records.append(
                _system_event_build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    reason="strategy not found",
                )
            )
            continue
        if strategy.bk_biz_id <= 0:
            skipped_records.append(
                _system_event_build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    strategy=strategy,
                    reason="non-positive bk_biz_id has no built-in custom event table",
                )
            )
            continue

        bk_tenant_id = tenant_map.get(strategy.bk_biz_id)
        if not bk_tenant_id:
            skipped_records.append(
                _system_event_build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    strategy=strategy,
                    reason="resolve bk_tenant_id from bk_biz_id failed",
                )
            )
            continue

        target_metric = _system_event_build_metric(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=strategy.bk_biz_id,
            custom_event_name=target_config.custom_event_name,
        )
        change_records.append(
            _system_event_build_change_record(
                query_config=query_config,
                strategy=strategy,
                target_config=target_config,
                target_metric=target_metric,
            )
        )

    _system_event_fill_item_info(change_records)
    _system_event_fill_algorithm_info(change_records)
    _system_event_fill_detect_info(change_records)
    return change_records, skipped_records


def _system_event_get_strategy_map(strategy_ids: set[int]) -> dict[int, StrategyModel]:
    if not strategy_ids:
        return {}
    return {
        strategy.pk: strategy
        for strategy in StrategyModel.objects.filter(id__in=strategy_ids).only("id", "name", "bk_biz_id", "scenario")
    }


def _system_event_get_bk_tenant_map(bk_biz_ids: set[int]) -> dict[int, str]:
    """按业务批量解析租户 ID，解析失败（如业务已删除）的业务直接跳过。"""
    tenant_map: dict[int, str] = {}
    for bk_biz_id in bk_biz_ids:
        try:
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        except ValueError:
            continue
        if bk_tenant_id:
            tenant_map[bk_biz_id] = bk_tenant_id
    return tenant_map


def _system_event_build_metric(bk_tenant_id: str, bk_biz_id: int, custom_event_name: str) -> SystemEventMetric:
    """
    直接按业务推导内置系统事件的目标指标，不再回查 MetricListCache。

    多租户下 GSE 系统事件走分业务 custom event 链路，结果表命名固定为
    ``base_{bk_tenant_id}_{bk_biz_id}_event``（见 metric_list_cache.get_system_event_tables 与
    os_loader），聚合周期固定 1 分钟，故这些字段可由业务与租户直接推导。
    """
    return SystemEventMetric(
        bk_biz_id=bk_biz_id,
        custom_event_name=custom_event_name,
        result_table_id=f"base_{bk_tenant_id}_{bk_biz_id}_event",
        agg_interval=SYSTEM_EVENT_AGG_INTERVAL,
        data_label="",
    )


def _system_event_build_skip_record(
    query_config: QueryConfigModel,
    target_config: SystemEventTargetConfig,
    reason: str,
    strategy: StrategyModel | None = None,
) -> dict[str, Any]:
    record = {
        "reason": reason,
        "query_config_id": query_config.pk,
        "strategy_id": query_config.strategy_id,
        "item_id": query_config.item_id,
        "old_metric_id": query_config.metric_id,
        "old_event_name": target_config.old_event_name,
        "new_custom_event_name": target_config.custom_event_name,
    }
    if strategy is not None:
        record["strategy_name"] = strategy.name
        record["bk_biz_id"] = strategy.bk_biz_id
    return record


def _system_event_build_change_record(
    query_config: QueryConfigModel,
    strategy: StrategyModel,
    target_config: SystemEventTargetConfig,
    target_metric: SystemEventMetric,
) -> dict[str, Any]:
    old_config = query_config.config or {}
    # 存量的过滤条件（agg_condition）需要继承，避免迁移后丢失用户已有的告警过滤逻辑。
    inherited_agg_condition = deepcopy(old_config.get("agg_condition") or [])
    new_config = {
        "result_table_id": target_metric.result_table_id,
        "agg_method": "COUNT",
        "agg_interval": target_metric.agg_interval,
        "agg_dimension": list(target_config.agg_dimension),
        "agg_condition": inherited_agg_condition,
        "custom_event_name": target_config.custom_event_name,
    }
    if target_metric.data_label:
        new_config["data_label"] = target_metric.data_label

    new_metric_id = get_metric_id(
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.EVENT,
        result_table_id=target_metric.result_table_id,
        custom_event_name=target_config.custom_event_name,
    )

    return {
        "action": "update",
        "strategy_id": strategy.pk,
        "strategy_name": strategy.name,
        "bk_biz_id": strategy.bk_biz_id,
        "scenario": strategy.scenario,
        "query_config_id": query_config.pk,
        "item_id": query_config.item_id,
        "alias": query_config.alias,
        "old_event_name": target_config.old_event_name,
        "new_custom_event_name": target_config.custom_event_name,
        "old_metric_id": query_config.metric_id,
        "new_metric_id": new_metric_id,
        "old_data_source_label": query_config.data_source_label,
        "new_data_source_label": DataSourceLabel.CUSTOM,
        "old_data_type_label": query_config.data_type_label,
        "new_data_type_label": DataTypeLabel.EVENT,
        "old_result_table_id": old_config.get("result_table_id"),
        "new_result_table_id": target_metric.result_table_id,
        "old_custom_event_name": old_config.get("custom_event_name"),
        "old_agg_dimension": old_config.get("agg_dimension"),
        "new_agg_dimension": list(target_config.agg_dimension),
        "old_agg_condition": old_config.get("agg_condition"),
        "new_agg_condition": deepcopy(inherited_agg_condition),
        "old_agg_method": old_config.get("agg_method"),
        "new_agg_method": "COUNT",
        "old_config": deepcopy(old_config),
        "new_config": new_config,
        "new_algorithm_type": "Threshold",
        "new_algorithm_config": deepcopy(TARGET_ALGORITHM_CONFIG),
        "new_trigger_config": deepcopy(target_config.trigger_config),
        "new_recovery_config": deepcopy(target_config.recovery_config),
        "applied": False,
    }


def _system_event_fill_item_info(change_records: list[dict[str, Any]]) -> None:
    item_ids = {record["item_id"] for record in change_records}
    if not item_ids:
        return

    items = {item.pk: item for item in ItemModel.objects.filter(id__in=item_ids).only("id", "name", "metric_type")}
    for record in change_records:
        item = items.get(record["item_id"])
        if item is None:
            continue
        record["item_name"] = item.name
        record["old_item_metric_type"] = item.metric_type
        record["new_item_metric_type"] = DataTypeLabel.EVENT


def _system_event_fill_algorithm_info(change_records: list[dict[str, Any]]) -> None:
    item_ids = {record["item_id"] for record in change_records}
    if not item_ids:
        return

    algorithms_by_item: dict[int, list[AlgorithmModel]] = {}
    algorithms = (
        AlgorithmModel.objects.filter(item_id__in=item_ids)
        .only("id", "strategy_id", "item_id", "level", "type", "config")
        .order_by("item_id", "level", "id")
    )
    for algorithm in algorithms:
        algorithms_by_item.setdefault(algorithm.item_id, []).append(algorithm)

    for record in change_records:
        record["old_algorithms"] = [
            {
                "id": algorithm.pk,
                "level": algorithm.level,
                "type": algorithm.type,
                "config": deepcopy(algorithm.config),
            }
            for algorithm in algorithms_by_item.get(record["item_id"], [])
        ]


def _system_event_fill_detect_info(change_records: list[dict[str, Any]]) -> None:
    strategy_ids = {record["strategy_id"] for record in change_records}
    if not strategy_ids:
        return

    detects_by_strategy: dict[int, list[DetectModel]] = {}
    detects = (
        DetectModel.objects.filter(strategy_id__in=strategy_ids)
        .only("id", "strategy_id", "level", "trigger_config", "recovery_config")
        .order_by("strategy_id", "level", "id")
    )
    for detect in detects:
        detects_by_strategy.setdefault(detect.strategy_id, []).append(detect)

    for record in change_records:
        record["old_detects"] = [
            {
                "id": detect.pk,
                "level": detect.level,
                "trigger_config": deepcopy(detect.trigger_config),
                "recovery_config": deepcopy(detect.recovery_config),
            }
            for detect in detects_by_strategy.get(record["strategy_id"], [])
        ]


def _system_event_apply_change_records(change_records: list[dict[str, Any]]) -> None:
    if not change_records:
        return

    record_map = {record["query_config_id"]: record for record in change_records}
    applied_records: list[dict[str, Any]] = []
    update_query_configs: list[QueryConfigModel] = []
    update_items: list[ItemModel] = []
    update_algorithms: list[AlgorithmModel] = []
    update_detects: list[DetectModel] = []

    with transaction.atomic():
        query_configs = QueryConfigModel.objects.select_for_update().filter(id__in=list(record_map))
        for query_config in query_configs:
            record = record_map[query_config.pk]
            if query_config.metric_id != record["old_metric_id"]:
                record["stale"] = True
                record["current_metric_id"] = query_config.metric_id
                continue

            query_config.data_source_label = record["new_data_source_label"]
            query_config.data_type_label = record["new_data_type_label"]
            query_config.metric_id = record["new_metric_id"]
            query_config.config = deepcopy(record["new_config"])
            update_query_configs.append(query_config)
            applied_records.append(record)
            record["applied"] = True

        if not applied_records:
            return

        applied_item_ids = {record["item_id"] for record in applied_records}
        applied_strategy_ids = {record["strategy_id"] for record in applied_records}
        record_by_item = {record["item_id"]: record for record in applied_records}
        record_by_strategy = {record["strategy_id"]: record for record in applied_records}

        items = ItemModel.objects.select_for_update().filter(id__in=applied_item_ids)
        for item in items:
            item.metric_type = DataTypeLabel.EVENT
            update_items.append(item)

        algorithms = AlgorithmModel.objects.select_for_update().filter(item_id__in=applied_item_ids)
        for algorithm in algorithms:
            record = record_by_item[algorithm.item_id]
            algorithm.type = record["new_algorithm_type"]
            algorithm.config = deepcopy(record["new_algorithm_config"])
            update_algorithms.append(algorithm)
            record.setdefault("applied_algorithm_ids", []).append(algorithm.pk)

        detects = DetectModel.objects.select_for_update().filter(strategy_id__in=applied_strategy_ids)
        for detect in detects:
            record = record_by_strategy[detect.strategy_id]
            detect.trigger_config = deepcopy(record["new_trigger_config"])
            detect.recovery_config = deepcopy(record["new_recovery_config"])
            update_detects.append(detect)
            record.setdefault("applied_detect_ids", []).append(detect.pk)

        if update_query_configs:
            QueryConfigModel.objects.bulk_update(
                update_query_configs,
                fields=["data_source_label", "data_type_label", "metric_id", "config"],
                batch_size=500,
            )
        if update_items:
            ItemModel.objects.bulk_update(update_items, fields=["metric_type"], batch_size=500)
        if update_algorithms:
            AlgorithmModel.objects.bulk_update(update_algorithms, fields=["type", "config"], batch_size=500)
        if update_detects:
            DetectModel.objects.bulk_update(
                update_detects, fields=["trigger_config", "recovery_config"], batch_size=500
            )


# ---------------------------------------------------------------------------
# gather_up 采集状态策略迁移
# ---------------------------------------------------------------------------

# 单租户默认策略（见 metadata migration 0177_add_gather_up_dataid）硬编码的全局 gather_up 结果表。
# 多租户下 gather_up 走自定义时序（custom time series）链路：按业务建链时每个业务拥有独立结果表，
# 按租户建链时使用不带业务/租户前缀的中立结果表（见 metadata.task.tasks 建链逻辑）。
# 迁移时需把存量策略改为引用对应结果表，并将数据来源切换为自定义时序。
GATHER_UP_LEGACY_RESULT_TABLE_ID = "bkmonitorbeat_gather_up.__default__"
# GATHER_UP_METRIC_FIELD / get_gather_up_result_table_id 统一由默认策略配置（datalink.v1）提供，
# 确保存量迁移与新建默认策略使用完全一致的结果表命名与指标字段。


def migrate_gather_up_strategy_config(
    bk_biz_id: int | Iterable[int] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    将存量 gather_up（采集任务状态）内置告警策略迁移到多租户分业务自定义时序引用方式。

    单租户默认策略（``DatalinkDefaultAlarmStrategyLoader`` 自动创建）硬编码了全局结果表
    ``bkmonitorbeat_gather_up.__default__``。多租户下需要把查询配置改为引用对应的 gather_up 结果表：
    按业务建链时使用分业务结果表，按租户建链时使用不带业务/租户前缀的中立结果表，并把数据来源
    切换为自定义时序（``data_source_label=custom``、``data_type_label=time_series``）。

    覆盖两类存量形态：仍指向全局结果表的原始策略，以及此前已迁移为 data_label 引用（``result_table_id``
    为空、``data_label=bkmonitorbeat_gather_up``）的中间态策略，统一收敛到分业务自定义时序引用。

    仅处理 ``source`` 为 ``DEFAULT_DATALINK_COLLECTING_FLAG`` 的内置采集告警策略，避免误改用户策略。
    单租户环境（``ENABLE_MULTI_TENANT_MODE`` 关闭）直接跳过；业务无法解析租户（如已删除）时跳过该业务。

    Args:
        bk_biz_id: 可选业务 ID 或业务 ID 列表；不传时扫描全量内置采集告警策略。
        dry_run: 为 ``True`` 时仅返回计划变更，不落库。

    Returns:
        迁移结果报告，包含变更明细与统计计数。
    """
    bk_biz_ids = _normalize_ids(bk_biz_id)
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return _build_empty_report(
            dry_run=dry_run,
            bk_biz_ids=bk_biz_ids,
            message="ENABLE_MULTI_TENANT_MODE is disabled, gather_up strategy migration skipped",
        )

    change_records = _gather_up_collect_change_records(bk_biz_ids=bk_biz_ids)
    if not dry_run:
        _gather_up_apply_change_records(change_records)

    return {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "changed_count": len(change_records),
        "applied_count": len([record for record in change_records if record.get("applied")]),
        "stale_count": len([record for record in change_records if record.get("stale")]),
        "changes": deepcopy(change_records),
    }


def _gather_up_collect_change_records(bk_biz_ids: list[int] | None) -> list[dict[str, Any]]:
    strategy_queryset = StrategyModel.objects.filter(source=DEFAULT_DATALINK_COLLECTING_FLAG)
    if bk_biz_ids is not None:
        strategy_queryset = strategy_queryset.filter(bk_biz_id__in=bk_biz_ids)

    strategy_map = {strategy.pk: strategy for strategy in strategy_queryset.only("id", "name", "bk_biz_id")}
    if not strategy_map:
        return []

    # 结果表命名需要租户 ID，按业务批量解析，解析失败（如业务已删除）的业务后续跳过。
    tenant_map = _gather_up_get_bk_tenant_map({strategy.bk_biz_id for strategy in strategy_map.values()})

    query_configs = (
        QueryConfigModel.objects.filter(
            strategy_id__in=list(strategy_map),
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
        )
        .only(
            "id",
            "strategy_id",
            "item_id",
            "alias",
            "metric_id",
            "data_source_label",
            "data_type_label",
            "config",
        )
        .order_by("strategy_id", "id")
    )

    change_records: list[dict[str, Any]] = []
    for query_config in query_configs.iterator(chunk_size=1000):
        config = query_config.config or {}
        if not _gather_up_is_migratable_config(config):
            continue
        strategy = strategy_map.get(query_config.strategy_id)
        if strategy is None:
            continue
        bk_tenant_id = tenant_map.get(strategy.bk_biz_id)
        if not bk_tenant_id:
            # 业务无法解析租户（如已删除），跳过，避免生成错误的结果表命名。
            continue
        change_records.append(
            _gather_up_build_change_record(
                query_config=query_config,
                config=config,
                strategy=strategy,
                bk_tenant_id=bk_tenant_id,
            )
        )

    return change_records


def _gather_up_get_bk_tenant_map(bk_biz_ids: set[int]) -> dict[int, str]:
    """按业务批量解析租户 ID，解析失败（如业务已删除）的业务直接跳过。"""
    tenant_map: dict[int, str] = {}
    for bk_biz_id in bk_biz_ids:
        try:
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        except ValueError:
            continue
        if bk_tenant_id:
            tenant_map[bk_biz_id] = bk_tenant_id
    return tenant_map


def _gather_up_is_migratable_config(config: dict[str, Any]) -> bool:
    """判断查询配置是否为待迁移的 gather_up 存量形态。

    覆盖两类：仍指向全局结果表 ``bkmonitorbeat_gather_up.__default__`` 的原始策略，以及此前迁移为
    data_label 引用（``result_table_id`` 为空、``data_label=bkmonitorbeat_gather_up``）的中间态策略。
    已收敛到分业务结果表的策略（``result_table_id`` 指向真实业务表）不再匹配。
    """
    result_table_id = config.get("result_table_id")
    if result_table_id == GATHER_UP_LEGACY_RESULT_TABLE_ID:
        return True
    if not result_table_id and config.get("data_label") == GATHER_UP_DATA_LABEL:
        return True
    return False


def _gather_up_build_change_record(
    query_config: QueryConfigModel,
    config: dict[str, Any],
    strategy: StrategyModel,
    bk_tenant_id: str,
) -> dict[str, Any]:
    metric_field = config.get("metric_field") or GATHER_UP_METRIC_FIELD
    new_result_table_id = get_gather_up_result_table_id(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=strategy.bk_biz_id,
        space_builtin_data_link_mode=settings.SPACE_BUILTIN_DATA_LINK_MODE,
    )
    # 自定义时序指标 ID：custom.{result_table_id}.bkm_gather_up
    new_metric_id = get_metric_id(
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        result_table_id=new_result_table_id,
        metric_field=metric_field,
    )
    return {
        "action": "update",
        "model": "bkmonitor.QueryConfigModel",
        "table": QueryConfigModel._meta.db_table,
        "query_config_id": query_config.pk,
        "strategy_id": query_config.strategy_id,
        "strategy_name": strategy.name,
        "bk_biz_id": strategy.bk_biz_id,
        "bk_tenant_id": bk_tenant_id,
        "item_id": query_config.item_id,
        "alias": query_config.alias,
        "metric_field": metric_field,
        "old_data_source_label": query_config.data_source_label,
        "new_data_source_label": DataSourceLabel.CUSTOM,
        "old_data_type_label": query_config.data_type_label,
        "new_data_type_label": DataTypeLabel.TIME_SERIES,
        "old_result_table_id": config.get("result_table_id"),
        "new_result_table_id": new_result_table_id,
        "old_data_label": config.get("data_label", ""),
        "new_data_label": GATHER_UP_DATA_LABEL,
        "old_metric_id": query_config.metric_id,
        "new_metric_id": new_metric_id,
        "applied": False,
    }


def _gather_up_apply_change_records(change_records: list[dict[str, Any]]) -> None:
    if not change_records:
        return

    record_map = {record["query_config_id"]: record for record in change_records}
    update_query_configs: list[QueryConfigModel] = []

    with transaction.atomic():
        query_configs = QueryConfigModel.objects.select_for_update().filter(id__in=list(record_map))
        for query_config in query_configs:
            record = record_map[query_config.pk]
            # 以 metric_id 作为幂等/防并发基准：与采集时不一致说明已被其他流程改写，跳过。
            if query_config.metric_id != record["old_metric_id"]:
                record["stale"] = True
                record["current_metric_id"] = query_config.metric_id
                continue

            new_config = deepcopy(query_config.config or {})
            new_config["result_table_id"] = record["new_result_table_id"]
            # 保留同名 data_label 作为兜底引用，与默认策略加载器（DatalinkDefaultAlarmStrategyLoader）保持一致。
            new_config["data_label"] = record["new_data_label"]
            query_config.config = new_config
            query_config.data_source_label = record["new_data_source_label"]
            query_config.data_type_label = record["new_data_type_label"]
            query_config.metric_id = record["new_metric_id"]
            update_query_configs.append(query_config)
            record["applied"] = True

        if update_query_configs:
            QueryConfigModel.objects.bulk_update(
                update_query_configs,
                fields=["data_source_label", "data_type_label", "metric_id", "config"],
                batch_size=500,
            )
