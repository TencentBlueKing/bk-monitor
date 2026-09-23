"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

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
