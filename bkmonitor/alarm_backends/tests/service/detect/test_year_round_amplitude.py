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

from alarm_backends.service.detect.strategy.year_round_amplitude import (
    YearRoundAmplitude,
)
from alarm_backends.tests.service.detect import DataPoint
from core.errors.alarm_backends.detect import InvalidAlgorithmsConfig, InvalidDataPoint

datapoint200 = DataPoint(200, 100000000, "percent", "item")
datapoint100 = DataPoint(100, 100000000, "percent", "item")
datapoint99 = DataPoint(99, 100000000, "percent", "item")
datapoint_1 = DataPoint(-1, 100000000, "percent", "item")
datapoint1 = DataPoint(1, 100000000, "percent", "item")
datapoint0 = DataPoint(0, 100000000, "percent", "item")


class TestYearRoundAmplitude(object):
    def test_algorithm(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "year_round_amplitude.YearRoundAmplitude.history_point_fetcher",
            return_value=[(datapoint99, datapoint200), (datapoint1, datapoint200), (datapoint99, datapoint1)],
        ):
            algorithms_config = {"method": "gte", "days": 2, "ratio": 1, "shock": 1}
            detect_engine = YearRoundAmplitude(config=algorithms_config, unit="percent")
            assert len(detect_engine.detect(datapoint99)) == 1

    def test_anomaly_message(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "year_round_amplitude.YearRoundAmplitude.history_point_fetcher",
            return_value=[(datapoint99, datapoint200), (datapoint1, datapoint200), (datapoint99, datapoint1)],
        ):
            algorithms_config = {"method": "gte", "days": 2, "ratio": 0.9, "shock": 1}
            detect_engine = YearRoundAmplitude(config=algorithms_config, unit="percent")
            from .mocked_data import mock_datapoint_with_value

            _datapoint99 = mock_datapoint_with_value(99)
            detect_result = detect_engine.detect_records([_datapoint99], 1)
            assert len(detect_result) == 1
            anomaly_record = detect_result[0]
            assert anomaly_record.anomaly_message == ("avg(测试指标) - 前一时刻值200% " ">= 2天前的同一时刻差值98% * 0.9 + 1.0%, 当前值99%")

    def test_detect_with_invalid_datapoint(self):
        algorithms_config = {"method": "gte", "days": 2, "ratio": 1, "shock": 1}
        with pytest.raises(InvalidDataPoint):
            detect_engine = YearRoundAmplitude(config=algorithms_config, unit="percent")
            detect_engine.detect((99, 100000000))

    def test_invalid_config(self):
        algorithms_config = {"floor1": 99, "ceil2": 99}
        with pytest.raises(InvalidAlgorithmsConfig):
            detect_engine = YearRoundAmplitude(config=algorithms_config, unit="percent")
            detect_engine.detect((99, 100000000))
