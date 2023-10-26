# -*- coding: utf-8 -*-
import mock
import pytest
from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.intelligent_detect import IntelligentDetect
from alarm_backends.tests.service.detect.test_threshold import mocked_item

pytestmark = pytest.mark.django_db


class TestIntelligentDetect:
    def test_anomaly_message(self):
        datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"is_anomaly": 1},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            mocked_item,
        )

        detect_engine = IntelligentDetect(config={})
        anomaly_result = detect_engine.detect_records(datapoint99, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标)智能模型检测到异常, 当前值99%"

    def test_anomaly(self):
        datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"is_anomaly": 0},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            mocked_item,
        )

        detect_engine = IntelligentDetect(config={})
        anomaly_result = detect_engine.detect_records(datapoint99, 1)
        assert not anomaly_result

    def test_anomaly__score(self):
        datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"is_anomaly": 1, "extra_info": '{"anomaly_score": 0.53, "alert_msg": "突降"}'},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            mocked_item,
        )

        detect_engine = IntelligentDetect(config={})
        anomaly_result = detect_engine.detect_records(datapoint99, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标)智能模型检测到异常, 异常类型: 突降, 异常分值: 0.53, 当前值99%"

    def test_anomaly__alert_msg(self):
        datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"is_anomaly": 1, "extra_info": '{"alert_msg": "上升异常"}'},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            mocked_item,
        )

        detect_engine = IntelligentDetect(config={})
        anomaly_result = detect_engine.detect_records(datapoint99, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == "avg(测试指标)智能模型检测到异常, 异常类型: 上升异常, 当前值99%"

    def test_anomaly__alert_msg_previous_point(self):
        datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"is_anomaly": 1, "extra_info": '{"alert_msg": "上升异常"}'},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            mocked_item,
        )

        previous_datapoint = DataPoint(
            {
                "record_id": "772a08e0f85f169a7e099c18db3708ed",
                "value": 90,
                "values": {"is_anomaly": 0},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246420,
            },
            mocked_item,
        )

        with mock.patch(
            "alarm_backends.service.detect.strategy.intelligent_detect.IntelligentDetect.history_point_fetcher",
            return_value=previous_datapoint,
        ):
            detect_engine = IntelligentDetect(config={})
            anomaly_result = detect_engine.detect_records(datapoint99, 1)
            assert len(anomaly_result) == 1
            assert anomaly_result[0].anomaly_message == ("avg(测试指标)智能模型检测到异常, 异常类型: 上升异常, " "前一时刻值90%, 当前值99%")
