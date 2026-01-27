"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

    # 对指定业务进行对账（多个业务 ID 用逗号分隔）
    python manage.py reconcile_log_ds_to_uq_records --biz_ids=2,3,5

    # 指定查询时间范围（分钟），默认 30 分钟
    python manage.py reconcile_log_ds_to_uq_records --biz_ids=2 --time_range=60

    # 指定输出文件路径
    python manage.py reconcile_log_ds_to_uq_records --biz_ids=2 --output=/tmp/reconciliation_result.csv
"""

import csv
import datetime
import json
import math
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, OutputWrapper
from django.core.management.color import Style

from alarm_backends.core.cache.cmdb import BusinessManager
from bkmonitor.data_source import load_data_source, UnifyQuery
from bkmonitor.data_source.data_source import DataSource, LogSearchTimeSeriesDataSource
from bkmonitor.models import StrategyModel, QueryConfigModel
from bkmonitor.strategy.new_strategy import Strategy
from constants.data_source import DataSourceLabel


# 查询时间范围递增列表（分钟），当未查询到数据时依次尝试更大的时间范围
DEFAULT_TIME_RANGES_MINUTES: list[int] = [30, 60, 180, 360, 720, 1440]

# 差异详情最大展示条数
MAX_DIFF_DISPLAY_COUNT: int = 10

# CSV 输出字段名
CSV_FIELDNAMES: list[str] = [
    "bk_biz_id",
    "bk_biz_name",
    "strategy_id",
    "strategy_name",
    "strategy_url",
    "data_type_label",
    "is_consistent",
    "has_data",
    "uq_record_count",
    "ds_record_count",
    "diff_detail",
    "query_string",
    "agg_dimension",
    "time_range_minutes",
    "query_config",
]


class Command(BaseCommand):
    """日志平台数据源 UnifyQuery 灰度切换对账命令"""

    help = "对账日志平台数据源切换 unify-query 前后的查询结果一致性"

    def add_arguments(self, parser) -> None:
        """添加命令行参数。"""
        parser.add_argument(
            "--biz_ids", type=str, required=True, help="需要对账的业务 ID 列表，多个 ID 用逗号分隔，例如：2,3,5"
        )
        parser.add_argument(
            "--time_range",
            type=int,
            default=30,
            help="初始查询时间范围（分钟），默认 30 分钟，如果无数据会自动扩大范围",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="reconciliation_result.csv",
            help="输出 CSV 文件路径，默认为当前目录下的 reconciliation_result.csv",
        )

    def handle(self, *args, **options) -> None:
        """命令执行入口"""
        biz_ids_str: str = options["biz_ids"]
        try:
            bk_biz_ids: list[int] = [int(biz_id.strip()) for biz_id in biz_ids_str.split(",")]
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f"业务 ID 格式错误：{e}"))
            return

        time_range: int = options["time_range"]
        output_path: str = options["output"]

        self.stdout.write(self.style.SUCCESS(f"开始对账，业务列表：{bk_biz_ids}"))
        self.stdout.write(f"初始时间范围：{time_range} 分钟")
        self.stdout.write(f"输出文件：{output_path}")

        run_reconciliation(
            bk_biz_ids=bk_biz_ids,
            initial_time_range=time_range,
            end_time=datetime.datetime.now(),
            output_csv_path=output_path,
            stdout=self.stdout,
            style=self.style,
        )
        self.stdout.write(self.style.SUCCESS("对账完成！"))


def build_data_sources(strategy: Strategy) -> list[DataSource]:
    """
    根据策略构建数据源列表。
    """
    item = strategy.items[0]
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
    try:
        uq = UnifyQuery(
            bk_biz_id=bk_biz_id,
            data_sources=data_sources,
            expression=expression,
            functions=functions,
        )
        return uq.query_data(start_time=start_time, end_time=end_time)
    finally:
        LogSearchTimeSeriesDataSource.LOG_UNIFY_QUERY_WHITE_BIZ_LIST = []


def filter_zero_values(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    过滤零值和空值记录。

    unify-query 会对缺失的时间点补 0，而 ES 查询返回 null，比较时需忽略这些值。

    :param records: 查询结果记录列表
    :return: 过滤后的记录列表
    """
    return [r for r in records if r.get("_result_") not in (0, 0.0, None)]


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    标准化记录字段类型。

    处理 unify-query 和 datasource 之间的类型差异：
        gseIndex/cloudId: unify-query 返回字符串，datasource 返回整数，统一转字符串
        _result_: unify-query 返回整数，datasource 返回浮点数，统一转浮点数

    :param record: 原始记录
    :return: 标准化后的记录
    """
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        if key in ("gseIndex", "cloudId"):
            normalized[key] = str(value) if value is not None else None
        elif key == "_result_":
            normalized[key] = float(value) if value is not None else None
        elif key not in ("serverIp", "a"):
            normalized[key] = value
    return normalized


def build_record_key(record: dict[str, Any]) -> str:
    """
    构建记录的唯一键。

    使用 _time_ 和所有维度字段组合作为唯一键，用于匹配两边的记录。
    """
    key_parts: list[str] = [f"_time_={record.get('_time_')}"]
    for field, value in sorted(record.items()):
        if field not in ("_time_", "_result_"):
            key_parts.append(f"{field}={value}")
    return "|".join(key_parts)


def compare_query_results(uq_records: list[dict[str, Any]], ds_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    比较两种查询方式的结果。

    逐条比对记录，处理 unify-query 补零和字段类型不一致的差异。

    :param uq_records: unify-query 查询返回的记录
    :param ds_records: 原始数据源查询返回的记录
    :return: 比较结果字典，包含 is_consistent、uq_record_count、ds_record_count、diff_detail
    """
    # 过滤零值并标准化记录字段类型
    uq_filtered = [normalize_record(r) for r in filter_zero_values(uq_records)]
    ds_filtered = [normalize_record(r) for r in filter_zero_values(ds_records)]

    # 两种查询方式都无数据
    if not uq_filtered and not ds_filtered:
        return {
            "is_consistent": True,
            "uq_record_count": 0,
            "ds_record_count": 0,
            "diff_detail": "两种查询结果均为空",
        }

    # 构建记录映射
    uq_map: dict[str, dict[str, Any]] = {build_record_key(r): r for r in uq_filtered}
    ds_map: dict[str, dict[str, Any]] = {build_record_key(r): r for r in ds_filtered}
    uq_keys: set[str] = set(uq_map.keys())
    ds_keys: set[str] = set(ds_map.keys())

    # 计算差异集合
    uq_only_keys: set[str] = uq_keys - ds_keys
    ds_only_keys: set[str] = ds_keys - uq_keys
    common_keys: set[str] = uq_keys & ds_keys

    diff_details: list[str] = []
    # unify-query 独有的记录
    if uq_only_keys:
        diff_details.append(f"unify_query 独有 {len(uq_only_keys)} 条记录")
        for i, key in enumerate(uq_only_keys):
            if i >= MAX_DIFF_DISPLAY_COUNT:
                diff_details.append(f"  ...（共 {len(uq_only_keys)} 条）")
                break
            record = uq_map[key]
            diff_details.append(f"  uq_only: time={record.get('_time_')}, result={record.get('_result_')}")
    # datasource 独有的记录
    if ds_only_keys:
        diff_details.append(f"datasource 独有 {len(ds_only_keys)} 条记录")
        for i, key in enumerate(ds_only_keys):
            if i >= MAX_DIFF_DISPLAY_COUNT:
                diff_details.append(f"  ...（共 {len(ds_only_keys)} 条）")
                break
            record = ds_map[key]
            diff_details.append(f"  ds_only: time={record.get('_time_')}, result={record.get('_result_')}")
    # 相同键但值不同的记录
    value_diff_count: int = 0
    for key in common_keys:
        uq_val = uq_map[key].get("_result_")
        ds_val = ds_map[key].get("_result_")
        if uq_val is not None and ds_val is not None and not math.isclose(uq_val, ds_val):
            value_diff_count += 1
            if value_diff_count <= MAX_DIFF_DISPLAY_COUNT:
                diff_details.append(f"  值不同: time={uq_map[key].get('_time_')}, uq={uq_val:.2f}, ds={ds_val:.2f}")
    if value_diff_count > MAX_DIFF_DISPLAY_COUNT:
        diff_details.append(f"  ...（共 {value_diff_count} 处值差异）")

    # 判断是否一致
    has_diff: bool = bool(uq_only_keys or ds_only_keys or value_diff_count)
    return {
        "is_consistent": not has_diff,
        "uq_record_count": len(uq_filtered),
        "ds_record_count": len(ds_filtered),
        "diff_detail": "\n".join(diff_details) if has_diff else f"结果一致，共 {len(common_keys)} 条记录",
    }


