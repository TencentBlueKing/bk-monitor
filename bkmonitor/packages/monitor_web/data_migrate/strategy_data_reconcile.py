from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PACKAGES_ROOT = REPO_ROOT / "packages"
if str(PACKAGES_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGES_ROOT))
AI_AGENT_SDK_ROOT = REPO_ROOT / "ai_agent" / "sdk"
if AI_AGENT_SDK_ROOT.exists() and str(AI_AGENT_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_SDK_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
os.environ.setdefault("DJANGO_CONF_MODULE", "conf.worker.development.tencent")

from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID


DEFAULT_TIME_RANGE_SECONDS = 3600
DEFAULT_STRATEGY_WORKERS = 4
MAX_STRATEGY_WORKERS = 32
SYSTEM_EVENT_METRIC_IDS = frozenset(
    {
        "bk_monitor.agent-gse",
        "bk_monitor.disk-readonly-gse",
        "bk_monitor.disk-full-gse",
        "bk_monitor.corefile-gse",
        "bk_monitor.oom-gse",
    }
)


def collect_strategy_data_stats(
    *,
    bk_biz_id: int,
    start_time: int | None = None,
    end_time: int | None = None,
    strategy_ids: Iterable[int] | None = None,
    include_dimension_keys: bool = False,
    max_workers: int = DEFAULT_STRATEGY_WORKERS,
) -> dict[str, Any]:
    """
    查询指定业务下每条策略在给定时间段内的数据量，用于迁移前后对账。

    统计口径：
    - 使用 StrategyCacheManager 生成的后台策略配置，与 access.data 查询配置保持一致。
    - 每个 item 调用 item.query_record(start_time, end_time) 查询原始数据。
    - 原始点转换为 DataRecord 后执行 access.data 的 fuller/filter/clean 流程，再统计最终保留的数据点。
    - 不执行 Duplicate 去重和 push，避免写 Redis 或影响线上检测状态。
    - GSE 系统事件策略走 Kafka 告警链路，当前无法按时间段统计，直接跳过。
    - 按策略粒度并发查询；max_workers=1 时退化为串行执行。
    """
    now = int(time.time())
    resolved_end_time = int(end_time or now)
    resolved_start_time = int(start_time or resolved_end_time - DEFAULT_TIME_RANGE_SECONDS)
    selected_strategy_ids = _normalize_strategy_ids(strategy_ids)
    resolved_max_workers = _normalize_max_workers(max_workers)

    strategy_configs = _get_strategy_configs(int(bk_biz_id))
    if selected_strategy_ids is not None:
        strategy_configs = {
            strategy_id: strategy_config
            for strategy_id, strategy_config in strategy_configs.items()
            if int(strategy_id) in selected_strategy_ids
        }

    strategy_results = []
    skipped_results = []
    strategy_jobs = []
    for strategy_id in sorted(strategy_configs):
        strategy_config = strategy_configs[strategy_id]
        if _is_system_event_strategy(strategy_config):
            skipped_results.append(
                _build_skipped_strategy_record(
                    strategy_config=strategy_config,
                    reason="system event strategy uses kafka and is not query-countable",
                )
            )
            continue

        strategy_jobs.append(
            {
                "strategy_id": int(strategy_id),
                "strategy_config": strategy_config,
                "start_time": resolved_start_time,
                "end_time": resolved_end_time,
                "include_dimension_keys": include_dimension_keys,
            }
        )
    strategy_results = _collect_strategy_jobs(strategy_jobs, max_workers=resolved_max_workers)

    return _build_report(
        bk_biz_id=int(bk_biz_id),
        start_time=resolved_start_time,
        end_time=resolved_end_time,
        strategies=strategy_results,
        skipped=skipped_results,
        selected_strategy_ids=sorted(selected_strategy_ids) if selected_strategy_ids is not None else None,
        max_workers=resolved_max_workers,
    )


def _normalize_strategy_ids(strategy_ids: Iterable[int] | None) -> set[int] | None:
    if strategy_ids is None:
        return None
    return {int(strategy_id) for strategy_id in strategy_ids}


def _normalize_max_workers(max_workers: int | None) -> int:
    if max_workers in (None, ""):
        return DEFAULT_STRATEGY_WORKERS
    try:
        normalized_value = int(max_workers)
    except (TypeError, ValueError):
        return DEFAULT_STRATEGY_WORKERS
    return min(max(normalized_value, 1), MAX_STRATEGY_WORKERS)


def _get_strategy_configs(bk_biz_id: int) -> dict[int, dict[str, Any]]:
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    return StrategyCacheManager.get_strategies_map(bk_biz_ids=[bk_biz_id])


def _collect_strategy_jobs(strategy_jobs: list[dict[str, Any]], *, max_workers: int) -> list[dict[str, Any]]:
    if not strategy_jobs:
        return []
    if max_workers <= 1 or len(strategy_jobs) == 1:
        return [_collect_one_strategy_job(strategy_job) for strategy_job in strategy_jobs]

    worker_count = min(max_workers, len(strategy_jobs))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(_collect_one_strategy_job, strategy_jobs))


