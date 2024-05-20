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
import json
import time
from unittest import TestCase

import mock
import pytest
from django.conf import settings

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.cache.key import (
    ALERT_DETECT_RESULT,
    COMPOSITE_DIMENSION_KEY_LOCK,
    COMPOSITE_QOS_COUNTER,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.composite.processor import CompositeProcessor
from bkmonitor.models import CacheNode
from constants.action import ActionSignal
from constants.alert import EventStatus

pytestmark = pytest.mark.django_db

STRATEGY = {
    "bk_biz_id": 2,
    "version": "v2",
    "items": [
        {
            "id": 32,
            "name": "关联告警",
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "alert",
                    "alias": "A",
                    "metric_id": "bk_monitor.alert.7",
                    "id": 41,
                    "functions": [],
                    "bkmonitor_strategy_id": 7,
                    "agg_dimension": ["ip", "bk_cloud_id", "tags.device"],
                    "agg_condition": [],
                },
                {
                    "data_source_label": "bk_fta",
                    "data_type_label": "alert",
                    "alias": "B",
                    "metric_id": "bk_fta.alert.测试关联告警",
                    "alert_name": "测试关联告警",
                    "id": 42,
                    "functions": [],
                    "agg_dimension": ["ip", "tags.device"],
                    "agg_condition": [],
                },
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "alert",
                    "alias": "C",
                    "metric_id": "bk_monitor.alert.9",
                    "id": 43,
                    "functions": [],
                    "bkmonitor_strategy_id": 9,
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "agg_condition": [],
                },
            ],
            "algorithms": [],
        }
    ],
    "detects": [
        {
            "id": 29,
            "level": 1,
            "expression": "A && B && C",
            "trigger_config": {"count": 5, "check_window": 5},
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "connector": "and",
        },
        {
            "id": 30,
            "level": 2,
            "expression": "A && B || C",
            "trigger_config": {"count": 5, "check_window": 5},
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "connector": "and",
        },
        {
            "id": 31,
            "level": 2,
            "expression": "A || B && C",
            "trigger_config": {"count": 5, "check_window": 5},
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "connector": "and",
        },
        {
            "id": 32,
            "level": 3,
            "expression": "A || B || C",
            "trigger_config": {"count": 5, "check_window": 5},
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "connector": "and",
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
    "id": 1,
    "name": "test",
}


class TestProcessor(TestCase):
    def setUp(self) -> None:
        get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()
        COMPOSITE_DIMENSION_KEY_LOCK.client.flushall()
        self.kafka_mock = mock.patch("alarm_backends.core.alert.adapter.MonitorEventAdapter.push_to_kafka")
        self.alert_log_create = mock.patch("bkmonitor.documents.AlertLog.bulk_create", return_value=True)
        self.alert_log_create.start()
        self.kafka_mock.start()
        self.celery_mock = mock.patch("alarm_backends.service.fta_action.tasks.create_actions.delay")
        self.celery_mock.start()

    def tearDown(self) -> None:
        COMPOSITE_DIMENSION_KEY_LOCK.client.flushall()
        self.kafka_mock.stop()
        self.celery_mock.stop()
        self.alert_log_create.stop()

    def test_pull(self):
        StrategyCacheManager.cache.hmset(
            StrategyCacheManager.FTA_ALERT_CACHE_KEY,
            {
                "alert|测试关联告警": json.dumps(
                    {
                        "2": [1, 2, 3],
                        "3": [4, 5, 6],
                    }
                )
            },
        )

        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(STRATEGY)
        )

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "测试关联告警",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        processor.pull()

        self.assertEqual(3, len(processor.strategy_ids))
        self.assertEqual(1, len(processor.strategies))
        self.assertEqual(1, processor.strategies[0]["id"])

        processor = CompositeProcessor(alert, composite_strategy_ids=[1, 2, 3])
        processor.pull()
        self.assertEqual(1, len(processor.strategies))

        processor = CompositeProcessor(alert, composite_strategy_ids=[2, 3])
        processor.pull()
        self.assertEqual(0, len(processor.strategies))

    def test_cal_public_dimensions(self):
        dimensions = CompositeProcessor.cal_public_dimensions(STRATEGY)
        self.assertEqual(["ip"], dimensions)

    def test_process_strategy__none(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "无关的测试关联告警",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        processor.process_composite_strategy(STRATEGY)

        self.assertEqual(0, len(processor.actions))

    def test_process_strategy(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "测试关联告警",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(3, int(event["severity"]))

        # IP 不一致的情况
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.2",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.2",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(3, int(event["severity"]))

        # IP 一致
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(2, int(event["severity"]))

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 9,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(1, int(event["severity"]))

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 9,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertIsNone(event)

    def test_match_query_config(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        query_config = copy.deepcopy(STRATEGY["items"][0]["query_configs"][0])
        processor = CompositeProcessor(alert)

        query_config["agg_condition"] = [
            {"key": "tags.device", "value": ["cpu0", "cpu1"], "method": "eq", "condition": "and"},
            {"key": "ip", "value": ["10.0.0.1"], "method": "eq", "condition": "and"},
        ]
        self.assertTrue(processor.match_query_config(query_config))

        query_config["agg_condition"] = [
            {"key": "tags.device", "value": ["cpu0", "cpu1"], "method": "eq", "condition": "and"},
            {"key": "ip", "value": ["10.0.0.2"], "method": "eq", "condition": "and"},
        ]
        self.assertFalse(processor.match_query_config(query_config))

        query_config["agg_condition"] = [
            {"key": "tags.device", "value": ["cpu0", "cpu1"], "method": "eq", "condition": "and"},
            {"key": "ip", "value": ["10.0.0.2"], "method": "eq", "condition": "or"},
        ]
        self.assertTrue(processor.match_query_config(query_config))

        query_config["agg_condition"] = [
            {"key": "tags.device", "value": ["cpu."], "method": "reg", "condition": "and"},
            {"key": "ip", "value": ["10.0.0.2"], "method": "neq", "condition": "and"},
        ]
        self.assertTrue(processor.match_query_config(query_config))

    def test_detect_connector(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(3, int(event["severity"]))
        self.assertEqual("test", event["alert_name"])
        self.assertEqual(1, event["strategy_id"])

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 9,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(2, int(event["severity"]))

    def test_composite_closed(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(3, int(event["severity"]))
        self.assertEqual("ABNORMAL", event["status"])

        alert.update(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                    "status": "RECOVERED",
                }
            )
        )
        processor = CompositeProcessor(alert)
        event = processor.process_composite_strategy(STRATEGY)
        self.assertEqual(3, int(event["severity"]))
        self.assertEqual("CLOSED", event["status"])

    def test_single_strategy(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(7, int(action["strategy_id"]))
        self.assertEqual("abnormal", action["signal"])
        self.assertEqual(1, int(action["severity"]))

        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

    def test_single_strategy_ack(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 7,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                    "extra_info": {"strategy": {"notice": {"signal": ["ack"]}}},
                }
            )
        )

        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(7, int(action["strategy_id"]))
        self.assertEqual("abnormal", action["signal"])
        self.assertEqual(1, int(action["severity"]))
        es_alert = alert.to_document()
        es_alert.is_ack = True
        es_alert.is_ack_noticed = False

        alert = Alert(data=es_alert.to_dict())
        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual("ack", action["signal"])
        self.assertEqual(1, int(action["severity"]))

    def test_single_strategy_recovered(self):
        recovered_event = Event(
            {
                "event_id": "2",
                "plugin_id": "fta-test",
                "alert_name": "xxx",
                "strategy_id": 8,
                "time": 1617504052,
                "tags": [{"key": "device", "value": "cpu0"}],
                "severity": 1,
                "target": "10.0.0.1",
                "dedupe_keys": ["alert_name", "target", "tags.device"],
                "ip": "10.0.0.1",
                "bk_cloud_id": 0,
                "bk_biz_id": 2,
                "status": "RECOVERED",
            }
        )
        recovered_alert = Alert.from_event(recovered_event)

        processor = CompositeProcessor(recovered_alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 8,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual("abnormal", action["signal"])
        self.assertEqual(1, int(action["severity"]))

        alert.update(recovered_event)
        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual("recovered", action["signal"])
        self.assertEqual(1, int(action["severity"]))

    def test_single_strategy_closed(self):
        closed_event = Event(
            {
                "event_id": "2",
                "plugin_id": "fta-test",
                "alert_name": "xxx",
                "strategy_id": 8,
                "time": 1617504052,
                "tags": [{"key": "device", "value": "cpu0"}],
                "severity": 1,
                "target": "10.0.0.1",
                "dedupe_keys": ["alert_name", "target", "tags.device"],
                "ip": "10.0.0.1",
                "bk_cloud_id": 0,
                "bk_biz_id": 2,
                "status": "CLOSED",
            }
        )
        recovered_alert = Alert.from_event(closed_event)

        processor = CompositeProcessor(recovered_alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 8,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )

        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual("abnormal", action["signal"])
        self.assertEqual(1, int(action["severity"]))

        alert.update(closed_event)
        processor = CompositeProcessor(alert)
        action = processor.process_single_strategy()
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual("closed", action["signal"])
        self.assertEqual(1, int(action["severity"]))

    def test_single_strategy_handle(self):
        """
        测试已经存在cache中但是并没有处理过的的告警
        """
        event = Event(
            {
                "event_id": "2",
                "plugin_id": "fta-test",
                "alert_name": "xxx",
                "strategy_id": 8,
                "time": 1617504052,
                "tags": [{"key": "device", "value": "cpu0"}],
                "severity": 1,
                "target": "10.0.0.1",
                "dedupe_keys": ["alert_name", "target", "tags.device"],
                "ip": "10.0.0.1",
                "bk_cloud_id": 0,
                "bk_biz_id": 2,
                "status": EventStatus.ABNORMAL,
            }
        )
        alert = Alert.from_event(event)
        # 被QOS的告警，需要在当前告警窗口结束之后才能再次发送，避免重复QOS记录
        alert.data["create_time"] = int(time.time()) - settings.QOS_DROP_ACTION_WINDOW - 1
        cache_key = ALERT_DETECT_RESULT.get_key(alert_id=alert.id)
        ALERT_DETECT_RESULT.client.set(cache_key, alert.severity, ALERT_DETECT_RESULT.ttl)
        processor = CompositeProcessor(alert=alert)
        action = processor.process_single_strategy()
        self.assertEqual(action["strategy_id"], event.strategy_id)
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual(ActionSignal.ABNORMAL, action["signal"])
        self.assertEqual(1, int(action["severity"]))

        processor = CompositeProcessor(alert=alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

    def test_single_strategy_no_data(self):
        no_data_alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 8,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}, {"key": "__NO_DATA_DIMENSION__", "value": True}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device", "tags.__NO_DATA_DIMENSION__"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            )
        )
        processor = CompositeProcessor(no_data_alert)
        action = processor.process_single_strategy()
        self.assertEqual(8, int(action["strategy_id"]))
        self.assertEqual("no_data", action["signal"])
        self.assertEqual(1, int(action["severity"]))

        processor = CompositeProcessor(no_data_alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

        no_data_alert.update(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "xxx",
                    "strategy_id": 8,
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}, {"key": "__NO_DATA_DIMENSION__", "value": True}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target", "tags.device", "tags.__NO_DATA_DIMENSION__"],
                    "ip": "10.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                    "status": "CLOSED",
                }
            )
        )
        processor = CompositeProcessor(no_data_alert)
        action = processor.process_single_strategy()
        self.assertIsNone(action)

    def test_qos(self):
        success = failed = 0
        processor = CompositeProcessor(
            Alert({"alert_name": "test", "severity": 2, "strategy_id": 1, "id": "alert_id"}), "ABNORMAL"
        )
        for i in range(settings.QOS_DROP_ACTION_THRESHOLD):
            processor.alert = Alert({"alert_name": "test", "severity": 2, "strategy_id": 1, "id": f"alert_id{i}"})
            processor.add_action(
                strategy_id=1,
                signal="ABNORMAL",
                alert_ids=[],
                severity=2,
                dimensions={},
            )
            s, f = processor.push_actions()
            success += s
            failed += f

        self.assertEqual(settings.QOS_DROP_ACTION_THRESHOLD, success)
        self.assertEqual(0, failed)

        processor = CompositeProcessor(
            Alert({"alert_name": "test", "severity": 2, "strategy_id": 1, "id": f"alert_id{success}"}), "ABNORMAL"
        )
        processor.add_action(
            strategy_id=1,
            signal="ABNORMAL",
            alert_ids=[],
            severity=2,
            dimensions={},
        )

        success, failed = processor.push_actions()
        self.assertEqual(0, success)
        self.assertEqual(1, failed)

        processor.alert = Alert({"alert_name": "test", "severity": 2, "strategy_id": 1, "id": f"alert_id{success + 1}"})

        processor.add_action(
            strategy_id=1,
            signal="CLOSED",
            alert_ids=[],
            severity=2,
            dimensions={},
        )

        success, failed = processor.push_actions()
        self.assertEqual(1, success)
        self.assertEqual(0, failed)

        qos_counter_key = COMPOSITE_QOS_COUNTER.get_key(strategy_id=1, signal="ABNORMAL", severity=2, alert_md5="")
        COMPOSITE_QOS_COUNTER.client.expire(qos_counter_key, 0)

        processor.add_action(
            strategy_id=1,
            signal="ABNORMAL",
            alert_ids=[],
            severity=2,
            dimensions={},
        )

        success, failed = processor.push_actions()
        self.assertEqual(1, success)
        self.assertEqual(0, failed)

        processor = CompositeProcessor(Alert({"alert_name": "test", "severity": 2, "strategy_id": 2}), "ABNORMAL")
        processor.add_action(
            strategy_id=2,
            signal="ABNORMAL",
            alert_ids=[],
            severity=2,
            dimensions={},
        )

        success, failed = processor.push_actions()
        self.assertEqual(1, success)
        self.assertEqual(0, failed)

        processor = CompositeProcessor(
            Alert({"alert_name": "test", "severity": 2, "strategy_id": 0, "event": {"bk_biz_id": 0}}), "ABNORMAL"
        )
        for i in range(0, settings.QOS_DROP_ACTION_THRESHOLD):
            processor.add_action(
                strategy_id=2,
                signal="ABNORMAL",
                alert_ids=[],
                severity=2,
                dimensions={},
            )

        success, failed = processor.push_actions()
        self.assertEqual(settings.QOS_DROP_ACTION_THRESHOLD, success)
        self.assertEqual(0, failed)
