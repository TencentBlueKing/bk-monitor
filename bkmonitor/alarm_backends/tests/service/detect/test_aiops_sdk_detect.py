# -*- coding: utf-8 -*-
import copy
from unittest import TestCase

import mock
import pytest

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.intelligent_detect import IntelligentDetect
from alarm_backends.tests.service.detect.mocked_data import mocked_item
from bkmonitor.models import CacheNode


@pytest.mark.django_db
class TestAIOpsSDKDetect(TestCase):
    def setUp(self):
        # 重置测试用例的Item防止ID超过用例上限
        CacheNode.refresh_from_settings()

        self.mocked_aiops_item = copy.deepcopy(mocked_item)
        self.mocked_aiops_item.query_configs[0]["intelligent_detect"] = {"use_sdk": True, "status": "ready"}
        self.datapoint99 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 99,
                "values": {"timestamp": 1569246480, "load5": 99},
                "dimensions": {"mocked": "127.0.0.1"},
                "time": 1569246480,
            },
            self.mocked_aiops_item,
        )

        self.anomaly_pre_detect = [
            {
                "__index__": self.datapoint99.record_id,
                "__id__": "",
                "__group_id__": "",
                "is_anomaly": 1,
                "timestamp": 1736404800000,
                "lower_bound": 9,
                "upper_bound": 10,
                "extra_info": "{\"anomaly_uncertainty\": 0.1, \"anomaly_alert\": 1.0, \"alert_msg\": \"上升异常\"}",
                "anomaly_alert": 0,
                "anomaly_score": 0.5,
                "value": 9.094444,
            }
        ]
        self.common_pre_detect = [
            {
                "__index__": self.datapoint99.record_id,
                "__id__": "",
                "__group_id__": "",
                "is_anomaly": 0,
                "timestamp": 1736404800000,
                "lower_bound": 9,
                "upper_bound": 10,
                "extra_info": "{\"anomaly_uncertainty\": 0.001, \"anomaly_alert\": 0.0, \"alert_msg\": \"正常\"}",
                "anomaly_alert": 0,
                "anomaly_score": 0.1,
                "value": 9.094444,
            }
        ]

    def test_detect_anomaly(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.intelligent_detect.IntelligentDetect.PREDICT_FUNC",
            return_value=self.anomaly_pre_detect,
        ):
            detect_engine = IntelligentDetect(
                config={
                    "args": {"$alert_down": "1", "$sensitivity": 5, "$alert_upward": "1"},
                    "plan_id": 1,
                    "visual_type": "score",
                }
            )
            anomaly_result = detect_engine.detect_records(self.datapoint99, 1)
            assert len(anomaly_result) == 1
            assert anomaly_result[0].anomaly_message == "avg(测试指标)智能模型检测到异常, 异常类型: 上升异常, 异常分值: 0.5, 当前值99%"

    def test_detect_not_anomaly(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.intelligent_detect.IntelligentDetect.PREDICT_FUNC",
            return_value=self.common_pre_detect,
        ):
            detect_engine = IntelligentDetect(
                config={
                    "args": {"$alert_down": "1", "$sensitivity": 5, "$alert_upward": "1"},
                    "plan_id": 1,
                    "visual_type": "score",
                }
            )
            anomaly_result = detect_engine.detect_records(self.datapoint99, 1)
            assert not anomaly_result

    def test_anomaly_with_previous_point(self):
        previous_datapoint = DataPoint(
            {
                "record_id": "772a08e0f85f169a7e099c18db3708ed",
                "value": 90,
                "values": {"is_anomaly": 0},
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246420,
            },
            self.mocked_aiops_item,
        )

        with mock.patch(
            "alarm_backends.service.detect.strategy.intelligent_detect.IntelligentDetect.history_point_fetcher",
            return_value=previous_datapoint,
        ):
            with mock.patch(
                "alarm_backends.service.detect.strategy.intelligent_detect.IntelligentDetect.PREDICT_FUNC",
                return_value=self.anomaly_pre_detect,
            ):
                detect_engine = IntelligentDetect(
                    config={
                        "args": {"$alert_down": "1", "$sensitivity": 5, "$alert_upward": "1"},
                        "plan_id": 1,
                        "visual_type": "score",
                    }
                )
                anomaly_result = detect_engine.detect_records(self.datapoint99, 1)
                assert len(anomaly_result) == 1
                assert anomaly_result[0].anomaly_message == (
                    "avg(测试指标)智能模型检测到异常, 异常类型: 上升异常, 异常分值: 0.5, 前一时刻值90%, 当前值99%"
                )
