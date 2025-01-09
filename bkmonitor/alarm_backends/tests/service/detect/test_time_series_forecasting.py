# -*- coding: utf-8 -*-
import copy
import json
from unittest import TestCase

import pytest

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.time_series_forecasting import (
    TimeSeriesForecasting,
)
from alarm_backends.tests.service.detect.mocked_data import mocked_item
from bkmonitor.models import CacheNode


@pytest.mark.django_db
class TestTimeSeriesForecasting(TestCase):
    def setUp(self):
        # 重置测试用例的Item防止ID超过用例上限
        CacheNode.refresh_from_settings()

        self.mocked_aiops_item = copy.deepcopy(mocked_item)
        self.mocked_aiops_item.query_configs[0]["intelligent_detect"] = {"use_sdk": False, "status": "running"}

        self.datapoint50 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 50,
                "values": {
                    "predict": json.dumps(
                        {
                            "1569250080000": 60,
                            "1569253680000": 70,
                            "1569340080000": 80,
                        }
                    ),
                    "upper_bound": json.dumps(
                        {
                            "1569250080000": 100,
                            "1569253680000": 200,
                            "1569340080000": 300,
                        }
                    ),
                    "lower_bound": json.dumps(
                        {
                            "1569250080000": 30,
                            "1569253680000": 20,
                            "1569340080000": 10,
                        }
                    ),
                },
                "dimensions": {"ip": "127.0.0.1"},
                "time": 1569246480,
            },
            self.mocked_aiops_item,
        )

    def test_anomaly_message__current(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "duration": 86400,
                "thresholds": [[{"method": "lte", "threshold": 50}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert len(anomaly_result) == 0

    def test_anomaly_message__predict(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "duration": 86400,
                "thresholds": [[{"method": "gte", "threshold": 60}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].context["predict_point"] == [60, 1569250080]
        assert anomaly_result[0].anomaly_message == "avg(测试指标) >= 60%, 将于1h后满足条件, 预测值60%"

    def test_anomaly_message__predict_2(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "duration": 86400 * 7,
                "thresholds": [[{"method": "lt", "threshold": 85}, {"method": "gte", "threshold": 75}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].context["predict_point"] == [80, 1569340080]
        assert anomaly_result[0].anomaly_message == "avg(测试指标) < 85% 且 >= 75%, 将于1d 2h后满足条件, 预测值80%"

    def test_anomaly_message__predict_normal(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "duration": 86400,
                "thresholds": [[{"method": "lt", "threshold": 85}, {"method": "gte", "threshold": 75}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert not anomaly_result

    def test_anomaly_message__predict_normal_2(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "duration": 86400,
                "thresholds": [[{"method": "lt", "threshold": 40}, {"method": "gte", "threshold": 30}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert not anomaly_result

    def test_anomaly_message__predict_upper_bound(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "bound_type": "upper",
                "duration": 86400,
                "thresholds": [[{"method": "gte", "threshold": 180}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].context["predict_point"] == [200, 1569253680]
        assert anomaly_result[0].anomaly_message == "avg(测试指标) >= 180%, 将于2h后满足条件, 预测上界200%"

    def test_anomaly_message__predict_lower_bound(self):
        detect_engine = TimeSeriesForecasting(
            config={
                "args": {"$is_linear": 0},
                "plan_id": 87,
                "visual_type": "forecasting",
                "bound_type": "lower",
                "duration": 86400,
                "thresholds": [[{"method": "lte", "threshold": 25}]],
            }
        )
        anomaly_result = detect_engine.detect_records(self.datapoint50, 1)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].context["predict_point"] == [20, 1569253680]
        assert anomaly_result[0].anomaly_message == "avg(测试指标) <= 25%, 将于2h后满足条件, 预测下界20%"
