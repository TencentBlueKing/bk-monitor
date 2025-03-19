# -*- coding: utf-8 -*-
import copy
from unittest import TestCase

import pytest

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.abnormal_cluster import (
    AbnormalCluster,
    parse_cluster,
)
from alarm_backends.tests.service.detect.mocked_data import mocked_item
from bkmonitor.models import CacheNode


@pytest.mark.django_db
class TestAbnormalCluster(TestCase):
    def setUp(self):
        # 重置测试用例的Item防止ID超过用例上限
        CacheNode.refresh_from_settings()

        self.mocked_aiops_item = copy.deepcopy(mocked_item)
        self.mocked_aiops_item.query_configs[0]["intelligent_detect"] = {"use_sdk": False, "status": "running"}

    def test_value_0_message(self):
        datapoint_0 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 0,
                "values": {
                    "cluster": '{"ip": "1.1.1.1"}',
                    "upper_bound": 10,
                    "lower_bound": 0,
                },
                "time": 1569246480,
            },
            self.mocked_aiops_item,
        )

        detect_engine = AbnormalCluster(config={})
        anomaly_result = detect_engine.detect(datapoint_0)
        assert len(anomaly_result) == 0

    def test_value_1_message(self):
        datapoint_1 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 1,
                "values": {
                    "cluster": '{"ip": "1.1.1.1"}',
                    "upper_bound": 10,
                    "lower_bound": 0,
                },
                "time": 1569246480,
            },
            self.mocked_aiops_item,
        )

        detect_engine = AbnormalCluster(config={})
        anomaly_result = detect_engine.detect(datapoint_1)
        alert_message = parse_cluster(datapoint_1.values["cluster"])
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == " {} 维度值发生离群".format(alert_message)

    def test_value_gt_10_message(self):
        datapoint_10 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 10,
                "values": {
                    "cluster": '{"ip": "1.1.1.1", "name": "name"},{"ip": "2.2.2.2", "name": "name2"}',
                    "upper_bound": 10,
                    "lower_bound": 0,
                },
                "time": 1569246480,
            },
            self.mocked_aiops_item,
        )

        detect_engine = AbnormalCluster(config={})
        anomaly_result = detect_engine.detect(datapoint_10)
        alert_message = parse_cluster(datapoint_10.values["cluster"])
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message == " {} 等{}组维度值发生离群".format(alert_message, datapoint_10.value)
