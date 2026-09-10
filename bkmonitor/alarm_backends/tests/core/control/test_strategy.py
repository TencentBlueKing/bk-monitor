import copy
from datetime import datetime

from unittest import mock
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
                    "active_calendars": [],
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
                    "today": 1649833300,
                    "list": [
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

    @mock.patch("alarm_backends.core.control.strategy.CalendarCacheManager")
    def test_in_alarm_time__with_active_calendar_only(self, CalendarCacheManager):
        """测试只配置生效日历的情况"""
        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"][0]["trigger_config"]["uptime"]["active_calendars"] = [4, 5]
        strategy_config["detects"][0]["trigger_config"]["uptime"]["calendars"] = []
        strategy = Strategy(1, strategy_config)

        # 模拟命中生效日历
        CalendarCacheManager.mget.return_value = [
            [
                {
                    "today": 1649833300,
                    "list": [
                        {
                            "id": 4,
                            "calendar_name": "告警日历",
                            "name": "重要活动保障",
                            "start_time": 1649833200,
                            "end_time": 1649833800,
                            "update_user": "admin",
                            "update_time": 1649832487,
                            "create_time": 1649832487,
                            "create_user": "admin",
                            "calendar_id": 4,
                            "color": "#ff0000",
                            "repeat": {},
                            "parent_id": None,
                            "is_first": True,
                        }
                    ],
                }
            ]
        ]
        result, message = strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertTrue(result)
        self.assertIn("告警日历事项", message)

        # 模拟未命中生效日历
        CalendarCacheManager.mget.return_value = [[]]
        result, message = strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertFalse(result)
        self.assertIn("未命中告警日历事项", message)

    @mock.patch("alarm_backends.core.control.strategy.CalendarCacheManager")
    def test_in_alarm_time__calendar_conflict(self, CalendarCacheManager):
        """测试生效日历和不生效日历冲突的情况"""
        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"][0]["trigger_config"]["uptime"]["active_calendar"] = [4]
        strategy_config["detects"][0]["trigger_config"]["uptime"]["calendars"] = [1]
        strategy = Strategy(1, strategy_config)

        # 模拟同时命中生效日历和不生效日历
        # 第一次调用返回生效日历，第二次调用返回不生效日历
        CalendarCacheManager.mget.side_effect = [
            # 第一次调用：生效日历返回值
            [
                [
                    {
                        "today": 1649833300,
                        "list": [
                            {
                                "id": 4,
                                "calendar_name": "告警日历",
                                "name": "紧急维护",
                                "start_time": 1649833200,
                                "end_time": 1649833800,
                                "update_user": "admin",
                                "update_time": 1649832487,
                                "create_time": 1649832487,
                                "create_user": "admin",
                                "calendar_id": 4,
                                "color": "#ff0000",
                                "repeat": {},
                                "parent_id": None,
                                "is_first": True,
                            }
                        ],
                    }
                ]
            ],
            # 第二次调用：不生效日历返回值
            [
                [
                    {
                        "today": 1649833300,
                        "list": [
                            {
                                "id": 1,
                                "calendar_name": "休息日历",
                                "name": "周末休息",
                                "start_time": 1649833200,
                                "end_time": 1649833800,
                                "update_user": "admin",
                                "update_time": 1649832487,
                                "create_time": 1649832487,
                                "create_user": "admin",
                                "calendar_id": 1,
                                "color": "#00ff00",
                                "repeat": {},
                                "parent_id": None,
                                "is_first": True,
                            }
                        ],
                    }
                ]
            ],
        ]

        result, message = strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertTrue(result)  # 生效日历优先，应该返回True
        self.assertIn("同时命中告警日历和休息日历，告警日历优先生效", message)
        self.assertIn("告警日历[告警日历(紧急维护)]", message)
        self.assertIn("休息日历[休息日历(周末休息)]", message)

    @mock.patch("alarm_backends.core.control.strategy.CalendarCacheManager")
    def test_in_alarm_time__active_calendar_miss_inactive_calendar_hit(self, CalendarCacheManager):
        """测试生效日历未命中，不生效日历命中的情况"""
        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"][0]["trigger_config"]["uptime"]["active_calendars"] = [4]
        strategy_config["detects"][0]["trigger_config"]["uptime"]["calendars"] = [1]
        strategy = Strategy(1, strategy_config)

        # 模拟生效日历未命中，不生效日历命中
        CalendarCacheManager.mget.side_effect = [
            # 第一次调用：生效日历返回值（空）
            [[]],
            # 第二次调用：不生效日历返回值
            [
                [
                    {
                        "today": 1649833300,
                        "list": [
                            {
                                "id": 1,
                                "calendar_name": "休息日历",
                                "name": "周末休息",
                                "start_time": 1649833200,
                                "end_time": 1649833800,
                                "update_user": "admin",
                                "update_time": 1649832487,
                                "create_time": 1649832487,
                                "create_user": "admin",
                                "calendar_id": 1,
                                "color": "#00ff00",
                                "repeat": {},
                                "parent_id": None,
                                "is_first": True,
                            }
                        ],
                    }
                ]
            ],
        ]

        result, message = strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertFalse(result)  # 不生效日历生效，应该返回False
        self.assertIn("命中日历休息事项", message)

    @mock.patch("alarm_backends.core.control.strategy.CalendarCacheManager")
    def test_in_alarm_time__active_calendar_configured_but_no_hit(self, CalendarCacheManager):
        """测试配置了生效日历但未命中任何事项的情况"""
        strategy_config = copy.deepcopy(STRATEGY)
        strategy_config["detects"][0]["trigger_config"]["uptime"]["active_calendars"] = [4]
        strategy_config["detects"][0]["trigger_config"]["uptime"]["calendars"] = []
        strategy = Strategy(1, strategy_config)

        # 模拟生效日历未命中任何事项
        CalendarCacheManager.mget.return_value = [[]]

        result, message = strategy.in_alarm_time(datetime.strptime("2022-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
        self.assertFalse(result)  # 配置了生效日历但未命中，应该返回False
        self.assertIn("未命中告警日历事项", message)


class TestStrategySnapshotNodeFallback(TestCase):
    """写入方按策略路由落节点，读取方常常只有一个普通字符串 key。

    分片环境下这两个落点不是同一个节点：CacheRouter 对没有 strategy_id 的
    key 直接返回默认节点。读取因此要先按路由读，取不到再读默认节点。
    """

    def setUp(self):
        self.reads = []

    def _client(self, present_on):
        client = mock.MagicMock()

        def get(snapshot_key):
            routed = getattr(snapshot_key, "strategy_id", 0)
            self.reads.append(routed)
            return '{"id": 1}' if routed == present_on else None

        client.get.side_effect = get
        return client

    def test_reads_the_routed_node_first(self):
        with mock.patch("alarm_backends.core.control.strategy.key") as cache_key:
            cache_key.SimilarStr = _SimilarStrStub
            cache_key.STRATEGY_SNAPSHOT_KEY.client = self._client(present_on=1001)
            snapshot = Strategy.get_strategy_snapshot_by_key("snapshot-key", 1001)
        self.assertEqual(snapshot, {"id": 1})
        self.assertEqual(self.reads, [1001])

    def test_falls_back_to_the_default_node(self):
        with mock.patch("alarm_backends.core.control.strategy.key") as cache_key:
            cache_key.SimilarStr = _SimilarStrStub
            cache_key.STRATEGY_SNAPSHOT_KEY.client = self._client(present_on=0)
            snapshot = Strategy.get_strategy_snapshot_by_key("snapshot-key", 1001)
        self.assertEqual(snapshot, {"id": 1})
        self.assertEqual(self.reads, [1001, 0])

    def test_absent_everywhere_returns_none(self):
        with mock.patch("alarm_backends.core.control.strategy.key") as cache_key:
            cache_key.SimilarStr = _SimilarStrStub
            cache_key.STRATEGY_SNAPSHOT_KEY.client = self._client(present_on=-1)
            snapshot = Strategy.get_strategy_snapshot_by_key("snapshot-key", 1001)
        self.assertIsNone(snapshot)
        self.assertEqual(self.reads, [1001, 0])

    def test_without_a_strategy_id_only_the_default_node_is_read(self):
        with mock.patch("alarm_backends.core.control.strategy.key") as cache_key:
            cache_key.SimilarStr = _SimilarStrStub
            cache_key.STRATEGY_SNAPSHOT_KEY.client = self._client(present_on=0)
            snapshot = Strategy.get_strategy_snapshot_by_key("snapshot-key")
        self.assertEqual(snapshot, {"id": 1})
        self.assertEqual(self.reads, [0])


class _SimilarStrStub(str):
    """复刻 cache.key.SimilarStr：带 strategy_id 属性的字符串。"""

    _strategy_id = 0

    @property
    def strategy_id(self):
        return self._strategy_id

    @strategy_id.setter
    def strategy_id(self, value):
        self._strategy_id = int(value)
