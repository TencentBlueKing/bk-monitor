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
