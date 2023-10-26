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

from django.test import TestCase

from alarm_backends.core.alert import Alert
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.cache.key import ALERT_DEDUPE_CONTENT_KEY
from alarm_backends.service.alert.manager.processor import AlertManager
from bkmonitor.models import CacheNode


class TestProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        ALERT_DEDUPE_CONTENT_KEY.client.flushall()
        CacheNode.refresh_from_settings()

    @classmethod
    def tearDownClass(cls):
        ALERT_DEDUPE_CONTENT_KEY.client.flushall()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_list_alerts_from_snapshot(self):
        alert = Alert(
            {
                "id": "4444555666",
                "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
                "end_time": None,
                "create_time": 1617504052,
                "begin_time": 1617504052,
                "first_anomaly_time": 1617504052,
                "latest_time": 1617504052,
                "status": "ABNORMAL",
                "severity": 0,
                "event": {"id": "event-1"},
                "strategy_id": 333,
            }
        )
        alert_key = AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)
        processor = AlertManager([alert_key])
        self.assertIsNone(Alert.get_from_snapshot(alert_key))
        processor.update_alert_snapshot([alert])

        snapshot_alert = Alert.get_from_snapshot(alert_key)
        self.assertIsNotNone(snapshot_alert)
        self.assertEqual(snapshot_alert.id, alert.id)
