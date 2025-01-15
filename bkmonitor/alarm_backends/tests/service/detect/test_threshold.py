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
import pytest

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.threshold import Threshold
from alarm_backends.tests.service.detect.mocked_data import (
    Item,
    Strategy,
    datapoint6,
    datapoint50,
    datapoint99,
    item_config,
    mock_unify_query,
    mocked_data_source,
)
from core.errors.alarm_backends.detect import InvalidAlgorithmsConfig, InvalidDataPoint


class TestThreshold(object):
    def test_detect_gte(self):
        algorithms_config = [[{"threshold": 50.0, "method": "gte"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 1
        assert len(detect_engine.detect(datapoint50)) == 1
        assert len(detect_engine.detect(datapoint6)) == 0

    def test_detect_gt(self):
        algorithms_config = [[{"threshold": 50.0, "method": "gt"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 1
        assert len(detect_engine.detect(datapoint50)) == 0
        assert len(detect_engine.detect(datapoint6)) == 0

    def test_detect_eq(self):
        algorithms_config = [[{"threshold": 50.0, "method": "eq"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 0
        assert len(detect_engine.detect(datapoint50)) == 1
        assert len(detect_engine.detect(datapoint6)) == 0

    def test_detect_neq(self):
        algorithms_config = [[{"threshold": 50.0, "method": "neq"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 1
        assert len(detect_engine.detect(datapoint50)) == 0
        assert len(detect_engine.detect(datapoint6)) == 1

    def test_detect_lt(self):
        algorithms_config = [[{"threshold": 50.0, "method": "lt"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 0
        assert len(detect_engine.detect(datapoint50)) == 0
        assert len(detect_engine.detect(datapoint6)) == 1

    def test_detect_lte(self):
        algorithms_config = [[{"threshold": 50.0, "method": "lte"}]]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 0
        assert len(detect_engine.detect(datapoint50)) == 1
        assert len(detect_engine.detect(datapoint6)) == 1

    def test_detect_multi(self):
        algorithms_config = [
            [{"threshold": 6, "method": "gt"}, {"threshold": 99, "method": "lte"}, {"threshold": 50, "method": "neq"}],
            [{"threshold": 6, "method": "eq"}],
        ]
        detect_engine = Threshold(config=algorithms_config)
        assert len(detect_engine.detect(datapoint99)) == 3
        assert len(detect_engine.detect(datapoint50)) == 0
        assert len(detect_engine.detect(datapoint6)) == 1

    def test_anomaly_message(self):
        algorithms_config = [
            [{"threshold": 6, "method": "gt"}, {"threshold": 99, "method": "lte"}, {"threshold": 50, "method": "neq"}],
            [{"threshold": 6, "method": "eq"}],
        ]
        detect_engine = Threshold(config=algorithms_config)
        level = 1
        anomaly_result = detect_engine.detect_records([datapoint99], level)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标) > 6.0%且 <= 99.0%且 != 50.0%, 当前值99%"

        anomaly_result = detect_engine.detect_records([datapoint6], level)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标) = 6.0%, 当前值6%"

    def test_detect_unknown_method(self):
        algorithms_config = [[{"threshold": 50.0, "method": "unknown"}]]
        with pytest.raises(
            InvalidAlgorithmsConfig,
        ):
            detect_engine = Threshold(config=algorithms_config)
            detect_engine.detect(datapoint99)

    def test_detect_with_empty_config(self):
        with pytest.raises(InvalidAlgorithmsConfig):
            detect_engine = Threshold(config=[])
            detect_engine.detect(datapoint99)

    def test_detect_with_invalid_datapoint(self):
        algorithms_config = [[{"threshold": 99, "method": "lte"}]]
        with pytest.raises(InvalidDataPoint):
            detect_engine = Threshold(config=algorithms_config)
            detect_engine.detect((99, 10000))

    def test_unit(self):
        algorithms_config = [[{"threshold": 1, "method": "gte"}]]
        detect_engine = Threshold(config=algorithms_config, unit="Ki")
        datapoint = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 1023,
                "values": {"timestamp": 1569246480, "load5": 1023},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            Item(
                1,
                Strategy(1, "os"),
                "bytes",
                [mocked_data_source],
                ["system.cpu_summary"],
                item_config["query_configs"],
                mock_unify_query,
            ),
        )

        assert len(detect_engine.detect(datapoint)) == 0

        datapoint._raw_input["value"] = 1025
        datapoint.value = 1025
        anomaly_records = detect_engine.detect(datapoint)
        assert len(anomaly_records) == 1

        anomaly_records = detect_engine.detect_records([datapoint], 1)
        assert anomaly_records[0].anomaly_message == "avg(测试指标) >= 1.0KiB, 当前值1.000977KiB"
