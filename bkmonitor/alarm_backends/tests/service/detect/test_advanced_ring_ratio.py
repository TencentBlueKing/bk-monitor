# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import mock
import pytest

from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.detect.strategy.advanced_ring_ratio import AdvancedRingRatio
from alarm_backends.tests.service.detect import DataPoint
from alarm_backends.tests.service.detect.test_threshold import mock_datapoint_with_value
from bkmonitor.models import CacheNode
from core.errors.alarm_backends.detect import (
    InvalidAdvancedRingRatioConfig,
    InvalidAlgorithmsConfig,
    InvalidDataPoint,
)

pytestmark = pytest.mark.django_db


datapoint200 = DataPoint(200, 100000000, "percent", "item")
datapoint101 = DataPoint(101, 100000000, "percent", "item")
datapoint100 = DataPoint(100, 100000000, "percent", "item")
datapoint99 = DataPoint(99, 100000000, "percent", "item")
datapoint_1 = DataPoint(-1, 100000000, "percent", "item")
datapoint1 = DataPoint(1, 100000000, "percent", "item")
datapoint0 = DataPoint(0, 100000000, "percent", "item")


class TestAdvancedRingRatio(object):
    def test_detect_floor(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "advanced_ring_ratio.AdvancedRingRatio.history_point_fetcher",
            return_value=[datapoint200, datapoint100, datapoint100],
        ):
            # 环比前3个周期均值（200， 100， 100）下降超过50%（包含等于）
            algorithms_config = {"floor": 50, "ceil": None, "floor_interval": 3, "ceil_interval": None}
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            assert detect_engine.get_history_offsets(mock_datapoint_with_value(100).item) == [(60, 180)]
            assert len(detect_engine.detect(datapoint100)) == 0
            assert len(detect_engine.detect(datapoint1)) == 1

    def test_detect_floor_with_zero_history(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "advanced_ring_ratio.AdvancedRingRatio.history_point_fetcher",
            return_value=[datapoint0] * 3,
        ):
            algorithms_config = {"floor": 50, "ceil": None, "floor_interval": 3, "ceil_interval": None}
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            assert len(detect_engine.detect(datapoint1)) == 0
            assert len(detect_engine.detect(datapoint0)) == 0
            # -1 环比 0 下降任意百分比 均成立
            assert len(detect_engine.detect(datapoint_1)) == 1

    def test_detect_ceil(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "advanced_ring_ratio.AdvancedRingRatio.history_point_fetcher",
            return_value=[datapoint99, datapoint100, datapoint101],
        ):
            # 上升超过100%（包含等于）
            algorithms_config = {"floor": None, "ceil": 100, "ceil_interval": 3, "floor_interval": None}
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            assert len(detect_engine.detect(datapoint200)) == 1
            assert len(detect_engine.detect(datapoint100)) == 0

    def test_detect_ceil_with_zero_history(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "advanced_ring_ratio.AdvancedRingRatio.history_point_fetcher",
            return_value=[datapoint0] * 3,
        ):
            # 上升超过100%（包含等于）
            algorithms_config = {"floor": None, "ceil": 100, "ceil_interval": 3, "floor_interval": None}
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            assert len(detect_engine.detect(datapoint1)) == 1
            assert len(detect_engine.detect(datapoint0)) == 0
            assert len(detect_engine.detect(datapoint_1)) == 0

    def test_detect_both_ceil_floor(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "advanced_ring_ratio.AdvancedRingRatio.history_point_fetcher",
            return_value=[datapoint99, datapoint1, datapoint101],
        ):
            algorithms_config = {"floor": 101, "ceil": 100, "ceil_interval": 3, "floor_interval": 3}
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            assert len(detect_engine.detect(datapoint200)) == 1
            assert len(detect_engine.detect(datapoint0)) == 0
            assert len(detect_engine.detect(datapoint100)) == 0
            assert len(detect_engine.detect(datapoint_1)) == 1

    def test_anomaly_message(self):
        from .test_threshold import mock_datapoint_with_value

        get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()

        algorithms_config = {"floor": 100, "ceil": 100, "ceil_interval": 3, "floor_interval": 3, "fetch_type": "last"}

        _datapoint500 = mock_datapoint_with_value(500)
        _datapoint_1 = mock_datapoint_with_value(-1)
        detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
        detect_engine.query_history_points([_datapoint500])
        anomaly_result = detect_engine.detect_records(_datapoint500, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标)较前3个时间点的瞬间值(101%)上升超过100.0%, 当前值500%"
        anomaly_result = detect_engine.detect_records(_datapoint_1, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标)较前3个时间点的瞬间值(101%)下降超过100.0%, 当前值-1%"

    def test_detect_with_invalid_datapoint(self):
        algorithms_config = {"floor": 101, "ceil": 100, "ceil_interval": 3, "floor_interval": 3}
        with pytest.raises(InvalidDataPoint):
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            detect_engine.detect((99, 100000000))

    def test_invalid_config(self):
        # interval 必须是整形
        algorithms_config = {"floor": 99, "ceil": 99, "ceil_interval": 3.1, "floor_interval": 3.5}
        with pytest.raises(InvalidAlgorithmsConfig):
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            detect_engine.detect((99, 100000000))

        algorithms_config = {"floor": None, "ceil": None, "ceil_interval": 3, "floor_interval": 3}
        with pytest.raises(InvalidAdvancedRingRatioConfig):
            detect_engine = AdvancedRingRatio(config=algorithms_config, unit="percent")
            detect_engine.detect((99, 100000000))
