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
from bkmonitor.models.metric_list_cache import MetricListCache
from constants.data_source import DataSourceLabel, DataTypeLabel


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


SYSTEM_EVENT_TARGET_CONFIGS: dict[str, SystemEventTargetConfig] = {
    "bk_monitor.agent-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.agent-gse",
        old_event_name="agent-gse",
        custom_event_name="AgentLost",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id"],
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
        trigger_config={"count": 1, "check_window": 10},
        recovery_config={"check_window": 10, "status_setter": "close"},
    ),
    "bk_monitor.oom-gse": SystemEventTargetConfig(
        old_metric_id="bk_monitor.oom-gse",
        old_event_name="oom-gse",
        custom_event_name="OOM",
        agg_dimension=["bk_target_ip", "bk_target_cloud_id", "process", "constraint"],
        trigger_config={"count": 1, "check_window": 10},
        recovery_config={"check_window": 10, "status_setter": "close"},
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
        )

    change_records, skipped_records = _collect_change_records(bk_biz_ids=bk_biz_ids)
    if not dry_run:
        _apply_change_records(change_records)

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


def _normalize_ids(ids: int | str | Iterable[int] | None) -> list[int] | None:
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


def _build_empty_report(*, dry_run: bool, bk_biz_ids: list[int] | None, message: str) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "changed_count": 0,
        "applied_count": 0,
        "stale_count": 0,
        "skipped_count": 0,
        "changes": [],
        "skipped": [],
        "message": message,
    }


def _collect_change_records(
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

    strategies = _get_strategy_map({query_config.strategy_id for query_config in query_configs})
    target_metric_map = _get_system_event_metric_map(
        {strategy.bk_biz_id for strategy in strategies.values() if strategy.bk_biz_id > 0}
    )

    change_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    for query_config in query_configs:
        target_config = SYSTEM_EVENT_TARGET_CONFIGS[query_config.metric_id]
        strategy = strategies.get(query_config.strategy_id)
        if strategy is None:
            skipped_records.append(
                _build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    reason="strategy not found",
                )
            )
            continue
        if strategy.bk_biz_id <= 0:
            skipped_records.append(
                _build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    strategy=strategy,
                    reason="non-positive bk_biz_id has no built-in custom event table",
                )
            )
            continue

        target_metric = target_metric_map.get((strategy.bk_biz_id, target_config.custom_event_name))
        if target_metric is None:
            skipped_records.append(
                _build_skip_record(
                    query_config=query_config,
                    target_config=target_config,
                    strategy=strategy,
                    reason="target custom event metric not found in MetricListCache",
                )
            )
            continue

        change_records.append(
            _build_change_record(
                query_config=query_config,
                strategy=strategy,
                target_config=target_config,
                target_metric=target_metric,
            )
        )

    _fill_item_info(change_records)
    _fill_algorithm_info(change_records)
    _fill_detect_info(change_records)
    return change_records, skipped_records


def _get_strategy_map(strategy_ids: set[int]) -> dict[int, StrategyModel]:
    if not strategy_ids:
        return {}
    return {
        strategy.pk: strategy
        for strategy in StrategyModel.objects.filter(id__in=strategy_ids).only("id", "name", "bk_biz_id", "scenario")
    }


def _get_system_event_metric_map(bk_biz_ids: set[int]) -> dict[tuple[int, str], SystemEventMetric]:
    if not bk_biz_ids:
        return {}

    target_event_names = {config.custom_event_name for config in SYSTEM_EVENT_TARGET_CONFIGS.values()}
    metric_map: dict[tuple[int, str], SystemEventMetric] = {}
    metrics = (
        MetricListCache.objects.filter(
            bk_biz_id__in=bk_biz_ids,
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.EVENT,
            result_table_label__in=["os", "host_process"],
        )
        .only(
            "bk_biz_id",
            "metric_field",
            "result_table_id",
            "collect_interval",
            "extend_fields",
            "data_label",
        )
        .order_by("bk_biz_id", "result_table_id", "metric_field")
    )

    for metric in metrics:
        custom_event_name = (metric.extend_fields or {}).get("custom_event_name") or metric.metric_field
        if custom_event_name not in target_event_names:
            continue
        metric_map.setdefault(
            (metric.bk_biz_id, custom_event_name),
            SystemEventMetric(
                bk_biz_id=metric.bk_biz_id,
                custom_event_name=custom_event_name,
                result_table_id=metric.result_table_id,
                agg_interval=(metric.collect_interval or 1) * 60,
                data_label=metric.data_label or "",
            ),
        )

    return metric_map


def _build_skip_record(
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


def _build_change_record(
    query_config: QueryConfigModel,
    strategy: StrategyModel,
    target_config: SystemEventTargetConfig,
    target_metric: SystemEventMetric,
) -> dict[str, Any]:
    old_config = query_config.config or {}
    new_config = {
        "result_table_id": target_metric.result_table_id,
        "agg_method": "COUNT",
        "agg_interval": target_metric.agg_interval,
        "agg_dimension": list(target_config.agg_dimension),
        "agg_condition": [],
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


def _fill_item_info(change_records: list[dict[str, Any]]) -> None:
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


def _fill_algorithm_info(change_records: list[dict[str, Any]]) -> None:
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


def _fill_detect_info(change_records: list[dict[str, Any]]) -> None:
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


def _apply_change_records(change_records: list[dict[str, Any]]) -> None:
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
