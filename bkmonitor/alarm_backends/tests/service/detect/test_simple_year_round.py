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

from alarm_backends.service.detect.strategy.simple_year_round import SimpleYearRound
from alarm_backends.tests.service.detect import DataPoint
from core.errors.alarm_backends.detect import (
    InvalidAlgorithmsConfig,
    InvalidDataPoint,
    InvalidSimpleYearRoundConfig,
)

datapoint200 = DataPoint(200, 100000000, "%", "item")
datapoint100 = DataPoint(100, 100000000, "%", "item")
datapoint99 = DataPoint(99, 100000000, "%", "item")
datapoint_1 = DataPoint(-1, 100000000, "%", "item")
datapoint1 = DataPoint(1, 100000000, "%", "item")
datapoint0 = DataPoint(0, 100000000, "%", "item")


class TestSimpleYearRound(object):
    def test_detect_floor(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint200,
        ):
            # 下降超过50%（包含等于）
            algorithms_config = {"floor": 50, "ceil": None}
            detect_engine = SimpleYearRound(config=algorithms_config)
            assert len(detect_engine.detect(datapoint99)) == 1
            assert len(detect_engine.detect(datapoint100)) == 1

    def test_detect_floor_with_zero_history(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint0,
        ):
            algorithms_config = {"floor": 50, "ceil": None}
            detect_engine = SimpleYearRound(config=algorithms_config)
            assert len(detect_engine.detect(datapoint1)) == 0
            assert len(detect_engine.detect(datapoint0)) == 0
            # -1 环比 0 下降任意百分比 均成立
            assert len(detect_engine.detect(datapoint_1)) == 1

    def test_detect_ceil(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint99,
        ):
            # 上升超过100%（包含等于）
            algorithms_config = {"floor": None, "ceil": 100}
            detect_engine = SimpleYearRound(config=algorithms_config)
            assert len(detect_engine.detect(datapoint200)) == 1
            assert len(detect_engine.detect(datapoint99)) == 0

    def test_detect_ceil_with_zero_history(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint0,
        ):
            # 上升超过100%（包含等于）
            algorithms_config = {"floor": None, "ceil": 100}
            detect_engine = SimpleYearRound(config=algorithms_config)
            assert len(detect_engine.detect(datapoint1)) == 1
            assert len(detect_engine.detect(datapoint0)) == 0
            assert len(detect_engine.detect(datapoint_1)) == 0

    def test_anomaly_message(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint0,
        ):
            # 上升超过100%（包含等于）
            algorithms_config = {"floor": None, "ceil": 100}
            detect_engine = SimpleYearRound(config=algorithms_config)
            from .mocked_data import mock_datapoint_with_value

            _datapoint1 = mock_datapoint_with_value(1)
            detect_result = detect_engine.detect_records([_datapoint1], 1)
            assert len(detect_result) == 1
            anomaly_record = detect_result[0]
            assert anomaly_record.anomaly_message == "avg(测试指标)较上周同一时刻(0%)上升超过100.0%, 当前值1%"

    def test_detect_both_ceil_floor(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "simple_year_round.SimpleYearRound.history_point_fetcher",
            return_value=datapoint99,
        ):
            algorithms_config = {"floor": 50, "ceil": 100}
            detect_engine = SimpleYearRound(config=algorithms_config)
            assert len(detect_engine.detect(datapoint200)) == 1
            assert len(detect_engine.detect(datapoint0)) == 1
            assert len(detect_engine.detect(datapoint100)) == 0
            assert len(detect_engine.detect(datapoint99)) == 0

    def test_detect_with_invalid_datapoint(self):
        algorithms_config = {"floor": 99, "ceil": 99}
        with pytest.raises(InvalidDataPoint):
            detect_engine = SimpleYearRound(config=algorithms_config)
            detect_engine.detect((99, 100000000))

    def test_invalid_config(self):
        algorithms_config = {"floor1": 99, "ceil2": 99}
        with pytest.raises(InvalidAlgorithmsConfig):
            detect_engine = SimpleYearRound(config=algorithms_config)
            detect_engine.detect((99, 100000000))

        algorithms_config = {"floor": None, "ceil": None}
        with pytest.raises(InvalidSimpleYearRoundConfig):
            detect_engine = SimpleYearRound(config=algorithms_config)
            detect_engine.detect((99, 100000000))

    def test_unit(self):
        pass
