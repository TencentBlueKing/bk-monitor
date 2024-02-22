# -*- coding: utf-8 -*-
import time

from django.conf import settings
from django.test import TestCase

from alarm_backends.core.alert import Event
from alarm_backends.service.alert.enricher import BizWhiteListFor3rdEvent


class TestBizWhiteListFor3rdEvent(TestCase):

    databases = {"monitor_api", "default"}

    def test_enrich(self):
        settings.BIZ_WHITE_LIST_FOR_3RD_EVENT = [2, 3, 4]
        time1 = int(time.time())
        event = Event(
            {
                "strategy_id": 2,
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "CPU usage high",
                "time": time1,
                "tags": [{"key": "device", "value": "cpu1"}],
                "target": "10.0.0.1",
                "severity": 1,
                "dedupe_keys": ["alert_name", "target"],
                "bk_biz_id": 2,
            }
        )
        self.assertFalse(event.is_dropped())
        new_event = BizWhiteListFor3rdEvent([event]).enrich()[0]
        self.assertFalse(new_event.is_dropped())

        settings.BIZ_WHITE_LIST_FOR_3RD_EVENT = []
        event = Event(
            {
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "CPU usage high",
                "time": time1,
                "tags": [{"key": "device", "value": "cpu1"}],
                "target": "10.0.0.1",
                "severity": 1,
                "dedupe_keys": ["alert_name", "target"],
                "bk_biz_id": 2,
            }
        )
        new_event = BizWhiteListFor3rdEvent([event]).enrich()[0]
        self.assertFalse(new_event.is_dropped())

        settings.BIZ_WHITE_LIST_FOR_3RD_EVENT = [3, 4]
        new_event = BizWhiteListFor3rdEvent([event]).enrich()[0]
        self.assertTrue(new_event.is_dropped())

        settings.BIZ_WHITE_LIST_FOR_3RD_EVENT = []