def run_reconciliation(
    bk_biz_ids: list[int],
    initial_time_range: int,
    end_time: datetime.datetime,
    output_csv_path: str,
    stdout: OutputWrapper,
    style: Style,
) -> None:
    """
    执行对账流程。

    遍历指定业务下的日志平台数据源策略，分别执行灰度和非灰度查询，比较结果一致性。
    """
    results: list[dict[str, Any]] = []
    time_ranges = [initial_time_range] + [t for t in DEFAULT_TIME_RANGES_MINUTES if t > initial_time_range]
    end_ts: int = int(end_time.timestamp() * 1000)
    base_url: str = getattr(settings, "BK_MONITOR_HOST", "")

    for bk_biz_id in bk_biz_ids:
        stdout.write(f"正在处理业务：{bk_biz_id}")
        business = BusinessManager.get(bk_biz_id)
        bk_biz_name: str = business.bk_biz_name if business else str(bk_biz_id)

        # 获取该业务下日志平台数据源的策略
        strategy_ids = (
            QueryConfigModel.objects.filter(
                data_source_label=DataSourceLabel.BK_LOG_SEARCH,
            )
            .values_list("strategy_id", flat=True)
            .distinct()
        )
        strategy_models = list(StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=strategy_ids, is_enabled=True))
        if not strategy_models:
            stdout.write(f"  业务 {bk_biz_id} 下未找到日志平台数据源策略")
            continue

        for strategy in Strategy.from_models(strategy_models):
            stdout.write(f"  正在处理策略：{strategy.name}（ID：{strategy.id}）")
            try:
                item = strategy.items[0]
                query_config_dict: dict[str, Any] = item.query_configs[0].to_dict()
                data_type_label: str = query_config_dict.get("data_type_label", "")

                # 使用非灰度查询依次尝试不同的时间范围
                start_ts: int = end_ts
                ds_records: list[dict[str, Any]] = []
                has_data: bool = False
                actual_time_range: int = initial_time_range

                for time_range_minutes in time_ranges:
                    start_ts = int((end_time - datetime.timedelta(minutes=time_range_minutes)).timestamp() * 1000)
                    ds_records = execute_query(
                        bk_biz_id,
                        build_data_sources(strategy),
                        item.expression,
                        item.functions,
                        start_ts,
                        end_ts,
                        enable_gray=False,
                    )
                    filtered_records = filter_zero_values(ds_records)
                    if filtered_records:
                        stdout.write(f"    在 {time_range_minutes} 分钟内查询到 {len(filtered_records)} 条有效数据")
                        has_data = True
                        actual_time_range = time_range_minutes
                        break
                    stdout.write(f"    在 {time_range_minutes} 分钟内未查询到有效数据，尝试更大范围")

                if not has_data:
                    stdout.write("    所有时间范围均未查询到有效数据")
                    actual_time_range = time_ranges[-1] if time_ranges else initial_time_range

                # 使用相同时间范围执行灰度查询
                uq_records = execute_query(
                    bk_biz_id,
                    build_data_sources(strategy),
                    item.expression,
                    item.functions,
                    start_ts,
                    end_ts,
                    enable_gray=True,
                )

                # 比较结果
                compare_result = compare_query_results(uq_records, ds_records)
                is_consistent: bool = compare_result["is_consistent"]
                stdout.write(
                    f"    一致={is_consistent}, 有数据={has_data}, "
                    f"uq 记录数={compare_result['uq_record_count']}, ds 记录数={compare_result['ds_record_count']}"
                )

                results.append(
                    {
                        "bk_biz_id": bk_biz_id,
                        "bk_biz_name": bk_biz_name,
                        "strategy_id": strategy.id,
                        "strategy_name": strategy.name,
                        "strategy_url": f"{base_url}/?bizId={bk_biz_id}#/strategy-config/detail/{strategy.id}",
                        "data_type_label": data_type_label,
                        "is_consistent": "是" if is_consistent else "否",
                        "has_data": "是" if has_data else "否",
                        "uq_record_count": compare_result["uq_record_count"],
                        "ds_record_count": compare_result["ds_record_count"],
                        "diff_detail": compare_result["diff_detail"],
                        "query_string": query_config_dict.get("query_string") or "",
                        "agg_dimension": json.dumps(query_config_dict.get("agg_dimension") or [], ensure_ascii=False),
                        "time_range_minutes": actual_time_range,
                        "query_config": json.dumps(query_config_dict, ensure_ascii=False),
                    }
                )
            except Exception as e:
                stdout.write(style.ERROR(f"    处理策略 {strategy.id} 时出错：{e}"))

    # 写入 CSV 文件
    with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    # 输出统计信息
    total_count: int = len(results)
    consistent_count: int = sum(1 for r in results if r["is_consistent"] == "是")
    inconsistent_count: int = sum(1 for r in results if r["is_consistent"] == "否")
    stdout.write(style.SUCCESS(f"对账完成，结果已保存至：{output_csv_path}"))
    stdout.write(style.SUCCESS(f"处理的策略总数：{total_count}"))
    stdout.write(style.SUCCESS(f"一致：{consistent_count}，不一致：{inconsistent_count}"))
