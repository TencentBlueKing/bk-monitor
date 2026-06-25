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
from rest_framework.exceptions import ValidationError

from bkmonitor.strategy.new_strategy import Strategy

validate = Strategy.Serializer.validate_new_series

NS = {"type": "NewSeries", "level": 1, "config": {"detect_range": 86400, "max_series": 100000}}
THRESHOLD = {"type": "Threshold", "level": 1, "config": [[{"method": "gte", "threshold": 1.0}]]}


def _attrs(algorithms, query_configs):
    return {"items": [{"algorithms": algorithms, "query_configs": query_configs}]}


def _qc(data_type_label="time_series", agg_interval=60, agg_dimension=None):
    return {
        "data_type_label": data_type_label,
        "agg_interval": agg_interval,
        "agg_dimension": agg_dimension or ["ip"],
    }


def test_valid_new_series_passes():
    # 合法：独占 level + 单 qc + 时序 + detect_range>=agg_interval
    validate(_attrs([NS], [_qc()]))


def test_non_new_series_skipped():
    # 不含 NewSeries 的策略不受影响
    validate(_attrs([THRESHOLD], [_qc(), _qc()]))


def test_reject_mixed_level():
    # NewSeries 与其它算法同 level -> 拒绝
    with pytest.raises(ValidationError):
        validate(_attrs([NS, dict(THRESHOLD, level=1)], [_qc()]))


def test_reject_multi_query_config():
    with pytest.raises(ValidationError):
        validate(_attrs([NS], [_qc(), _qc()]))


def test_reject_non_time_series():
    with pytest.raises(ValidationError):
        validate(_attrs([NS], [_qc(data_type_label="log")]))


def test_reject_detect_range_lt_agg_interval():
    ns = {"type": "NewSeries", "level": 1, "config": {"detect_range": 30, "max_series": 100000}}
    with pytest.raises(ValidationError):
        validate(_attrs([ns], [_qc(agg_interval=60)]))


def test_allow_multi_level_new_series():
    # 同一 item 两个 NewSeries 分属不同 level(各自独占)是允许的
    ns2 = {"type": "NewSeries", "level": 2, "config": {"detect_range": 86400}}
    validate(_attrs([NS, ns2], [_qc()]))


def test_reject_detect_range_zero():
    # degenerate: detect_range=0(且 agg_interval 缺失时也要拦)
    ns = {"type": "NewSeries", "level": 1, "config": {"detect_range": 0, "max_series": 100000}}
    with pytest.raises(ValidationError):
        validate(_attrs([ns], [{"data_type_label": "time_series", "agg_dimension": ["ip"]}]))


def test_reject_max_series_zero():
    ns = {"type": "NewSeries", "level": 1, "config": {"detect_range": 86400, "max_series": 0}}
    with pytest.raises(ValidationError):
        validate(_attrs([ns], [_qc()]))


def test_reject_effective_delay_zero():
    ns = {"type": "NewSeries", "level": 1, "config": {"detect_range": 86400, "effective_delay": 0}}
    with pytest.raises(ValidationError):
        validate(_attrs([ns], [_qc()]))


def test_reject_cross_item_same_level():
    # item A 的 NewSeries 与 item B 的其它算法落在同一 level(独占须 strategy 维) -> 拒绝
    # (否则 get_trigger_configs 会把该 level 的 trigger_count 强制为 1，静默波及 item B 的算法)
    item_a = {"algorithms": [NS], "query_configs": [_qc()]}
    item_b = {"algorithms": [dict(THRESHOLD, level=1)], "query_configs": [_qc()]}
    with pytest.raises(ValidationError):
        validate({"items": [item_a, item_b]})


def test_allow_cross_item_different_level():
    # item A 的 NewSeries(level=1) 与 item B 的其它算法(level=2) 不同 level -> 允许
    item_a = {"algorithms": [NS], "query_configs": [_qc()]}
    item_b = {"algorithms": [dict(THRESHOLD, level=2)], "query_configs": [_qc()]}
    validate({"items": [item_a, item_b]})


def test_effective_delay_always_equals_detect_range():
    # NewSeries 不设独立宽限期：effective_delay 一律归一化为 detect_range(缺省/更小/更大输入都被覆盖)。
    from bkmonitor.strategy.serializers import NewSeriesSerializer

    # 缺省 -> detect_range
    s = NewSeriesSerializer(data={"detect_range": 3600})
    s.is_valid(raise_exception=True)
    assert s.validated_data["effective_delay"] == 3600
    # 显式更小 -> detect_range
    s = NewSeriesSerializer(data={"detect_range": 86400, "effective_delay": 3600})
    s.is_valid(raise_exception=True)
    assert s.validated_data["effective_delay"] == 86400
    # 显式更大(扩展宽限不支持) -> detect_range
    s = NewSeriesSerializer(data={"detect_range": 3600, "effective_delay": 604800})
    s.is_valid(raise_exception=True)
    assert s.validated_data["effective_delay"] == 3600
