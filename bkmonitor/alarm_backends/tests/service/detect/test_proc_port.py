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

from alarm_backends.service.detect.strategy.proc_port import ProcPort
from core.errors.alarm_backends.detect import InvalidDataPoint

DataPoint = namedtuple("DataPoint", ["value", "timestamp", "unit", "item", "dimensions"])

process_ok = DataPoint(
    1.0,
    100000000,
    "",
    "item",
    {
        "protocol": "tcp",
        "not_accurate_listen": "[]",
        "nonlisten": "[]",
        "bind_ip": "10.0.0.1",
        "bk_target_ip": "10.0.0.1",
        "display_name": "test",
        "listen": "[]",
    },
)

process_down = DataPoint(
    0,
    100000000,
    "",
    "item",
    {
        "protocol": "tcp",
        "not_accurate_listen": "[]",
        "nonlisten": "[]",
        "bind_ip": "10.0.0.1",
        "bk_target_ip": "10.0.0.1",
        "display_name": "test",
        "listen": "[]",
    },
)

port_down = DataPoint(
    1.0,
    100000000,
    "",
    "item",
    {
        "protocol": "tcp",
        "not_accurate_listen": "[]",
        "nonlisten": "[10011]",
        "bind_ip": "10.0.0.1",
        "bk_target_ip": "10.0.0.1",
        "display_name": "test",
        "listen": "[]",
    },
)

bind_ip_error = DataPoint(
    1.0,
    100000000,
    "",
    "item",
    {
        "protocol": "tcp",
        "not_accurate_listen": "[127.0.0.1:10011]",
        "nonlisten": "[]",
        "bind_ip": "10.0.0.1",
        "bk_target_ip": "10.0.0.1",
        "display_name": "test",
        "listen": "[]",
    },
)

port_ok_with_nulll = DataPoint(
    1.0,
    100000000,
    "",
    "item",
    {
        "protocol": "tcp",
        "not_accurate_listen": "null",
        "nonlisten": "null",
        "bind_ip": "10.0.0.1",
        "bk_target_ip": "10.0.0.1",
        "display_name": "test",
        "listen": "[]",
    },
)


class TestProcPort(object):
    def test_proc_ok(self):
        detect_engine = ProcPort(config={})
        assert len(detect_engine.detect(process_ok)) == 0

    def test_proc_down(self):
        detect_engine = ProcPort(config={})
        assert len(detect_engine.detect(process_down)) == 1

    def test_proc_port_down(self):
        detect_engine = ProcPort(config={})
        assert len(detect_engine.detect(port_down)) == 1

    def test_proc_port_bind_error(self):
        detect_engine = ProcPort(config={})
        assert len(detect_engine.detect(bind_ip_error)) == 1

    def test_port_ok_with_null(self):
        detect_engine = ProcPort(config={})
        assert len(detect_engine.detect(port_ok_with_nulll)) == 0

    def test_anomaly_message(self):
        from .mocked_data import datapoint_example as mocked_point

        # proc down
        mocked_point.value = 0
        mocked_point.dimensions = {
            "protocol": "tcp",
            "not_accurate_listen": "[]",
            "nonlisten": "[]",
            "bind_ip": "10.0.0.1",
            "bk_target_ip": "10.0.0.1",
            "display_name": "test",
            "listen": "[]",
        }
        detect_engine = ProcPort(config={})
        anomaly_result = detect_engine.detect_records(mocked_point, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "当前进程(test)不存在"

        # port down
        mocked_point.value = 1
        mocked_point.dimensions = {
            "protocol": "tcp",
            "not_accurate_listen": "[]",
            "nonlisten": "[8080, 8081, 9000]",
            "bind_ip": "10.0.0.1",
            "bk_target_ip": "10.0.0.1",
            "display_name": "test",
            "listen": "[]",
        }
        detect_engine = ProcPort(config={})
        anomaly_result = detect_engine.detect_records(mocked_point, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "当前进程(test)存在，端口([8080-8081,9000])不存在"

        # bind_error
        mocked_point.value = 1
        mocked_point.dimensions = {
            "protocol": "tcp",
            "not_accurate_listen": '["127.0.0.1:8080"]',
            "nonlisten": "[]",
            "bind_ip": "10.0.0.1",
            "bk_target_ip": "10.0.0.1",
            "display_name": "test",
            "listen": "[]",
        }
        detect_engine = ProcPort(config={})
        anomaly_result = detect_engine.detect_records(mocked_point, 1)
        assert len(anomaly_result) == 1
        assert (
            anomaly_result[0].anomaly_message == '当前进程(test)和监听端口(["127.0.0.1:8080"])存在，' "监听的IP与CMDB中配置的(10.0.0.1)不符"
        )

    def test_detect_with_invalid_datapoint(self):
        with pytest.raises(InvalidDataPoint):
            detect_engine = ProcPort(config={})
            detect_engine.detect((99, 100000000))
