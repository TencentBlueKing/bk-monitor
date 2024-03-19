# -*- coding: utf-8 -*-
import copy
from datetime import datetime

import mock
from django.test import TestCase

from alarm_backends.core.control.strategy import Strategy

STRATEGY = {
    "bk_biz_id": 2,
    "version": "v2",
    "items": [],
    "scenario": "os",
    "detects": [
        {
            "expression": "",
            "level": 1,
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {
                "count": 3,
                "check_window": 5,
                "uptime": {
                    "time_ranges": [
                        {"start": "06:00", "end": "10:00"},
                        {"start": "18:00", "end": "21:00"},
                        {"start": "23:00", "end": "04:00"},
                    ],
                    "calendars": [1, 2, 3],
                },
            },
        },
    ],
    "actions": [],
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}


class TestStrategy(TestCase):
    # @classmethod
    # def setUpClass(cls):
    #     cls.StrategyCacheManager = mock.patch("alarm_backends.core.control.strategy.StrategyCacheManager")
    #     StrategyCacheManager = cls.StrategyCacheManager.start()
    #     StrategyCacheManager.get_strategy_by_id.return_value = STRATEGY
    #
    # @classmethod
    # def tearDownClass(cls):
    #     cls.StrategyCacheManager.stop()

    def test_in_alarm_time__no_calendar(self):
        strategy = Strategy(1, STRATEGY)
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertFalse(strategy.in_alarm_time(datetime.strptime("2022-01-01 05:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 07:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertFalse(strategy.in_alarm_time(datetime.strptime("2022-01-01 12:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 19:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertFalse(strategy.in_alarm_time(datetime.strptime("2022-01-01 22:00:00", "%Y-%m-%d %H:%M:%S"))[0])
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 23:00:00", "%Y-%m-%d %H:%M:%S"))[0])

        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"] = []
        strategy = Strategy(1, strategy_config)
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 22:00:00", "%Y-%m-%d %H:%M:%S"))[0])

        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"][0]["trigger_config"]["uptime"]["time_ranges"] = []
        strategy = Strategy(1, strategy_config)
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 22:00:00", "%Y-%m-%d %H:%M:%S"))[0])

    @mock.patch("alarm_backends.core.control.strategy.CalendarCacheManager")
    def test_in_alarm_time__with_calendar(self, CalendarCacheManager):
        strategy = Strategy(1, STRATEGY)
        self.assertTrue(strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))[0])

        CalendarCacheManager.mget.return_value = [
            [],
            [
                {
                    'today': 1649833300,
                    'list': [
                        {
                            "id": 2,
                            "calendar_name": "测试日历",
                            "name": "放假1",
                            "start_time": 1649833200,
                            "end_time": 1649833800,
                            "update_user": "admin",
                            "update_time": 1649832487,
                            "create_time": 1649832487,
                            "create_user": "admin",
                            "calendar_id": 2,
                            "color": "#540ac0",
                            "repeat": {},
                            "parent_id": None,
                            "is_first": True,
                        }
                    ],
                }
            ],
            [],
        ]
        self.assertFalse(strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))[0])