def _collect_one_strategy_job(strategy_job: dict[str, Any]) -> dict[str, Any]:
    _close_old_connections_safely()
    try:
        return _collect_one_strategy_stats(**strategy_job)
    finally:
        _close_old_connections_safely()


def _close_old_connections_safely() -> None:
    try:
        from django.conf import settings
        from django.db import close_old_connections

        if settings.configured:
            close_old_connections()
    except Exception:
        return


def _collect_one_strategy_stats(
    *,
    strategy_id: int,
    strategy_config: dict[str, Any],
    start_time: int,
    end_time: int,
    include_dimension_keys: bool,
) -> dict[str, Any]:
    from alarm_backends.core.control.strategy import Strategy

    strategy = Strategy(strategy_id, default_config=strategy_config)
    item_results = []
    for item in strategy.items:
        item_results.append(
            _collect_one_item_stats(
                item=item,
                start_time=start_time,
                end_time=end_time,
                include_dimension_keys=include_dimension_keys,
            )
        )

    errors = [error for item_result in item_results for error in item_result.get("errors", [])]
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy.name,
        "bk_biz_id": int(strategy.bk_biz_id),
        "scenario": strategy.scenario,
        "type": strategy.type,
        "items": item_results,
        "raw_data_point_count": sum(item_result["raw_data_point_count"] for item_result in item_results),
        "data_point_count": sum(item_result["data_point_count"] for item_result in item_results),
        "dimension_combination_count": sum(item_result["dimension_combination_count"] for item_result in item_results),
        "error_count": len(errors),
        "errors": errors,
    }


def _collect_one_item_stats(
    *,
    item: Any,
    start_time: int,
    end_time: int,
    include_dimension_keys: bool,
) -> dict[str, Any]:
    try:
        raw_points = item.query_record(start_time, end_time)
        records, none_point_count = _build_data_records(item, raw_points)
        retained_records = _filter_records_with_access_flow(item, records)
        stat = _summarize_records(
            records=retained_records,
            include_dimension_keys=include_dimension_keys,
        )
        stat.update(
            {
                "item_id": item.id,
                "item_name": item.name,
                "query_md5": item.item_config.get("query_md5", ""),
                "query_configs": [_summarize_query_config(query_config) for query_config in item.query_configs],
                "raw_data_point_count": len(raw_points),
                "none_point_count": none_point_count,
                "errors": [],
            }
        )
        return stat
    except Exception as error:  # noqa: BLE001 - one failed strategy should not stop the whole reconciliation.
        return {
            "item_id": item.id,
            "item_name": item.name,
            "query_md5": item.item_config.get("query_md5", ""),
            "query_configs": [_summarize_query_config(query_config) for query_config in item.query_configs],
            "raw_data_point_count": 0,
            "data_point_count": 0,
            "none_point_count": 0,
            "dimension_combination_count": 0,
            "dimension_keys": [] if include_dimension_keys else None,
            "dimension_counts": {} if include_dimension_keys else None,
            "first_data_time": None,
            "last_data_time": None,
            "errors": [{"item_id": item.id, "message": str(error)}],
        }


def _build_data_records(item: Any, raw_points: list[dict[str, Any]]) -> tuple[list[Any], int]:
    from alarm_backends.service.access.data.records import DataRecord, get_value_from_raw_data

    records = []
    none_point_count = 0
    for raw_point in raw_points:
        if get_value_from_raw_data(raw_point, item) is None:
            none_point_count += 1
            continue
        records.append(DataRecord(item, raw_point))
    return records, none_point_count


def _filter_records_with_access_flow(item: Any, records: list[Any]) -> list[Any]:
    if not records:
        return []

    from alarm_backends.service.access.data.processor import BaseAccessDataProcess

    processor = BaseAccessDataProcess()
    processor.record_list = records
    processor.handle()
    return [
        record for record in processor.record_list if record.is_retains[item.id] and not record.inhibitions[item.id]
    ]


