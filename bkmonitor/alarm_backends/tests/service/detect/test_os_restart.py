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

import mock
import pytest

from alarm_backends.service.detect.strategy.os_restart import OsRestart
from core.errors.alarm_backends.detect import InvalidDataPoint

DataPoint = namedtuple("DataPoint", ["value", "timestamp", "unit", "item", "dimensions"])

datapoint200 = DataPoint(200, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint99 = DataPoint(99, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint30 = DataPoint(30, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint800 = DataPoint(800, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint700 = DataPoint(700, 100000000, "%", "item", {"ip": "127.0.0.1"})


class TestOsRestart(object):
    def test_os_restart_1(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint700, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_os_restart_2(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_os_restart_3(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint800, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint700)) == 0

    def test_os_restart_4(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint99, datapoint30, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 0

    def test_os_restart_5(self):
        # bugfix: 解决云机器买入后，10分钟内部署完agent，开始上报数据，引起的误告。
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, None, None],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 0

    def test_os_restart_6(self):
        # bugfix: 解决云机器买入后，10分钟内部署完agent，开始上报数据，引起的误告。
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, datapoint200, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_anomaly_message(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy." "os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint800, datapoint30, datapoint700],
        ):
            from .mocked_data import datapoint99

            detect_engine = OsRestart(config={})
            anomaly_result = detect_engine.detect_records(datapoint99, 1)
            assert len(anomaly_result) == 1
            assert anomaly_result[0].anomaly_message == "当前服务器在99秒前发生系统重启事件"

    def test_detect_with_invalid_datapoint(self):
        with pytest.raises(InvalidDataPoint):
            detect_engine = OsRestart(config={})
            detect_engine.detect((99, 100000000))
