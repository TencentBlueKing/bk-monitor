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


import json
from datetime import datetime
from uuid import uuid4

import mock
from django.test import TestCase
from six.moves import range

from alarm_backends.core.cache.key import (
    ANOMALY_LIST_KEY,
    ANOMALY_SIGNAL_KEY,
    TRIGGER_EVENT_LIST_KEY,
)
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.trigger.processor import TriggerProcessor
from bkmonitor.models import AnomalyRecord, CacheNode, time_tools
from core.errors.alarm_backends import StrategyNotFound

from .test_checker import STRATEGY

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

EVENT = {
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
    "trigger": {
        "level": "2",
        "anomaly_ids": [
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246240.1.1.2",
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246360.1.1.2",
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
        ],
    },
}


def mocked_check():
    anomaly_records = []
    for i in range(3):
        anomaly_records.append(
            AnomalyRecord(
                anomaly_id=uuid4().hex,
                source_time=time_tools.mysql_time(datetime.now()),
                strategy_id=1,
                origin_alarm={},
                event_id="",
            )
        )
    return anomaly_records, EVENT


#
# Strategy = mock.patch('alarm_backends.service.trigger.processor.Strategy').start()
# Strategy.get_strategy_snapshot_by_key.side_effect = lambda key: STRATEGY if key == 'xxx' else None
#
# check_func = mock.patch('alarm_backends.service.trigger.processor.AnomalyChecker.check').start()
# check_func.side_effect = mocked_check


class TestProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Strategy = mock.patch("alarm_backends.service.trigger.processor.Strategy")
        mock_strategy = cls.Strategy.start()
        mock_strategy.get_strategy_snapshot_by_key.side_effect = lambda key, _: STRATEGY if key == "xxx" else None

        cls.check_func = mock.patch("alarm_backends.service.trigger.processor.AnomalyChecker.check")
        mock_check = cls.check_func.start()
        mock_check.side_effect = mocked_check

    @classmethod
    def tearDownClass(cls):
        cls.Strategy.stop()
        cls.check_func.stop()

    def clear_data(self):
        anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=1, item_id=1)
        ANOMALY_LIST_KEY.client.delete(anomaly_list_key)
        TRIGGER_EVENT_LIST_KEY.client.delete(TRIGGER_EVENT_LIST_KEY.get_key())
        AnomalyRecord.objects.all().delete()

    def setUp(self):
        get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()
        self.clear_data()

    def tearDown(self):
        self.clear_data()

    def test_get_strategy(self):
        processor = TriggerProcessor(1, 1)

        strategy_config = processor.get_strategy_snapshot("xxx")
        self.assertDictEqual(strategy_config, STRATEGY)

        with self.assertRaises(StrategyNotFound):
            processor.get_strategy_snapshot("non-exist")

        self.assertEqual(len(processor._strategy_snapshots), 1)

    def test_pull(self):
        def _fake_redis_delay(*args, **kwargs):
            ANOMALY_SIGNAL_KEY.client.rpush(ANOMALY_SIGNAL_KEY.get_key(), "1.1")

        anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=1, item_id=1)
        for i in range(10):
            ANOMALY_LIST_KEY.client.lpush(anomaly_list_key, json.dumps(POINT))
        TriggerProcessor.MAX_PROCESS_COUNT = 6
        processor = TriggerProcessor(1, 1)

        # 除了 pull 分片拉取逻辑，trigger 信号一般先进先出，此处检测分片拉取将信号直接插入到右侧
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")

        with mock.patch(
            "alarm_backends.service.trigger.processor.ANOMALY_SIGNAL_KEY.client.delay", side_effect=_fake_redis_delay
        ) as fake_redis_delay:
            processor.pull()
            fake_redis_delay.assert_called_once()

        self.assertEqual(len(processor.anomaly_points), 6)
        self.assertEqual(ANOMALY_LIST_KEY.client.llen(anomaly_list_key), 4)
        self.assertEqual(ANOMALY_SIGNAL_KEY.client.lindex(ANOMALY_SIGNAL_KEY.get_key(), -1), "1.1")

        with mock.patch(
            "alarm_backends.service.trigger.processor.ANOMALY_SIGNAL_KEY.client.delay", side_effect=_fake_redis_delay
        ) as fake_redis_delay:
            processor.pull()
            fake_redis_delay.assert_not_called()

        self.assertEqual(len(processor.anomaly_points), 4)
        self.assertEqual(ANOMALY_LIST_KEY.client.llen(anomaly_list_key), 0)

        TriggerProcessor.MAX_PROCESS_COUNT = 0
        ANOMALY_LIST_KEY.client.delete(anomaly_list_key)

    def test_process_point(self):
        processor = TriggerProcessor(1, 1)
        processor.process_point(json.dumps(POINT))
        self.assertEqual(len(processor.event_records), 1)

    def test_process(self):
        processor = TriggerProcessor(1, 1)
        setattr(processor.strategy, "in_alarm_time", lambda: (True, None))
        anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=1, item_id=1)
        for i in range(10):
            ANOMALY_LIST_KEY.client.lpush(anomaly_list_key, json.dumps(POINT))

        with mock.patch(
            "alarm_backends.service.trigger.processor.MonitorEventAdapter.push_to_kafka"
        ) as fake_push_to_kafka:
            processor.process()
            print(fake_push_to_kafka.call_args)
