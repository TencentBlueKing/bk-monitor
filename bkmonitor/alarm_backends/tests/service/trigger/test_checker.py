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
import copy

import arrow
import pytest
from django.test import TestCase

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache.key import CHECK_RESULT_CACHE_KEY
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.trigger.checker import AnomalyChecker
from bkmonitor.models import CacheNode
from bkmonitor.utils import time_tools
from core.errors.alarm_backends import StrategyItemNotFound

pytestmark = pytest.mark.django_db

STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "idle",
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "id": 2,
                    "agg_method": "AVG",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "result_table_id": "system.cpu_detail",
                    "unit": "%",
                    "data_type_label": "time_series",
                    "metric_id": "bk_monitor.system.cpu_detail.idle",
                    "data_source_label": "bk_monitor",
                }
            ],
            "target": [
                [
                    {
                        "field": "ip",
                        "method": "eq",
                        "value": [
                            {"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0},
                        ],
                    }
                ]
            ],
            "algorithms": [
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 1, "type": "Threshold", "id": 1},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 2, "type": "Threshold", "id": 2},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 3, "type": "Threshold", "id": 3},
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 1,
            "name": "\u7a7a\u95f2\u7387",
        }
    ],
    "detects": [
        {
            "expression": "",
            "connector": "and",
            "level": 1,
            "trigger_config": {"count": 3, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
        {
            "expression": "",
            "connector": "and",
            "level": 2,
            "trigger_config": {"count": 2, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
        {
            "expression": "",
            "connector": "and",
            "level": 3,
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
    ],
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "aa", "recovery_template": ""},
            "id": 2,
            "notice_group_list": [
                {
                    "notice_receiver": ["user#test"],
                    "name": "test",
                    "notice_way": {"1": ["weixin"], "3": ["weixin"], "2": ["weixin"]},
                    "notice_group_id": 1,
                    "message": "",
                    "notice_group_name": "test",
                    "id": 1,
                }
            ],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}


POINT = {
    "data": {
        "record_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480",
        "value": 1.38,
        "values": {"timestamp": 1569246480, "load5": 1.38},
        "dimensions": {"ip": "10.0.0.1"},
        "time": 1569246480,
    },
    "anomaly": {
        "1": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.1",
            "anomaly_time": "2019-10-10 10:10:00",
        },
        "2": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
            "anomaly_time": "2019-10-10 10:10:00",
        },
        "3": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.3",
            "anomaly_time": "2019-10-10 10:10:00",
        },
    },
    "strategy_snapshot_key": "xxx",
}

# 不同的异常数量测试集
CHECK_RESULT_SETS = {
    0: [
        ("1569246240|1", 1569246240),
        ("1569246300|2", 1569246300),
        ("1569246360|3", 1569246360),
        ("1569246420|4", 1569246420),
        ("1569246480|5", 1569246480),
    ],
    1: [
        ("1569246240|1", 1569246240),
        ("1569246300|2", 1569246300),
        ("1569246360|3", 1569246360),
        ("1569246420|ANOMALY", 1569246420),
        ("1569246480|5", 1569246480),
    ],
    2: [
        ("1569246240|ANOMALY", 1569246240),
        ("1569246300|2", 1569246300),
        ("1569246360|3", 1569246360),
        ("1569246420|ANOMALY", 1569246420),
        ("1569246480|5", 1569246480),
    ],
    3: [
        ("1569246240|ANOMALY", 1569246240),
        ("1569246300|2", 1569246300),
        ("1569246360|ANOMALY", 1569246360),
        ("1569246420|4", 1569246420),
        ("1569246480|ANOMALY", 1569246480),
    ],
    4: [
        # 距离较远的点
        ("1690517000|ANOMALY", 1569244240),
        ("1690516000|2", 1569246300),
        ("1690515000|ANOMALY", 1569246360),
        ("1690514000|ANOMALY", 1569246420),
        ("1690513000|ANOMALY", 1569246480),
    ],
    5: [
        ("1569246240|ANOMALY", 1569246240),
        ("1569246300|ANOMALY", 1569246300),
        ("1569246360|ANOMALY", 1569246360),
        ("1569246420|ANOMALY", 1569246420),
        ("1569246480|ANOMALY", 1569246480),
    ],
}


