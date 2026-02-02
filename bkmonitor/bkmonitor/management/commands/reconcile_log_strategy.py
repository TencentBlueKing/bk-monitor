"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
灰度切换 UnifyQuery 查询结果对账命令。

本命令用于验证日志平台数据源切换到 unify-query 前后查询结果的一致性。
通过分别启用和禁用灰度开关进行查询，比较两种查询方式的结果是否一致。

灰度控制机制：通过 LogSearchTimeSeriesDataSource.LOG_UNIFY_QUERY_WHITE_BIZ_LIST 类成员变量控制。

使用方法：

    # 模式 1：统计日志类策略数量
    python manage.py reconcile_log_strategy --mode=stat

    # 模式 2：查询对账（默认模式）
    python manage.py reconcile_log_strategy --mode=reconcile --biz-ids 1 2 3

    # 指定查询时间范围（秒级时间戳），默认取 (now - 30m, now)
    python manage.py reconcile_log_strategy --biz-ids 1 2 3 --start-time=1706169600 --end-time=1706171400

    # 指定输出文件路径
    python manage.py reconcile_log_strategy --biz-ids 1 2 3 --output=/tmp/reconciliation_result.csv
"""

import csv
import json
import time
from argparse import ArgumentParser
from collections import defaultdict
from enum import Enum
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, OutputWrapper
from django.core.management.color import Style

from alarm_backends.core.cache.cmdb import BusinessManager
from api.cmdb.define import Business
from bkmonitor.data_source import load_data_source, UnifyQuery
from bkmonitor.data_source.data_source import DataSource, LogSearchTimeSeriesDataSource
from bkmonitor.models import StrategyModel, QueryConfigModel
from bkmonitor.strategy.new_strategy import Strategy, Item
from constants.data_source import DataSourceLabel

# CSV 输出字段名（查询对账模式）
CSV_FIELDNAMES_RECONCILE: list[str] = [
    "bk_biz_id",
    "bk_biz_name",
    "strategy_id",
    "strategy_name",
    "strategy_url",
    "data_type_label",
    "is_consistent",
    "has_data",
    "uq_count",
    "ds_count",
    "diff_reason",
    "query_string",
    "agg_dimension",
    "query_config",
]

# CSV 输出字段名（策略统计模式）
CSV_FIELDNAMES_STAT: list[str] = [
    "bk_biz_id",
    "bk_biz_name",
    "strategy_count",
]


class DiffReason(Enum):
    """查询结果不一致原因枚举"""

    # datapoints 存在不一致
    DIFF_DATAPOINTS = "DIFF_DATAPOINTS"
    # 两种查询结果包含的维度字段不一致
    DIFF_DIMENSION_FIELD = "DIFF_DIMENSION_FIELD"
    # 两种查询结果包含的维度字段不一致，且多出来的维度字段值为空（原因：datasource 返回所有配置的维度字段，UnifyQuery 会过滤空值维度字段）
    EMPTY_DIMENSION_FIELD = "EMPTY_DIMENSION_FIELD"


class Command(BaseCommand):
    """日志平台数据源 UnifyQuery 灰度切换对账命令"""

    help = "对账日志平台数据源切换 unify-query 前后的查询结果一致性"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """添加命令行参数。"""
        parser.add_argument(
            "--mode",
            type=str,
            choices=["stat", "reconcile"],
            default="reconcile",
            help="运行模式：stat（统计日志类策略数量）或 reconcile（日志数据源查询对账，默认）",
        )
        parser.add_argument(
            "--biz-ids",
            nargs="+",
            type=int,
            required=False,
            default=None,
            help="需要处理的业务 ID 列表，例如：--biz-ids 1 2 3（查询对账模式必填）",
        )
        parser.add_argument(
            "--start-time",
            type=int,
            default=None,
            help="查询开始时间（秒级时间戳），默认为 now - 30m",
        )
        parser.add_argument(
            "--end-time",
            type=int,
            default=None,
            help="查询结束时间（秒级时间戳），默认为 now",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="reconciliation_result.csv",
            help="输出 CSV 文件路径，默认为当前目录下的 reconciliation_result.csv",
        )

    def handle(self, *args, **options) -> None:
        """命令执行入口"""
        bk_biz_ids: list[int] | None = options["biz_ids"]
        mode: str = options["mode"]
        output_path: str = str(options["output"])

        now: int = int(time.time())
        end_time: int = options["end_time"] or now
        start_time: int = options["start_time"] or (now - 30 * 60)

        self.stdout.write(self.style.SUCCESS(f"运行模式：{mode}，业务列表：{bk_biz_ids}"))

        if mode == "stat":
            run_stat_mode(bk_biz_ids, output_path, self.stdout, self.style)
        else:
            if not bk_biz_ids:
                self.stderr.write(self.style.ERROR("查询对账模式必须提供 --biz-ids 参数"))
                return

            self.stdout.write(f"查询时间范围：{start_time} ~ {end_time}")

            run_reconciliation(bk_biz_ids, start_time, end_time, output_path, self.stdout, self.style)

        self.stdout.write(self.style.SUCCESS("执行完成！"))


def get_biz_name(bk_biz_id: int) -> str:
    """获取业务名"""
    business: Business | None = BusinessManager.get(bk_biz_id)
    return business.bk_biz_name if business else str(bk_biz_id)


def get_log_strategy_ids() -> list[int]:
    """
    获取日志平台数据源关联的策略 ID 列表
    """
    return list(
        QueryConfigModel.objects.filter(data_source_label=DataSourceLabel.BK_LOG_SEARCH)
        .values_list("strategy_id", flat=True)
        .distinct()
    )


def write_results_to_csv(output_csv_path: str, fieldnames: list[str], results: list[dict[str, Any]]) -> None:
    """
    将结果列表写入 CSV 文件
    """
    with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer: csv.DictWriter[str] = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def run_stat_mode(bk_biz_ids: list[int] | None, output_csv_path: str, stdout: OutputWrapper, style: Style):
    """
    统计模式：统计各业务下日志类策略数量（若未指定业务 ID，则统计所有业务）
    """
    results: list[dict[str, Any]] = []

    # 一次性查询所有日志平台策略，按业务 ID 分组统计
    log_strategy_ids: list[int] = get_log_strategy_ids()
    if bk_biz_ids:
        # 指定业务 ID 时，使用 in 查询一次性获取
        queryset = StrategyModel.objects.filter(id__in=log_strategy_ids, is_enabled=True, bk_biz_id__in=bk_biz_ids)
    else:
        # 未指定业务 ID 时，统计所有业务
        queryset = StrategyModel.objects.filter(id__in=log_strategy_ids, is_enabled=True)

    # 按业务 ID 分组统计策略数量
    biz_strategy_counts: dict[int, int] = defaultdict(int)
    for biz_id in queryset.values_list("bk_biz_id", flat=True):
        biz_strategy_counts[biz_id] += 1

    # 构建结果列表，若指定业务 ID，按指定顺序输出，否则按业务 ID 升序输出
    target_biz_ids: list[int] = bk_biz_ids if bk_biz_ids else sorted(biz_strategy_counts.keys())
    for bk_biz_id in target_biz_ids:
        bk_biz_name: str = get_biz_name(bk_biz_id)
        strategy_count: int = biz_strategy_counts.get(bk_biz_id, 0)
        results.append({"bk_biz_id": bk_biz_id, "bk_biz_name": bk_biz_name, "strategy_count": strategy_count})
        stdout.write(f"业务 {bk_biz_id}（{bk_biz_name}）：{strategy_count} 个日志类策略")

    # 写入 CSV 文件
    write_results_to_csv(output_csv_path, CSV_FIELDNAMES_STAT, results)
    stdout.write(style.SUCCESS(f"统计结果已保存至：{output_csv_path}"))


def build_data_sources(strategy: Strategy) -> list[DataSource]:
    """
    根据策略构建数据源列表。
    """
    item: Item = strategy.items[0]
    data_sources: list[DataSource] = []
    for query_config in item.query_configs:
        query_config_dict: dict[str, Any] = query_config.to_dict()
        query_config_dict["target"] = item.target
        data_source_class = load_data_source(query_config.data_source_label, query_config.data_type_label)
        data_sources.append(
            data_source_class.init_by_query_config(
                query_config=query_config_dict,
                name=item.name,
                bk_biz_id=strategy.bk_biz_id,
            )
        )
    return data_sources


def execute_query(
    bk_biz_id: int,
    data_sources: list[DataSource],
    expression: str,
    functions: list[dict[str, Any]],
    start_time: int,
    end_time: int,
    enable_gray: bool,
) -> list[dict[str, Any]]:
    """
    执行查询。
    """
    LogSearchTimeSeriesDataSource.LOG_UNIFY_QUERY_WHITE_BIZ_LIST = [bk_biz_id] if enable_gray else []
    uq: UnifyQuery = UnifyQuery(
        bk_biz_id=bk_biz_id,
        data_sources=data_sources,
        expression=expression,
        functions=functions,
    )
    try:
        return uq.query_data(start_time=start_time, end_time=end_time)
    finally:
        LogSearchTimeSeriesDataSource.LOG_UNIFY_QUERY_WHITE_BIZ_LIST = []


def process_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    处理查询记录：过滤零值/空值，并标准化字段类型。

    处理规则：
        - 过滤 _result_ 为 0、0.0、None 的记录
        - _result_ 转成浮点数
        - 排除 a 字段
        - 其他字段统一转成字符串
    """
    processed_records: list[dict[str, Any]] = []

    for record in records:
        if not record.get("_result_"):
            continue

        normalized_record: dict[str, Any] = {"_result_": float(record["_result_"])}
        normalized_record.update({k: str(v) for k, v in record.items() if k not in {"_result_", "a"}})
        processed_records.append(normalized_record)

    return processed_records


