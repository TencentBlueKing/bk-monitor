"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Callable
from typing import Any
from collections import defaultdict

from bkmonitor.utils.common_utils import format_percent


def process_growth_rates(baseline: str, aliases: list[str], records: list[dict[str, Any]]):
    for record in records:
        for alias in aliases:
            growth_rate: float | None = None

            if record[baseline] == 0 and record[alias] == 0:
                # 两个数据都为 0 时，设定增长率为 0%
                growth_rate = 0
            elif not record[alias] and record[baseline]:
                # 往期无数据，同比正增长 100%
                growth_rate = 100
            elif record[alias] and not record[baseline]:
                # 当前无数据，同比负增长 100%
                growth_rate = -100
            elif record[alias] and record[baseline]:
                # 设置 4 位可读精度，非 0 展示 0.0001
                growth_rate = format_percent(
                    (record[baseline] - record[alias]) / record[alias] * 100,
                    precision=2,
                    sig_fig_cnt=1,
                    readable_precision=4,
                )

            record.setdefault("growth_rates", {})[alias] = growth_rate


def process_proportions(aliases: list[str], records: list[dict[str, Any]]):
    alias_total_map: dict[str, int] = defaultdict(int)
    for record in records:
        for alias in aliases:
            alias_total_map[alias] += record[alias] or 0

    for record in records:
        for alias in aliases:
            if alias_total_map[alias] == 0 or record[alias] is None:
                # 总数为 0 或者 数据为空 的情况下，直接置空
                record.setdefault("proportions", {})[alias] = None
                continue
            record.setdefault("proportions", {})[alias] = format_percent(
                (record[alias] / alias_total_map[alias]) * 100, precision=2, sig_fig_cnt=1, readable_precision=4
            )


def merge_records(
    group_fields: list[str],
    alias_records_map: dict[str, list[dict[str, Any]]],
    format_value: Callable[[Any], int | float],
) -> list[dict[str, Any]]:
    """按维度合并各别名的聚合结果，缺失值补 None。

    :param group_fields: 分组字段，time 使用已对齐的 _time_（毫秒）转换为秒
    :param alias_records_map: 各别名对应的聚合记录
    :param format_value: 数值格式化函数，保留调用方的精度和单位约定
    :return: 包含 dimensions 和各别名数值的记录列表
    """
    group_key_record_map: dict[tuple, dict[str, Any]] = {}
    # 取各时间窗口维度的并集，缺失窗口保留为 None。
    for alias, records in alias_records_map.items():
        for record in records:
            dimensions = {**record, "time": record.get("_time_", 0) // 1000}
            group_key = tuple((field, dimensions.get(field) or "") for field in group_fields)
            group_key_record_map.setdefault(group_key, {})[alias] = record["_result_"]

    merged_records: list[dict[str, Any]] = []
    for group_key, record in group_key_record_map.items():
        processed_record: dict[str, Any] = {"dimensions": dict(group_key)}
        for alias in alias_records_map:
            value = record.get(alias)
            processed_record[alias] = None if value is None else format_value(value)
        merged_records.append(processed_record)
    return merged_records