class TestChecker(TestCase):

    databases = {"monitor_api", "default"}

    @classmethod
    def gen_check_result_key(cls, level):
        return CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=level,
        )

    def test_init(self):
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        self.assertEqual(checker.item["id"], 1)
        self.assertEqual(checker.trigger_configs["1"]["trigger_count"], 3)
        self.assertEqual(checker.trigger_configs["1"]["check_window_size"], 5)
        self.assertEqual(checker.trigger_configs["2"]["trigger_count"], 2)
        self.assertEqual(checker.trigger_configs["3"]["trigger_count"], 1)
        self.assertEqual(checker.check_window_unit, 60)
        self.assertEqual(checker.dimensions_md5, "55a76cf628e46c04a052f4e19bdb9dbf")
        self.assertEqual(checker.source_time, 1569246480)

        with self.assertRaises(StrategyItemNotFound):
            AnomalyChecker(POINT, STRATEGY, 23)

    def setUp(self):
        get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()
        self.clear_check_result()

    def tearDown(self):
        self.clear_check_result()

    @classmethod
    def clear_check_result(cls):
        CHECK_RESULT_CACHE_KEY.client.flushall()

    def insert_check_result(self, anomaly_count):
        for level in [1, 2, 3]:
            check_results = CHECK_RESULT_SETS.get(anomaly_count, [])
            for check_result in check_results:
                CHECK_RESULT_CACHE_KEY.client.zadd(self.gen_check_result_key(level), {check_result[0]: check_result[1]})

    def test_check_anomaly_by_level_anomaly_count_1(self):
        self.insert_check_result(1)
        checker = AnomalyChecker(POINT, STRATEGY, 1)

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246420])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("2")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246420])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("3")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246420])

    def test_check_anomaly_by_multi_metrics(self):
        self.insert_check_result(4)
        multi_strategy = copy.deepcopy(STRATEGY)
        multi_strategy["detects"][0] = {
            "expression": "",
            "connector": "and",
            "level": 1,
            "trigger_config": {"count": 4, "check_window": 5},
            "recovery_config": {"check_window": 5},
        }
        multi_strategy["items"][0]["query_configs"] = [
            {
                "metric_field": "idle",
                "agg_dimension": ["ip", "bk_cloud_id"],
                "id": 2,
                "agg_method": "AVG",
                "agg_condition": [],
                "agg_interval": 480,
                "result_table_id": "system.cpu_detail",
                "unit": "%",
                "data_type_label": "time_series",
                "metric_id": "bk_monitor.system.cpu_detail.idle",
                "data_source_label": "bk_monitor",
            },
            {
                "metric_field": "idle",
                "agg_dimension": ["ip", "bk_cloud_id"],
                "id": 2,
                "agg_method": "AVG",
                "agg_condition": [],
                "agg_interval": 60,
                "result_table_id": "system.cpu_detail",
                "unit": "%",
                "data_type_label": "time_series",
                "metric_id": "bk_monitor.system.cpu_detail.idle",
                "data_source_label": "bk_monitor",
            },
        ]

        checker = AnomalyChecker(POINT, multi_strategy, 1)
        # 取小的周期
        assert checker.check_window_unit == 60
        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertFalse(is_triggered)

        multi_strategy["items"][0]["query_configs"] = [
            {
                "metric_field": "idle",
                "agg_dimension": ["ip", "bk_cloud_id"],
                "id": 2,
                "agg_method": "AVG",
                "agg_condition": [],
                "agg_interval": 480,
                "result_table_id": "system.cpu_detail",
                "unit": "%",
                "data_type_label": "time_series",
                "metric_id": "bk_monitor.system.cpu_detail.idle",
                "data_source_label": "bk_monitor",
            }
        ]

        checker = AnomalyChecker(POINT, multi_strategy, 1)
        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertTrue(is_triggered)

    def test_check_anomaly_by_level_anomaly_count_2(self):
        self.insert_check_result(2)
        checker = AnomalyChecker(POINT, STRATEGY, 1)

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246420])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("2")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246420])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("3")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246420])

    def test_check_anomaly_by_level_anomaly_count_3(self):
        self.insert_check_result(3)
        checker = AnomalyChecker(POINT, STRATEGY, 1)

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246360, 1569246480])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("2")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246360, 1569246480])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("3")
        self.assertTrue(is_triggered)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246360, 1569246480])

        # 等级不存在的情况
        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("0")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

    def test_check_anomaly_by_level_anomaly_count_0(self):
        self.insert_check_result(0)
        checker = AnomalyChecker(POINT, STRATEGY, 1)

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("2")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("3")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

    def test_check_anomaly_by_level_no_anomaly_data(self):
        checker = AnomalyChecker(POINT, STRATEGY, 1)

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("1")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("2")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

        is_triggered, anomaly_timestamps = checker._check_anomaly_by_level("3")
        self.assertFalse(is_triggered)
        self.assertListEqual(anomaly_timestamps, [])

    def test_check_anomaly_by_level_no_data(self):
        self.insert_check_result(5)
        strategy = copy.deepcopy(STRATEGY)
        strategy["no_data_config"] = {"continuous": 5}

        point = copy.deepcopy(POINT)
        point["data"]["dimensions"][NO_DATA_TAG_DIMENSION] = True

        checker = AnomalyChecker(point, strategy, 1)
        anomaly_level, anomaly_timestamps = checker.check_anomaly()
        self.assertEqual(anomaly_level, 1)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246300, 1569246360, 1569246420, 1569246480])

    def test_check_anomaly_level_3(self):
        self.insert_check_result(3)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_level, anomaly_timestamps = checker.check_anomaly()
        self.assertEqual(anomaly_level, 1)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246360, 1569246480])

    def test_check_anomaly_level_2(self):
        self.insert_check_result(2)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_level, anomaly_timestamps = checker.check_anomaly()
        self.assertEqual(anomaly_level, 2)
        self.assertListEqual(anomaly_timestamps, [1569246240, 1569246420])

    def test_check_anomaly_level_1(self):
        self.insert_check_result(1)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_level, anomaly_timestamps = checker.check_anomaly()
        self.assertEqual(anomaly_level, 3)
        self.assertListEqual(anomaly_timestamps, [1569246420])

    def test_check_anomaly_no_anomaly(self):
        self.insert_check_result(0)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_level, anomaly_timestamps = checker.check_anomaly()
        self.assertEqual(anomaly_level, -1)
        self.assertListEqual(anomaly_timestamps, [])

    def test_gen_event_record(self):
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        record = checker.gen_event_record(-1, [])
        self.assertIsNone(record)
        record = checker.gen_event_record(2, [1569246240, 1569246360, 1569246480])
        self.assertEqual(record["trigger"]["level"], "2")
        self.assertListEqual(
            record["trigger"]["anomaly_ids"],
            [
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246240.1.1.2",
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246360.1.1.2",
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
            ],
        )

    def test_gen_anomaly_records(self):
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        records = checker.gen_anomaly_records()
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].source_time, time_tools.mysql_time(arrow.get(1569246480).datetime))
        self.assertEqual(records[0].strategy_id, 1)
        anomaly_ids = {record.anomaly_id for record in records}
        self.assertSetEqual(
            anomaly_ids,
            {
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.1",
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
                "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.3",
            },
        )

    def test_check_no_anomaly(self):
        self.insert_check_result(0)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_records, event_record = checker.check()
        self.assertEqual(len(anomaly_records), 3)
        self.assertIsNone(event_record)

    def test_check(self):
        self.insert_check_result(2)
        checker = AnomalyChecker(POINT, STRATEGY, 1)
        anomaly_records, event_record = checker.check()
        self.assertEqual(len(anomaly_records), 3)
        self.assertEqual(event_record["trigger"]["level"], "2")
