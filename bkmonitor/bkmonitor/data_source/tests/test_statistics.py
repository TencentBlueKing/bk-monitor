"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.data_source.utils.statistics import process_growth_rates, process_proportions


def _make_records(records: list[dict]) -> list[dict]:
    """深拷贝一份入参，避免用例之间共享可变对象互相污染。"""
    return [dict(record) for record in records]


class TestProcessGrowthRates:
    """process_growth_rates：基于 baseline 计算各时间偏移维度（alias）的同比增长率。"""

    @pytest.mark.parametrize(
        ("baseline_val", "alias_val", "expected"),
        [
            # baseline 与 alias 均为 0 → 增长率为 0%
            (0, 0, 0),
            # 往期无数据（alias 为 0），当前有数据 → 同比正增长 100%
            (100, 0, 100),
            # 当前无数据（baseline 为 0），往期有数据 → 同比负增长 -100%
            (0, 100, -100),
        ],
    )
    def test_boundary_cases(self, baseline_val, alias_val, expected):
        records = _make_records([{"baseline": baseline_val, "alias": alias_val}])
        process_growth_rates("baseline", ["alias"], records)

        assert records[0]["growth_rates"]["alias"] == expected

    def test_normal_growth_rate(self):
        # baseline=120, alias=100 → (120-100)/100*100 = 20 的增长率
        records = _make_records([{"baseline": 120, "alias": 100}])
        process_growth_rates("baseline", ["alias"], records)

        assert records[0]["growth_rates"]["alias"] == 20

    def test_negative_value_computation(self):
        # baseline=80, alias=100 → (80-100)/100*100 = -20
        records = _make_records([{"baseline": 80, "alias": 100}])
        process_growth_rates("baseline", ["alias"], records)

        assert records[0]["growth_rates"]["alias"] == -20

    def test_multiple_aliases(self):
        # 同一 record 下多个时间偏移维度各自独立计算增长率
        records = _make_records([{"baseline": 200, "shift_1d": 100, "shift_7d": 0}])
        process_growth_rates("baseline", ["shift_1d", "shift_7d"], records)

        assert records[0]["growth_rates"]["shift_1d"] == 100
        assert records[0]["growth_rates"]["shift_7d"] == 100

    def test_multiple_records_independent(self):
        # 多 record 互不影响，各自独立写入 growth_rates
        records = _make_records(
            [
                {"baseline": 0, "alias": 0},
                {"baseline": 100, "alias": 50},
            ]
        )
        process_growth_rates("baseline", ["alias"], records)

        assert records[0]["growth_rates"]["alias"] == 0
        assert records[1]["growth_rates"]["alias"] == 100

    def test_does_not_overwrite_existing_dimensions(self):
        # 函数只新增 growth_rates 键，不应破坏 record 原有字段
        records = _make_records([{"baseline": 120, "alias": 100, "dimensions": {"a": "1"}}])
        process_growth_rates("baseline", ["alias"], records)

        assert records[0]["dimensions"] == {"a": "1"}
        assert records[0]["growth_rates"]["alias"] == 20


class TestProcessProportions:
    """process_proportions：基于各时间偏移维度（alias）的总量计算占比。"""

    def test_proportion_by_total(self):
        # alias=100, 总量 200 → 占比 50%
        records = _make_records([{"0s": 100}, {"0s": 100}])
        process_proportions(["0s"], records)

        assert records[0]["proportions"]["0s"] == 50
        assert records[1]["proportions"]["0s"] == 50

    def test_total_is_zero(self):
        # 某 alias 所有 record 总量为 0 → 占比置空（None）
        records = _make_records([{"0s": 0}, {"0s": 0}])
        process_proportions(["0s"], records)

        assert records[0]["proportions"]["0s"] is None
        assert records[1]["proportions"]["0s"] is None

    def test_alias_value_is_none(self):
        # record[alias] 显式为 None（对比窗口无该维度数据）→ 占比置空（None）
        records = _make_records([{"0s": None}, {"0s": 100}])
        process_proportions(["0s"], records)

        assert records[0]["proportions"]["0s"] is None
        assert records[1]["proportions"]["0s"] == 100

    def test_multiple_aliases_each_total(self):
        # 多个 alias 各自按自身总量计算占比，互不干扰
        records = _make_records([{"0s": 100, "1d": 50}, {"0s": 100, "1d": 150}])
        process_proportions(["0s", "1d"], records)

        # 0s 总量 200，1d 总量 200
        assert records[0]["proportions"]["0s"] == 50
        assert records[1]["proportions"]["0s"] == 50
        assert records[0]["proportions"]["1d"] == 25
        assert records[1]["proportions"]["1d"] == 75

    def test_uses_falsy_fallback_for_total(self):
        # record[alias] 为 0 时，在累加总量阶段按 0 处理（falsy fallback）
        records = _make_records([{"0s": 0}, {"0s": 100}])
        process_proportions(["0s"], records)

        # 总量 100；第一条显式为 0（非 None）应正常计算占比为 0
        assert records[0]["proportions"]["0s"] == 0
        assert records[1]["proportions"]["0s"] == 100

    def test_does_not_overwrite_existing_dimensions(self):
        records = _make_records([{"0s": 100, "dimensions": {"a": "1"}}, {"0s": 100}])
        process_proportions(["0s"], records)

        assert records[0]["dimensions"] == {"a": "1"}
        assert records[0]["proportions"]["0s"] == 50


class TestStatisticsIntegration:
    """模拟 _statistics 调用两个函数的端到端行为（records 已按维度合并）。"""

    def test_growth_and_proportion_together(self):
        # cal_type=count 场景：同时计算增长率与占比
        records = _make_records(
            [
                {"baseline": 100, "0s": 60},
                {"baseline": 100, "0s": 40},
            ]
        )
        process_growth_rates("baseline", ["0s"], records)
        process_proportions(["0s"], records)

        # (100-60)/60*100 = 66.66（format_percent 截断处理，保留 2 位）
        assert records[0]["growth_rates"]["0s"] == pytest.approx(66.66, abs=0.01)
        assert records[0]["proportions"]["0s"] == 60
        assert records[1]["proportions"]["0s"] == 40
