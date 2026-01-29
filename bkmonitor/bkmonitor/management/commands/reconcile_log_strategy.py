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

使用方法::

    # 模式 1：统计日志类策略数量
    python manage.py reconcile_log_strategy --mode=stat --biz-ids 1 2 3

    # 模式 2：查询对账（默认模式）
    python manage.py reconcile_log_strategy --mode=reconcile --biz-ids 1 2 3

    # 指定查询时间范围（秒级时间戳），默认取 (now - 30m, now)
    python manage.py reconcile_log_strategy --biz-ids 1 2 3 --start-time=1706169600 --end-time=1706171400

    # 指定输出文件路径
    python manage.py reconcile_log_strategy --biz-ids 1 2 3 --output=/tmp/reconciliation_result.csv
"""

import csv
import json
import math
import time
from argparse import ArgumentParser
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
    "query_string",
    "agg_dimension",
    "query_config",
]

# CSV 输出字段名（日志类策略统计模式）
CSV_FIELDNAMES_STAT: list[str] = [
    "bk_biz_id",
    "bk_biz_name",
    "strategy_count",
]


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
            help="运行模式：stat（统计日志类策略数量）或 reconcile（查询对账，默认）",
        )
        parser.add_argument(
            "--biz-ids",
            nargs="+",
            type=int,
            required=True,
            help="需要处理的业务 ID 列表，例如：--biz-ids 1 2 3",
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
        bk_biz_ids: list[int] = options["biz_ids"]
        mode: str = options["mode"]
        output_path: str = str(options["output"])

        # 处理时间参数
        now_ts: int = int(time.time())
        end_time_ts: int = options["end_time"] if options["end_time"] else now_ts
        start_time_ts: int = options["start_time"] if options["start_time"] else (now_ts - 30 * 60)

        self.stdout.write(self.style.SUCCESS(f"运行模式：{mode}，业务列表：{bk_biz_ids}"))

        if mode == "stat":
            run_stat_mode(
                bk_biz_ids=bk_biz_ids,
                output_csv_path=output_path,
                stdout=self.stdout,
                style=self.style,
            )
        else:
            self.stdout.write(f"查询时间范围：{start_time_ts} ~ {end_time_ts}")
            run_reconciliation(
                bk_biz_ids=bk_biz_ids,
                start_time_ts=start_time_ts,
                end_time_ts=end_time_ts,
                output_csv_path=output_path,
                stdout=self.stdout,
                style=self.style,
            )

        self.stdout.write(self.style.SUCCESS("执行完成！"))


def get_biz_name(bk_biz_id: int) -> str:
    """获取业务名"""
    business: Business | None = BusinessManager.get(bk_biz_id)
    return business.bk_biz_name if business else str(bk_biz_id)


def get_biz_strategies(bk_biz_id: int) -> list[StrategyModel]:
    """
    获取业务下日志平台数据源的策略模型列表。

    :param bk_biz_id: 业务 ID
    :return: 策略模型列表
    """
    strategy_ids: list[int] = list(
        QueryConfigModel.objects.filter(data_source_label=DataSourceLabel.BK_LOG_SEARCH)
        .values_list("strategy_id", flat=True)
        .distinct()
    )
    return list(StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=strategy_ids, is_enabled=True))


def run_stat_mode(bk_biz_ids: list[int], output_csv_path: str, stdout: OutputWrapper, style: Style):
    """
    统计模式：统计各业务下日志类策略数量。
    """
    results: list[dict[str, Any]] = []

    for bk_biz_id in bk_biz_ids:
        bk_biz_name: str = get_biz_name(bk_biz_id)
        strategy_count: int = len(get_biz_strategies(bk_biz_id))

        results.append(
            {
                "bk_biz_id": bk_biz_id,
                "bk_biz_name": bk_biz_name,
                "strategy_count": strategy_count,
            }
        )
        stdout.write(f"业务 {bk_biz_id}（{bk_biz_name}）：{strategy_count} 个日志类策略")

    # 写入 CSV 文件
    with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer: csv.DictWriter[str] = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES_STAT)
        writer.writeheader()
        writer.writerows(results)

    stdout.write(style.SUCCESS(f"统计结果已保存至：{output_csv_path}"))


def build_data_sources(strategy: Strategy) -> list[DataSource]:
    """
    根据策略构建数据源列表。
    """
    item: Item = strategy.items[0]
    data_sources: list[DataSource] = []
    for query_config in item.query_configs:
        query_config_dict = query_config.to_dict()
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
        normalized_record: dict[str, Any] = {}
        for key, value in record.items():
            if key == "a":
                continue
            normalized_record[key] = float(value) if key == "_result_" else str(value)
        processed_records.append(normalized_record)
    return processed_records


def build_record_key(record: dict[str, Any], fields: list[str]) -> str:
    """使用指定字段集合构建记录的唯一键。"""
    return "|".join(f"{k}={record[k]}" for k in fields)


def compare_query_records(uq_records: list[dict[str, Any]], ds_records: list[dict[str, Any]]) -> dict[str, Any]:
    """比较两种查询方式的结果，使用两边记录的共同字段集合来构建唯一键。"""
    # 两种查询方式都无数据
    if not uq_records and not ds_records:
        return {"is_consistent": True, "uq_count": 0, "ds_count": 0}

    # 计算共同字段集合（除 _result_），构建唯一键，用于解决两种查询方式针对维度字段为空的返回处理不一致的问题
    uq_fields: set[str] = set(uq_records[0].keys()) if uq_records else set()
    ds_fields: set[str] = set(ds_records[0].keys()) if ds_records else set()
    common_fields: list[str] = sorted(uq_fields & ds_fields - {"_result_"})

    # 构建记录映射：key -> _result_ 值
    uq_map: dict[str, float] = {build_record_key(r, common_fields): r["_result_"] for r in uq_records}
    ds_map: dict[str, float] = {build_record_key(r, common_fields): r["_result_"] for r in ds_records}

    # 判断是否一致：键集合相同且所有值都相等
    keys_match: bool = uq_map.keys() == ds_map.keys()
    values_match: bool = all(math.isclose(uq_map[k], ds_map[k]) for k in uq_map) if keys_match else False
    is_consistent: bool = keys_match and values_match

    return {"is_consistent": is_consistent, "uq_count": len(uq_records), "ds_count": len(ds_records)}


def run_reconciliation(
    bk_biz_ids: list[int],
    start_time_ts: int,
    end_time_ts: int,
    output_csv_path: str,
    stdout: OutputWrapper,
    style: Style,
):
    """
    执行对账流程。

    遍历指定业务下的日志平台数据源策略，分别执行灰度和非灰度查询，比较结果一致性。
    """
    results: list[dict[str, Any]] = []
    # 转换为毫秒时间戳
    start_ts: int = start_time_ts * 1000
    end_ts: int = end_time_ts * 1000
    base_url: str = settings.BK_MONITOR_HOST

    for bk_biz_id in bk_biz_ids:
        stdout.write(f"正在处理业务：{bk_biz_id}")
        bk_biz_name: str = get_biz_name(bk_biz_id)

        # 获取该业务下日志平台数据源的策略
        strategy_models: list[StrategyModel] = get_biz_strategies(bk_biz_id)
        if not strategy_models:
            stdout.write(f"  业务 {bk_biz_id} 下未找到日志平台数据源策略")
            continue

        stdout.write(f"  找到 {len(strategy_models)} 个策略，开始对账...")

        for strategy in Strategy.from_models(strategy_models):
            try:
                item: Item = strategy.items[0]
                query_config_dict: dict[str, Any] = item.query_configs[0].to_dict()
                data_type_label: str = query_config_dict.get("data_type_label", "")

                # 构建查询参数
                query_params: dict[str, Any] = {
                    "bk_biz_id": bk_biz_id,
                    "data_sources": build_data_sources(strategy),
                    "expression": item.expression,
                    "functions": item.functions,
                    "start_time": start_ts,
                    "end_time": end_ts,
                }

                # 执行非灰度查询
                ds_records_raw: list[dict[str, Any]] = execute_query(**query_params, enable_gray=False)
                ds_records: list[dict[str, Any]] = process_records(ds_records_raw)
                has_data: bool = bool(ds_records)

                # 执行灰度查询
                uq_records_raw: list[dict[str, Any]] = execute_query(**query_params, enable_gray=True)
                uq_records: list[dict[str, Any]] = process_records(uq_records_raw)

                # 比较结果
                compare_result: dict[str, Any] = compare_query_records(uq_records, ds_records)
                is_consistent: bool = compare_result["is_consistent"]

                results.append(
                    {
                        "bk_biz_id": bk_biz_id,
                        "bk_biz_name": bk_biz_name,
                        "strategy_id": strategy.id,
                        "strategy_name": strategy.name,
                        "strategy_url": f"{base_url}?bizId={bk_biz_id}#/strategy-config/detail/{strategy.id}",
                        "data_type_label": data_type_label,
                        "is_consistent": 1 if is_consistent else 0,
                        "has_data": 1 if has_data else 0,
                        "uq_count": compare_result["uq_count"],
                        "ds_count": compare_result["ds_count"],
                        "query_string": query_config_dict.get("query_string") or "",
                        "agg_dimension": json.dumps(query_config_dict.get("agg_dimension") or [], ensure_ascii=False),
                        "query_config": json.dumps(query_config_dict, ensure_ascii=False),
                    }
                )
            except Exception as e:
                stdout.write(style.ERROR(f"  处理策略 {strategy.id} 时出错：{e}"))

    # 写入 CSV 文件
    with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer: csv.DictWriter[str] = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES_RECONCILE)
        writer.writeheader()
        writer.writerows(results)

    # 输出统计信息
    total_count: int = len(results)
    consistent_count: int = sum(1 for r in results if r["is_consistent"] == 1)
    stdout.write(style.SUCCESS(f"对账完成，结果已保存至：{output_csv_path}"))
    stdout.write(
        style.SUCCESS(f"总数：{total_count}，一致：{consistent_count}，不一致：{total_count - consistent_count}")
    )
