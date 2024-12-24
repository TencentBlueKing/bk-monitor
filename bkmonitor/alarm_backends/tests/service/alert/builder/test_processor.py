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
import time

import mock
from django.conf import settings
from django.test import TestCase
from elasticsearch.helpers import BulkIndexError

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.alert import AlertUIDManager
from alarm_backends.core.cache.key import ALERT_DEDUPE_CONTENT_KEY, ALERT_SNAPSHOT_KEY
from alarm_backends.service.alert.builder.processor import AlertBuilder
from api.cmdb.define import Host
from bkmonitor.models import CacheNode
from constants.data_source import KubernetesResultTableLabel


class TestProcessor(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        CacheNode.refresh_from_settings()
        ALERT_DEDUPE_CONTENT_KEY.client.flushall()
        AlertUIDManager.SEQUENCE_REDIS_KEY.client.flushall()
        AlertUIDManager.clear_pool()
        Alert.RECOVER_WINDOW_SIZE = 0
        self.celery_mock = mock.patch("alarm_backends.service.composite.tasks.check_action_and_composite.delay")
        self.host_ip_mock = mock.patch(
            "alarm_backends.core.cache.cmdb.host.HostIPManager.multi_get_with_dict",
            return_value={
                # 单个IP
                "127.0.0.1": ["127.0.0.1|0"],
                # 多云区域
                "127.0.0.2": ["127.0.0.2|0", "127.0.0.2|1"],
            },
        )

        self.host_mock = mock.patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.multi_get_with_dict",
            return_value={
                "127.0.0.1|0": Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                ),
                "127.0.0.2|1": Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.2",
                        "bk_cloud_id": 1,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                ),
                "127.0.0.2|0": Host(
                    attrs={
                        "bk_host_innerip": "127.0.0.2",
                        "bk_cloud_id": 0,
                        "bk_host_id": 1,
                        "bk_biz_id": 2,
                        "idc_unit_name": "上海",
                        "net_device_id": 123,
                        "topo_link": {},
                    }
                ),
            },
        )
        self.host_mock.start()
        self.host_ip_mock.start()
        self.celery_mock.start()

    def tearDown(self):
        ALERT_DEDUPE_CONTENT_KEY.client.flushall()
        AlertUIDManager.SEQUENCE_REDIS_KEY.client.flushall()
        AlertUIDManager.clear_pool()
        Alert.RECOVER_WINDOW_SIZE = 0
        self.celery_mock.stop()
        self.host_mock.stop()
        self.host_ip_mock.stop()

    def test_build_alerts__same_md5(self):
        processor = AlertBuilder()

        time1 = int(time.time())
        time2 = time1 - 500

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time1,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                }
            ),
            Event(
                {
                    "event_id": "1",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time2,
                    "tags": [{"key": "device", "value": "cpu1"}],
                    "target": "10.0.0.1",
                    "severity": 1,
                    "dedupe_keys": ["alert_name", "target"],
                }
            ),
        ]
        result = processor.build_alerts(events)
        self.assertEqual(len(result), 1)
        alert = result[0]
        self.assertEqual("da2a935c581c2a96004f129878a935b0", alert.dedupe_md5)
        self.assertEqual(time2, alert.begin_time)
        self.assertEqual(time1, alert.latest_time)
        self.assertEqual(1, alert.severity)
        self.assertDictEqual(events[0].to_dict(), alert.top_event)
        self.assertEqual("ABNORMAL", alert.status)
        self.assertEqual(1, AlertUIDManager.parse_sequence(alert.id))

        self.assertEqual(2, len(result[0].logs))
        self.assertEqual("CREATE", result[0].logs[0]["op_type"])
        self.assertEqual("CONVERGE", result[0].logs[1]["op_type"])

    def test_build_alerts__diff_md5(self):
        processor = AlertBuilder()

        time1 = int(time.time())
        time2 = time1 - 500

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time1,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "tags.device", "target"],
                    "extra_info": {"strategy": {"labels": ["TEST"]}},
                }
            ),
            Event(
                {
                    "event_id": "1",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time2,
                    "tags": [{"key": "device", "value": "cpu1"}],
                    "target": "10.0.0.2",
                    "severity": 2,
                    "dedupe_keys": ["alert_name", "tags.device", "target"],
                    "extra_info": {"strategy": {"labels": ["TEST"]}},
                }
            ),
        ]

        result = processor.build_alerts(events)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].labels, ["TEST"])
        self.assertEqual(result[1].labels, ["TEST"])
        self.assertEqual("88590646d37632c545b81ed8bfc0ba5f", result[0].dedupe_md5)
        self.assertEqual(time1, result[0].begin_time)
        self.assertEqual(time1, result[0].latest_time)
        self.assertEqual(1, result[0].severity)
        self.assertDictEqual(events[0].to_dict(), result[0].top_event)
        self.assertEqual(1, len(result[0].logs))
        self.assertEqual("CREATE", result[0].logs[0]["op_type"])

        self.assertEqual("8207bf3588710f1bab2fac2dce3dbb3f", result[1].dedupe_md5)
        self.assertEqual(time2, result[1].begin_time)
        self.assertEqual(time2, result[1].latest_time)
        self.assertEqual(2, result[1].severity)
        self.assertDictEqual(events[1].to_dict(), result[1].top_event)
        self.assertEqual(1, len(result[1].logs))
        self.assertEqual("CREATE", result[1].logs[0]["op_type"])

    def test_build_alerts__expired(self):
        event_time = int(time.time())
        alert_time = event_time - 500

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "strategy_id": 123,
                "alert_name": "test expired",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
            }
        )

        alert = {
            "id": "xxx",
            "dedupe_md5": event.dedupe_md5,
            "end_time": None,
            "begin_time": alert_time,
            "latest_time": alert_time,
            "severity": 2,
            "status": "ABNORMAL",
            "strategy_id": 123,
        }

        ALERT_DEDUPE_CONTENT_KEY.client.set(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"]),
            json.dumps(alert),
        )

        processor = AlertBuilder()

        result = processor.build_alerts([event])
        self.assertEqual(1, len(result))

        alert["end_time"] = event_time + 500
        ALERT_DEDUPE_CONTENT_KEY.client.set(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"]),
            json.dumps(alert),
        )
        result = processor.get_unexpired_events([event])
        self.assertEqual(0, len(result))
        result = processor.dedupe_events_to_alerts([event])
        self.assertEqual(0, len(result))

    @mock.patch("bkmonitor.documents.base.BaseDocument.bulk_create")
    def test_build_alerts__event_drop(self, bulk_create):
        documents = []

        def mock_bulk_create(docs, *args, **kwargs):
            documents.extend(docs)

        bulk_create.side_effect = mock_bulk_create
        processor = AlertBuilder()

        time1 = int(time.time())
        time2 = time1 - 500

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time1,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                }
            ),
            Event(
                {
                    "event_id": "1",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": time2,
                    "tags": [{"key": "device", "value": "cpu1"}],
                    "target": "10.0.0.1",
                    "severity": 2,
                    "dedupe_keys": ["alert_name", "target"],
                }
            ),
        ]

        result = processor.build_alerts(events)

        self.assertEqual(len(result), 1)

        alert = result[0]
        self.assertEqual("da2a935c581c2a96004f129878a935b0", alert.dedupe_md5)
        self.assertEqual(time1, alert.begin_time)
        self.assertEqual(time1, alert.latest_time)
        self.assertEqual(1, alert.severity)
        self.assertDictEqual(events[0].to_dict(), alert.top_event)
        self.assertEqual("ABNORMAL", alert.status)
        self.assertEqual(1, AlertUIDManager.parse_sequence(alert.id))

        self.assertEqual(2, len(result[0].logs))
        self.assertEqual("CREATE", result[0].logs[0]["op_type"])
        self.assertEqual("EVENT_DROP", result[0].logs[1]["op_type"])

        saved_events = processor.save_events(events)
        self.assertEqual(len(saved_events), 1)

    def test_build_alerts__status_recovered(self):
        event_time = int(time.time())
        alert_time = event_time - 500

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "test recovered",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
                "status": "RECOVERED",
                "strategy_id": 123,
            }
        )
        processor = AlertBuilder()

        result = processor.build_alerts([event])
        # 没有告警则恢复事件不起作用
        self.assertEqual(0, len(result))

        alert = {
            "id": "xxx",
            "dedupe_md5": event.dedupe_md5,
            "end_time": None,
            "begin_time": alert_time,
            "latest_time": alert_time,
            "status": "ABNORMAL",
            "severity": 2,
            "strategy_id": 123,
        }

        ALERT_DEDUPE_CONTENT_KEY.client.set(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"]),
            json.dumps(alert),
        )

        result = processor.build_alerts([event])
        # 没有告警则恢复事件不起作用
        self.assertEqual(1, len(result))
        self.assertEqual("RECOVERED", result[0].status)
        self.assertEqual(event_time, result[0].end_time)
        self.assertEqual(1, len(result[0].logs))
        self.assertEqual("RECOVER", result[0].logs[0]["op_type"])

    def test_build_alerts__status_delay_recovered(self):
        Alert.RECOVER_WINDOW_SIZE = 5 * 60
        event_time = int(time.time())
        alert_time = event_time - 500

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "test recovered",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "strategy_id": 123,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
                "status": "RECOVERED",
            }
        )
        processor = AlertBuilder()

        result = processor.build_alerts([event])
        # 没有告警则恢复事件不起作用
        self.assertEqual(0, len(result))

        alert = {
            "id": "xxx",
            "dedupe_md5": event.dedupe_md5,
            "end_time": None,
            "begin_time": alert_time,
            "latest_time": alert_time,
            "status": "ABNORMAL",
            "severity": 2,
            "strategy_id": 123,
        }
        content_key = ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"])

        ALERT_DEDUPE_CONTENT_KEY.client.set(content_key, json.dumps(alert))

        result = processor.build_alerts([event])
        self.assertEqual(1, len(result))
        self.assertEqual("ABNORMAL", result[0].status)
        self.assertEqual(None, result[0].end_time)
        self.assertEqual("RECOVERED", result[0].data["next_status"])
        self.assertEqual(1, len(result[0].logs))
        self.assertEqual("DELAY_RECOVER", result[0].logs[0]["op_type"])

        ALERT_DEDUPE_CONTENT_KEY.client.set(content_key, json.dumps(result[0].to_dict()))

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "test recovered",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "strategy_id": 123,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
                "status": "ABNORMAL",
            }
        )
        result = processor.build_alerts([event])
        self.assertEqual(1, len(result))
        self.assertEqual("ABNORMAL", result[0].status)
        self.assertEqual(None, result[0].end_time)
        self.assertEqual("CLOSED", result[0].data["next_status"])
        self.assertEqual(2, len(result[0].logs))
        self.assertEqual("CONVERGE", result[0].logs[0]["op_type"])
        self.assertEqual("ABORT_RECOVER", result[0].logs[1]["op_type"])

    def test_build_alerts__status_closed(self):
        event_time = int(time.time())
        alert_time = event_time - 500

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "test closed",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "strategy_id": 123,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
                "status": "CLOSED",
            }
        )
        processor = AlertBuilder()

        result = processor.build_alerts([event])
        # 没有告警则恢复事件不起作用
        self.assertEqual(0, len(result))

        alert = {
            "id": "xxx",
            "dedupe_md5": event.dedupe_md5,
            "end_time": None,
            "begin_time": alert_time,
            "latest_time": alert_time,
            "status": "ABNORMAL",
            "severity": 2,
            "strategy_id": 123,
        }
        content_key = ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"])

        ALERT_DEDUPE_CONTENT_KEY.client.set(content_key, json.dumps(alert))

        result = processor.build_alerts([event])
        # 没有告警则恢复事件不起作用
        self.assertEqual(1, len(result))
        self.assertEqual("CLOSED", result[0].status)
        self.assertEqual(event_time, result[0].end_time)
        self.assertEqual(1, len(result[0].logs))
        self.assertEqual("CLOSE", result[0].logs[0]["op_type"])

    def test_build_alerts__severity_up(self):
        event_time = int(time.time())
        alert_time = event_time - 500

        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "test closed",
                "time": event_time,
                "tags": [{"key": "device", "value": "cpu1"}],
                "ip": "10.0.0.1",
                "severity": 2,
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
                "status": "ABNORMAL",
                "strategy_id": 123,
            }
        )
        processor = AlertBuilder()

        result = processor.build_alerts([event])
        self.assertEqual(1, len(result))

        alert = {
            "id": "xxx",
            "dedupe_md5": event.dedupe_md5,
            "end_time": None,
            "begin_time": alert_time,
            "latest_time": alert_time,
            "status": "ABNORMAL",
            "severity": 3,
            "strategy_id": 123,
        }

        content_key = ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=event.strategy_id, dedupe_md5=alert["dedupe_md5"])
        ALERT_DEDUPE_CONTENT_KEY.client.set(content_key, json.dumps(alert))
        result = processor.build_alerts([event])
        self.assertEqual(2, len(result))
        self.assertEqual("CLOSED", result[0].status)
        self.assertEqual(3, result[0].severity)
        self.assertEqual(event_time, result[0].end_time)
        self.assertEqual("ABNORMAL", result[1].status)
        self.assertEqual(2, result[1].severity)
        self.assertEqual(None, result[1].end_time)

    @mock.patch("bkmonitor.documents.base.BaseDocument.bulk_create")
    def test_save_events(self, bulk_create):
        documents = []

        def mock_bulk_create(docs, *args, **kwargs):
            documents.extend(docs)

        bulk_create.side_effect = mock_bulk_create

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504100,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "ip": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "tags.device", "ip"],
                }
            ),
            Event(
                {
                    "event_id": "1",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu1"}],
                    "ip": "10.0.0.1",
                    "severity": 2,
                    "dedupe_keys": ["alert_name", "tags.device", "ip"],
                }
            ),
        ]
        processor = AlertBuilder()
        result = processor.save_events(events)

        self.assertEqual(2, len(result))
        self.assertEqual(2, len(documents))
        self.assertEqual(events[0].id, documents[0].id)
        self.assertEqual(events[1].id, documents[1].id)

    @mock.patch("bkmonitor.documents.base.BaseDocument.bulk_create")
    def test_save_events__duplicate(self, bulk_create):
        documents = []

        def mock_bulk_create(docs, *args, **kwargs):
            documents.extend(docs)

        bulk_create.side_effect = mock_bulk_create

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504100,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "ip": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "tags.device", "ip"],
                }
            )
        ] * 10
        processor = AlertBuilder()
        result = processor.save_events(events)

        self.assertEqual(1, len(result))
        self.assertEqual(1, len(documents))
        self.assertEqual(events[0].id, documents[0].id)

    @mock.patch("bkmonitor.documents.base.BaseDocument.bulk_create")
    def test_save_events__error(self, bulk_create):
        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504100,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "ip": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "tags.device", "ip"],
                }
            )
        ]

        def mock_bulk_create(docs, *args, **kwargs):
            raise BulkIndexError(
                "1 document(s) failed to index.",
                [{"create": {"_index": "fta-test", "_type": "_doc", "_id": events[0].id, "status": 409}}],
            )

        bulk_create.side_effect = mock_bulk_create

        processor = AlertBuilder()
        result = processor.save_events(events)

        self.assertEqual(0, len(result))

    @mock.patch("bkmonitor.documents.base.BaseDocument.bulk_create")
    def test_save_alerts(self, bulk_create):
        documents = []

        def mock_bulk_create(docs, *args, **kwargs):
            documents.extend(docs)

        bulk_create.side_effect = mock_bulk_create

        alert = Alert(
            {
                "id": "test update alert cache",
                "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
                "end_time": None,
                "create_time": 1617504052,
                "begin_time": 1617504052,
                "latest_time": 1617504052,
                "first_anomaly_time": 1617504052,
                "status": "ABNORMAL",
                "severity": 0,
                "labels": ["TEST"],
            }
        )
        alert._refresh_db = True
        processor = AlertBuilder()
        alerts = processor.save_alerts([alert])
        self.assertEqual(1, len(alerts))
        self.assertEqual(1, len(documents))
        self.assertEqual(alert.id, documents[0].id)
        self.assertEqual(alert.labels, documents[0].labels)

    def test_update_alert_cache(self):
        older_alert = Alert(
            {
                "id": "test update alert cache --- old",
                "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
                "end_time": None,
                "create_time": 1617504000,
                "first_anomaly_time": 1617504052,
                "begin_time": 1617504052,
                "latest_time": 1617504052,
                "status": "ABNORMAL",
                "severity": 0,
                "strategy_id": 123,
            }
        )

        alert = Alert(
            {
                "id": "test update alert cache",
                "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
                "end_time": None,
                "create_time": 1617504020,
                "begin_time": 1617504052,
                "first_anomaly_time": 1617504052,
                "latest_time": 1617504052,
                "status": "ABNORMAL",
                "severity": 0,
                "strategy_id": 123,
            }
        )

        processor = AlertBuilder()
        processor.update_alert_cache([older_alert, alert])

        result = ALERT_DEDUPE_CONTENT_KEY.client.get(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id, dedupe_md5=alert.dedupe_md5)
        )
        self.assertIsNotNone(result)

        new_alert = json.loads(result)
        self.assertEqual(alert.id, new_alert["id"])

    def test_update_alert_cache_with_snapshot(self):
        alert = Alert(
            {
                "id": "test update alert cache",
                "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
                "end_time": None,
                "begin_time": 1617504052,
                "first_anomaly_time": 1617504052,
                "latest_time": 1617504052,
                "status": "RECOVERED",
                "severity": 0,
                "strategy_id": 124,
            }
        )

        processor = AlertBuilder()
        processor.update_alert_snapshot([alert])

        result = ALERT_SNAPSHOT_KEY.client.get(
            ALERT_SNAPSHOT_KEY.get_key(strategy_id=alert.strategy_id, alert_id=alert.id)
        )
        self.assertIsNotNone(result)

        new_alert = json.loads(result)
        self.assertEqual(alert.id, new_alert["id"])

    def test_empty_data(self):
        processor = AlertBuilder()

        self.assertEqual([], processor.save_events([]))
        self.assertEqual([], processor.build_alerts([]))
        self.assertEqual([], processor.save_alerts([]))
        self.assertEqual((0, 0), processor.update_alert_cache([]))
        self.assertEqual(0, processor.update_alert_snapshot([]))

    @staticmethod
    def get_alert_processor(event_data=None):
        processor = AlertBuilder()

        event = {
            "event_id": "2",
            "bk_biz_id": 2,
            "plugin_id": "fta-test",
            "alert_name": "CPU usage high",
            "time": int(time.time()),
            "tags": [{"key": "device", "value": "cpu0"}],
            "severity": 1,
            "target_type": "host",
            "target": "10.0.0.1|0",
            "dedupe_keys": ["alert_name", "tags.device", "target_type", "target"],
            "extra_info": {},
        }
        if event_data:
            event.update(event_data)
        alerts = processor.build_alerts([Event(event)])
        return processor, alerts

    def test_enrich_alerts(self):
        processor, alerts = self.get_alert_processor()
        alerts = processor.enrich_alerts(alerts)
        self.assertEqual(1, len(alerts))
        alert = alerts[0]

        target_dimension = [d for d in alert.dimensions if d["key"] == "tags.device"][0]
        self.assertEqual("tags.device", target_dimension.get("key"))
        self.assertEqual("cpu0", target_dimension.get("value"))
        self.assertEqual("tags.device", target_dimension.get("display_key"))
        self.assertEqual("cpu0", target_dimension.get("display_value"))

    def test_enrich_kubernetes_alerts(self):
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [
                {"data": [{"code": 200, "source_type": "pod", "target_list": [{"bk_target_ip": "127.0.0.1"}]}]}
            ]
            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "dedupe_keys": ["alert_name", "tags.device", "target_type", "target", "tags.bcs_cluster_id"],
                }
            )

            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}
            self.assertTrue("ip" in dimensions)
            self.assertEqual("127.0.0.1", dimensions["ip"])
            self.assertEqual(0, dimensions["bk_cloud_id"])

    def test_enrich_kubernetes_alerts_notin_white_biz_list(self):
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [
                {"data": [{"code": 200, "source_type": "pod", "target_list": [{"bk_target_ip": "127.0.0.1"}]}]}
            ]
            settings.KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST = [3]
            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "extra_info": {"agg_dimensions": ["bcs_cluster_id"]},
                }
            )
            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}
            # 没有在灰度列表中，不进行丰富
            self.assertFalse("ip" in dimensions)
            settings.KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST = []

    def test_enrich_kubernetes_alerts_without_biz_ip(self):
        # 没有对应业务下ip， 将不会做丰富
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [
                {"data": [{"code": 200, "source_type": "pod", "target_list": [{"bk_target_ip": "127.0.0.1"}]}]}
            ]
            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "bk_biz_id": 3,
                    "extra_info": {"agg_dimensions": ["bcs_cluster_id"]},
                }
            )
            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}
            self.assertFalse("ip" in dimensions)

    def test_enrich_kubernetes_alerts_multi_targets(self):
        # 返回多个IP， 以第一个能够确定ip和云区域的IP进行确认
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [
                {
                    "data": [
                        {
                            "code": 200,
                            "source_type": "pod",
                            "target_list": [{"bk_target_ip": "127.0.0.2"}, {"bk_target_ip": "127.0.0.1"}],
                        }
                    ]
                }
            ]

            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "extra_info": {"agg_dimensions": ["bcs_cluster_id"]},
                    "dedupe_keys": ["alert_name", "tags.device", "target_type", "target", "tags.bcs_cluster_id"],
                }
            )
            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}
            self.assertTrue("ip" in dimensions)
            self.assertEqual("127.0.0.1", dimensions["ip"])
            self.assertEqual(0, dimensions["bk_cloud_id"])

    def test_enrich_kubernetes_alerts_with_multi_ip(self):
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [
                {"data": [{"code": 200, "source_type": "pod", "target_list": [{"bk_target_ip": "127.0.0.2"}]}]}
            ]

            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "category": KubernetesResultTableLabel.kubernetes,
                }
            )
            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}
            # 存在多个ip，所以不会进行主机IP丰富
            self.assertFalse("ip" in dimensions)
            self.assertFalse("bk_cloud_id" in dimensions)

    def test_enrich_kubernetes_alerts_no_ip(self):
        with mock.patch("bkmonitor.utils.thread_backend.ThreadPool.map_ignore_exception") as relation_mock:
            relation_mock.return_value = [{"data": [{"code": 404}]}]
            processor, alerts = self.get_alert_processor(
                {
                    "target_type": "",
                    "target": "",
                    "category": KubernetesResultTableLabel.kubernetes,
                }
            )
            alerts = processor.enrich_alerts(alerts)
            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            dimensions = {d["key"]: d["value"] for d in alert.dimensions}

            # 返回404， 没有ip，所以不会进行主机IP丰富
            self.assertFalse("ip" in dimensions)
            self.assertFalse("bk_cloud_id" in dimensions)

    def test_save_labels(self):
        alert = Alert.from_event(
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "10.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                    "extra_info": {"strategy": {"labels": ["TEST"]}},
                }
            )
        )
        self.assertCountEqual(alert.labels, ["TEST"])

    def test_save_agg_dimensions(self):
        processor = AlertBuilder()

        events = [
            Event(
                {
                    "event_id": "2",
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": int(time.time()),
                    "tags": [{"key": "bk_cloud_id", "value": "0"}, {"key": "bk_target_ip", "value": "127.0.0.1"}],
                    "severity": 1,
                    "target_type": "host",
                    "target": "10.0.0.1|0",
                    "dedupe_keys": ["alert_name", "tags.bk_cloud_id", "tags.bk_target_ip", "target_type", "target"],
                    "extra_info": {
                        "strategy": {
                            "items": [
                                {
                                    "query_configs": [
                                        {"agg_dimension": ["bk_target_ip"]},
                                        {"agg_dimension": ["bk_target_ip", "bk_cloud_id"]},
                                    ],
                                }
                            ]
                        }
                    },
                }
            )
        ]
        alerts = processor.build_alerts(events)
        alerts = processor.enrich_alerts(alerts)
        self.assertCountEqual(alerts[0].agg_dimensions, ["bk_target_ip", "bk_cloud_id"])
        self.assertCountEqual([d["key"][5:] for d in alerts[0].dimensions], ["bk_target_ip", "bk_cloud_id"])

    def test_send_signal(self):
        processor = AlertBuilder()
        processor.send_signal(
            [
                Alert.from_event(
                    Event(
                        {
                            "event_id": "2",
                            "plugin_id": "fta-test",
                            "alert_name": "CPU usage high",
                            "time": 1617504052,
                            "tags": [{"key": "device", "value": "cpu0"}],
                            "severity": 1,
                            "target": "10.0.0.1",
                            "dedupe_keys": ["alert_name", "target"],
                        }
                    )
                ),
                Alert.from_event(
                    Event(
                        {
                            "strategy_id": 1,
                            "event_id": "2",
                            "plugin_id": "fta-test",
                            "alert_name": "CPU usage high",
                            "time": 1617504052,
                            "tags": [{"key": "device", "value": "cpu0"}],
                            "severity": 1,
                            "target": "10.0.0.1",
                            "dedupe_keys": ["alert_name", "target"],
                        }
                    )
                ),
            ]
        )

    @mock.patch("alarm_backends.service.composite.tasks.check_action_and_composite.delay")
    def test_alert_qos(self, composite_patch):
        block_alerts = []
        normal_alerts = []
        for i in range(settings.QOS_ALERT_THRESHOLD):
            alert = Alert.from_event(
                Event(
                    {
                        "strategy_id": 1,
                        "event_id": f"{i}",
                        "plugin_id": "fta-test",
                        "alert_name": "CPU usage high",
                        "time": 1617504052,
                        "tags": [{"key": "device", "value": "cpu0"}],
                        "severity": 1,
                        "target": f"127.0.0.{i}",
                        "dedupe_keys": ["alert_name", "target"],
                    }
                )
            )
            if alert.is_blocked:
                block_alerts.append(alert)
            else:
                normal_alerts.append(alert)

        # 条件内满足，不会被kill掉
        self.assertEqual(0, len(block_alerts))

        for i in range(4):
            alert = Alert.from_event(
                Event(
                    {
                        "strategy_id": 1,
                        "event_id": f"{i}",
                        "plugin_id": "fta-test",
                        "alert_name": "CPU usage high",
                        "time": 1617504052,
                        "tags": [{"key": "device", "value": "cpu0"}],
                        "severity": 1,
                        "target": f"127.0.{i}.1",
                        "dedupe_keys": ["alert_name", "target"],
                    }
                )
            )
            if alert.is_blocked:
                block_alerts.append(alert)
            else:
                normal_alerts.append(alert)

        # 条件不满足，4个告警被阻塞
        self.assertEqual(4, len(block_alerts))

        builder = AlertBuilder()

        builder.send_signal(normal_alerts)
        self.assertEqual(composite_patch.call_count, len(normal_alerts))

        builder.send_signal(block_alerts)
        self.assertEqual(composite_patch.call_count, len(normal_alerts))

    def test_alert_qos_unblocked(self):
        alert = Alert.from_event(
            Event(
                {
                    "strategy_id": 1,
                    "event_id": 1,
                    "plugin_id": "fta-test",
                    "alert_name": "CPU usage high",
                    "time": 1617504052,
                    "tags": [{"key": "device", "value": "cpu0"}],
                    "severity": 1,
                    "target": "127.0.0.1",
                    "dedupe_keys": ["alert_name", "target"],
                }
            )
        )
        self.assertFalse(alert.is_blocked)

        alert.update_qos_status(True)
        alert._is_new = False
        alert = AlertBuilder().alert_qos_handle(alert)
        self.assertEqual(alert.status, "CLOSED")
