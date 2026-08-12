# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from unittest import mock

from django.test import TestCase

from alarm_backends.core.alert.alert import Alert, AlertUIDManager
from bkmonitor.documents import AlertLog
from constants.alert import EventStatus


class TestAlertEndStatus(TestCase):
    @staticmethod
    def make_alert():
        return Alert(
            {
                "status": EventStatus.ABNORMAL,
                "severity": 1,
                "extra_info": {},
                "next_status": EventStatus.CLOSED,
                "next_status_time": int(time.time()) - 1,
            }
        )

    @mock.patch("alarm_backends.service.alert.manager.checker.utils.terminate_new_series_lifecycle_state")
    def test_set_end_status_terminates_new_series_lifecycle_by_default(self, terminate_lifecycle):
        alert = self.make_alert()

        alert.set_end_status(EventStatus.CLOSED, AlertLog.OpType.CLOSE)

        terminate_lifecycle.assert_called_once_with(alert)

    @mock.patch("alarm_backends.service.alert.manager.checker.utils.terminate_new_series_lifecycle_state")
    def test_set_end_status_can_preserve_transferred_new_series_lifecycle(self, terminate_lifecycle):
        alert = self.make_alert()

        alert.set_end_status(
            EventStatus.CLOSED,
            AlertLog.OpType.CLOSE,
            preserve_new_series_lifecycle=True,
        )

        terminate_lifecycle.assert_not_called()
        self.assertNotIn("preserve_new_series_lifecycle", alert.logs[-1])

    @mock.patch("alarm_backends.service.alert.manager.checker.utils.terminate_new_series_lifecycle_state")
    def test_blocked_alert_timeout_uses_lifecycle_aware_terminal_transition(self, terminate_lifecycle):
        alert = self.make_alert()
        alert.data["is_blocked"] = True

        self.assertTrue(alert.move_to_next_status())

        terminate_lifecycle.assert_called_once_with(alert)


class TestAlertUIDManager(TestCase):
    def setUp(self) -> None:
        AlertUIDManager.SEQUENCE_REDIS_KEY.client.flushall()
        AlertUIDManager.clear_pool()

    def tearDown(self) -> None:
        AlertUIDManager.SEQUENCE_REDIS_KEY.client.flushall()
        AlertUIDManager.clear_pool()

    def test_generate(self):
        ts = 1619840289  # s
        uid = AlertUIDManager.generate(ts)
        self.assertEqual("16198402891", uid)
        self.assertEqual(1619840289, AlertUIDManager.parse_timestamp(uid))
        self.assertEqual(1, AlertUIDManager.parse_sequence(uid))

        ts = 1619840290000  # ms
        uid = AlertUIDManager.generate(ts)
        self.assertEqual("16198402902", uid)
        self.assertEqual(1619840290, AlertUIDManager.parse_timestamp(uid))
        self.assertEqual(2, AlertUIDManager.parse_sequence(uid))

        ts = 161984029  # ms
        uid = AlertUIDManager.generate(ts)
        self.assertEqual("01619840293", uid)
        self.assertEqual(161984029, AlertUIDManager.parse_timestamp(uid))
        self.assertEqual(3, AlertUIDManager.parse_sequence(uid))

    def test_preload(self):
        AlertUIDManager.preload_pool()
        self.assertSetEqual({1}, AlertUIDManager.sequence_pool)
        seq = AlertUIDManager.pop_sequence()
        self.assertEqual(1, seq)
        seq = AlertUIDManager.pop_sequence()
        self.assertEqual(2, seq)

        AlertUIDManager.preload_pool(3)
        self.assertSetEqual({3, 4, 5}, AlertUIDManager.sequence_pool)

        AlertUIDManager.preload_pool(2)
        self.assertSetEqual({3, 4, 5}, AlertUIDManager.sequence_pool)

        AlertUIDManager.preload_pool(4)
        self.assertSetEqual({3, 4, 5, 6}, AlertUIDManager.sequence_pool)

        seq = AlertUIDManager.pop_sequence()
        self.assertEqual(3, seq)

        AlertUIDManager.preload_pool(4)
        self.assertSetEqual({4, 5, 6, 7}, AlertUIDManager.sequence_pool)
