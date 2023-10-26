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

from collections import namedtuple

import pytest

from alarm_backends.service.detect.strategy.ping_unreachable import PingUnreachable
from core.errors.alarm_backends.detect import InvalidDataPoint

DataPoint = namedtuple("DataPoint", ["value", "timestamp", "unit", "item", "dimensions"])

datapoint0 = DataPoint(0, 100000000, "", "item", {"ip": "127.0.0.1"})
datapoint1 = DataPoint(1, 100000000, "", "item", {"ip": "127.0.0.1"})


class TestPingUnreachable(object):
    def test_ping_unreachable_none(self):
        detect_engine = PingUnreachable(config={})
        assert len(detect_engine.detect(datapoint0)) == 0

    def test_ping_unreachable_one(self):
        detect_engine = PingUnreachable(config={})
        assert len(detect_engine.detect(datapoint1)) == 1

    def test_anomaly_message(self):
        detect_engine = PingUnreachable(config={})
        anomaly_result = detect_engine.detect(datapoint1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "Ping不可达"

    def test_detect_with_invalid_datapoint(self):
        with pytest.raises(InvalidDataPoint):
            detect_engine = PingUnreachable(config={})
            detect_engine.detect((99, 100000000))