def convert_records_to_series(records: list[dict[str, Any]]) -> dict[frozenset, list[list]]:
    """
    将查询记录转换为 series 格式
    """
    series_map: dict[frozenset, list[list]] = defaultdict(list)

    excluded_keys: set[str] = {"_result_", "_time_"}
    for record in records:
        # 提取维度字段（排除 _result_ 和 _time_）
        dimensions: frozenset = frozenset((k, v) for k, v in record.items() if k not in excluded_keys)

        # 构建 datapoint：[value, timestamp]
        series_map[dimensions].append([record["_result_"], record["_time_"]])

    return series_map


def has_empty_dimension_value(diff_keys: set[frozenset]) -> bool:
    """
    检查差集维度 key 中是否存在空值维度字段
    """
    for dimension_key in diff_keys:
        for _, value in dimension_key:
            if value == "":
                return True
    return False


def compare_query_records(uq_records: list[dict[str, Any]], ds_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    比较两种查询方式的结果。

    对比逻辑：
        1. 两种查询方式都无数据时，返回一致
        2. 对比两种查询方式的 dimensions key 差集，若不一致，判断是否因空值维度字段导致
        3. key 差集为空时，对比每个 key 下的 datapoints 是否一致
    """
    # 两种查询方式都无数据
    if not uq_records and not ds_records:
        return {"is_consistent": True, "uq_count": 0, "ds_count": 0, "diff_reason": ""}

    uq_count: int = len(uq_records)
    ds_count: int = len(ds_records)

    # 将记录转换为 series 格式
    uq_series: dict[frozenset, list[list]] = convert_records_to_series(uq_records)
    ds_series: dict[frozenset, list[list]] = convert_records_to_series(ds_records)

    uq_only_keys = uq_series.keys() - ds_series.keys()
    ds_only_keys = ds_series.keys() - uq_series.keys()

    # key 差集不为空，判断不一致原因
    if uq_only_keys or ds_only_keys:
        diff_reason = DiffReason.DIFF_DIMENSION_FIELD.value
        if has_empty_dimension_value(uq_only_keys) or has_empty_dimension_value(ds_only_keys):
            diff_reason = DiffReason.EMPTY_DIMENSION_FIELD.value
        return {"is_consistent": False, "uq_count": uq_count, "ds_count": ds_count, "diff_reason": diff_reason}

    # key 差集为空，对比每个 key 下的 datapoints
    for key in uq_series:
        uq_datapoints: list[list] = sorted(uq_series[key], key=lambda x: (x[1], x[0]))
        ds_datapoints: list[list] = sorted(ds_series[key], key=lambda x: (x[1], x[0]))
        if uq_datapoints != ds_datapoints:
            return {
                "is_consistent": False,
                "uq_count": uq_count,
                "ds_count": ds_count,
                "diff_reason": DiffReason.DIFF_DATAPOINTS.value,
            }

    return {"is_consistent": True, "uq_count": uq_count, "ds_count": ds_count, "diff_reason": ""}


def run_reconciliation(
    bk_biz_ids: list[int],
    start_time: int,
    end_time: int,
    output_csv_path: str,
    stdout: OutputWrapper,
    style: Style,
):
    """
    执行对账流程。

    遍历指定业务下的日志平台数据源策略，分别执行灰度和非灰度查询，比较结果一致性。
    """
    results: list[dict[str, Any]] = []
    start_time: int = start_time * 1000
    end_time: int = end_time * 1000
    base_url: str = settings.BK_MONITOR_HOST
    log_strategy_ids: list[int] = get_log_strategy_ids()

    for bk_biz_id in bk_biz_ids:
        stdout.write(f"正在处理业务：{bk_biz_id}")
        bk_biz_name: str = get_biz_name(bk_biz_id)

        # 获取该业务下日志平台数据源的已启用策略
        strategy_models: list[StrategyModel] = list(
            StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=log_strategy_ids, is_enabled=True)
        )
        if not strategy_models:
            stdout.write(f"  业务 {bk_biz_id} 下未找到日志平台数据源策略")
            continue

        stdout.write(f"  找到 {len(strategy_models)} 个策略，开始对账...")

        for strategy in Strategy.from_models(strategy_models):
            try:
                item: Item = strategy.items[0]
                query_config_dict: dict[str, Any] = item.query_configs[0].to_dict()

                # 构建查询参数
                query_params: dict[str, Any] = {
                    "bk_biz_id": bk_biz_id,
                    "data_sources": build_data_sources(strategy),
                    "expression": item.expression,
                    "functions": item.functions or [],
                    "start_time": start_time,
                    "end_time": end_time,
                }

                # 执行非灰度查询
                ds_records: list[dict[str, Any]] = process_records(execute_query(**query_params, enable_gray=False))

                # 执行灰度查询
                uq_records: list[dict[str, Any]] = process_records(execute_query(**query_params, enable_gray=True))

                # 比较结果
                compare_result: dict[str, Any] = compare_query_records(uq_records, ds_records)

                results.append(
                    {
                        "bk_biz_id": bk_biz_id,
                        "bk_biz_name": bk_biz_name,
                        "strategy_id": strategy.id,
                        "strategy_name": strategy.name,
                        "strategy_url": f"{base_url}?bizId={bk_biz_id}#/strategy-config/detail/{strategy.id}",
                        "data_type_label": query_config_dict.get("data_type_label") or "",
                        "is_consistent": int(compare_result["is_consistent"]),
                        "has_data": 1 if ds_records else 0,
                        "uq_count": compare_result["uq_count"],
                        "ds_count": compare_result["ds_count"],
                        "diff_reason": compare_result["diff_reason"],
                        "query_string": query_config_dict.get("query_string") or "",
                        "agg_dimension": json.dumps(query_config_dict.get("agg_dimension") or [], ensure_ascii=False),
                        "query_config": json.dumps(query_config_dict, ensure_ascii=False),
                    }
                )
            except Exception as e:
                stdout.write(style.ERROR(f"  处理策略 {strategy.id} 时出错：{e}"))

    # 写入 CSV 文件
    write_results_to_csv(output_csv_path, CSV_FIELDNAMES_RECONCILE, results)

    # 输出统计信息
    total_count: int = len(results)
    consistent_count: int = sum(1 for r in results if r["is_consistent"] == 1)
    stdout.write(style.SUCCESS(f"对账完成，结果已保存至：{output_csv_path}"))
    stdout.write(
        style.SUCCESS(f"总数：{total_count}，一致：{consistent_count}，不一致：{total_count - consistent_count}")
    )