def _summarize_records(
    *,
    records: list[Any],
    include_dimension_keys: bool,
) -> dict[str, Any]:
    dimension_counts = Counter(_stable_dimension_key(record.data.get("dimensions", {})) for record in records)
    data_times = [record.data.get("time") for record in records if record.data.get("time") is not None]

    result = {
        "data_point_count": len(records),
        "dimension_combination_count": len(dimension_counts),
        "first_data_time": min(data_times) if data_times else None,
        "last_data_time": max(data_times) if data_times else None,
    }
    if include_dimension_keys:
        result["dimension_keys"] = sorted(dimension_counts)
        result["dimension_counts"] = dict(sorted(dimension_counts.items()))
    return result


def _stable_dimension_key(dimensions: dict[str, Any]) -> str:
    return json.dumps(dimensions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _summarize_query_config(query_config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "alias",
        "data_source_label",
        "data_type_label",
        "metric_id",
        "result_table_id",
        "metric_field",
        "agg_method",
        "agg_interval",
        "agg_dimension",
    ]
    return {key: query_config.get(key) for key in keys if key in query_config}


def _is_system_event_strategy(strategy_config: dict[str, Any]) -> bool:
    for item in strategy_config.get("items") or []:
        for query_config in item.get("query_configs") or []:
            data_source_label = query_config.get("data_source_label")
            data_type_label = query_config.get("data_type_label")
            result_table_id = query_config.get("result_table_id") or query_config.get("config", {}).get(
                "result_table_id"
            )
            metric_id = query_config.get("metric_id")
            if (
                data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
                and data_type_label == DataTypeLabel.EVENT
                and (result_table_id == SYSTEM_EVENT_RT_TABLE_ID or metric_id in SYSTEM_EVENT_METRIC_IDS)
            ):
                return True
    return False


def _build_skipped_strategy_record(strategy_config: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy_config.get("id"),
        "strategy_name": strategy_config.get("name"),
        "bk_biz_id": strategy_config.get("bk_biz_id"),
        "scenario": strategy_config.get("scenario"),
        "type": strategy_config.get("type"),
        "reason": reason,
    }


def _build_report(
    *,
    bk_biz_id: int,
    start_time: int,
    end_time: int,
    strategies: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    selected_strategy_ids: list[int] | None,
    max_workers: int,
) -> dict[str, Any]:
    errors = [error for strategy in strategies for error in strategy.get("errors", [])]
    return {
        "bk_biz_id": bk_biz_id,
        "selected_strategy_ids": selected_strategy_ids,
        "time_range": {"start_time": start_time, "end_time": end_time},
        "max_workers": max_workers,
        "strategy_count": len(strategies),
        "skipped_strategy_count": len(skipped),
        "raw_data_point_count": sum(strategy["raw_data_point_count"] for strategy in strategies),
        "data_point_count": sum(strategy["data_point_count"] for strategy in strategies),
        "dimension_combination_count": sum(strategy["dimension_combination_count"] for strategy in strategies),
        "error_count": len(errors),
        "strategies": strategies,
        "skipped": skipped,
        "errors": errors,
    }


def _setup_django() -> None:
    import django

    django.setup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统计业务策略在指定时间段内的查询结果，用于迁移前后数据对账")
    parser.add_argument("--bk-biz-id", type=int, required=True, help="业务 ID")
    parser.add_argument("--from", dest="start_time", type=int, help="开始时间戳，单位秒；默认最近 1 小时")
    parser.add_argument("--until", dest="end_time", type=int, help="结束时间戳，单位秒；默认当前时间")
    parser.add_argument("--strategy-ids", nargs="+", type=int, help="只统计指定策略 ID")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_STRATEGY_WORKERS,
        help=f"策略查询并发数，默认 {DEFAULT_STRATEGY_WORKERS}，最大 {MAX_STRATEGY_WORKERS}；设置为 1 表示串行",
    )
    parser.add_argument(
        "--include-dimension-keys",
        action="store_true",
        help="输出每个维度组合的稳定 JSON key 以及点数；数据量大时输出会明显变大",
    )
    parser.add_argument("--output", help="结果 JSON 输出路径；不传则输出到 stdout")
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进，默认 2")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _setup_django()
    report = collect_strategy_data_stats(
        bk_biz_id=args.bk_biz_id,
        start_time=args.start_time,
        end_time=args.end_time,
        strategy_ids=args.strategy_ids,
        include_dimension_keys=args.include_dimension_keys,
        max_workers=args.max_workers,
    )
    output = json.dumps(report, ensure_ascii=False, indent=args.indent, sort_keys=True)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"strategy data reconcile result written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
