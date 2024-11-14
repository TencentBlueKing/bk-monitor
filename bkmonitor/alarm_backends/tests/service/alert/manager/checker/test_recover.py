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

import arrow
import pytest
from django.test import TestCase
from six.moves import range

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache.key import (
    CHECK_RESULT_CACHE_KEY,
    LAST_CHECKPOINTS_CACHE_KEY,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.context import ActionContext
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from alarm_backends.service.alert.manager.checker.recover import RecoverStatusChecker
from alarm_backends.tests.service.alert.manager.checker import ANOMALY_EVENT, STRATEGY
from bkmonitor.documents import AlertLog
from bkmonitor.models import CacheNode
from constants.alert import EventStatus

pytestmark = pytest.mark.django_db


def _set_recovery_with_event_id(event_id, timedelta=1000):
    check_time = arrow.now().replace(seconds=-timedelta).timestamp
    LAST_CHECKPOINTS_CACHE_KEY.client.hset(
        LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
        LAST_CHECKPOINTS_CACHE_KEY.get_field(
            dimensions_md5=event_id,
            level=2,
        ),
        check_time,
    )

    cache_key = CHECK_RESULT_CACHE_KEY.get_key(
        strategy_id=1,
        item_id=1,
        dimensions_md5=event_id,
        level=2,
    )
    for i in range(9):
        ts = check_time - 60 * i
        CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})


class TestRecoverStatusChecker(TestCase):
    databases = {"monitor_api", "default"}

    def clear_data(self):
        LAST_CHECKPOINTS_CACHE_KEY.client.flushall()
        CHECK_RESULT_CACHE_KEY.client.flushall()

    def setUp(self) -> None:
        CacheNode.refresh_from_settings()
        self.clear_data()

    def tearDown(self) -> None:
        self.clear_data()

    @classmethod
    def get_alert(cls, strategy=None, event=None):
        event = MonitorEventAdapter(event or ANOMALY_EVENT, strategy or STRATEGY).adapt()
        event["extra_info"]["strategy"] = strategy or STRATEGY
        alert = Alert.from_event(Event(event))
        return alert

    def test_set_recovered(self):
        alert = self.get_alert()
        RecoverStatusChecker.recover(alert, "测试恢复")
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        self.assertEqual(alert.logs[-1]["description"], "测试恢复")
        self.assertEqual(alert.logs[-1]["op_type"], AlertLog.OpType.RECOVER)

        alert = self.get_alert()
        RecoverStatusChecker.recover(alert, "测试关闭", "close")
        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertEqual(alert.logs[-1]["description"], "测试关闭")
        self.assertEqual(alert.logs[-1]["op_type"], AlertLog.OpType.CLOSE)

    def test_has_recovered(self):
        alert = self.get_alert()
        RecoverStatusChecker.recover(alert, "测试恢复")

        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)

    def test_anomaly_record_not_exist(self):
        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)

    def test_has_trigger(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i < 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_is_recovering(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i > 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)
        self.assertTrue(alert.get_extra_info("is_recovering"))
        self.assertEqual(alert.logs[-1]["op_type"], AlertLog.OpType.RECOVERING)

    def test_has_trigger2(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i % 2 == 0:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_has_trigger3(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert()
        alert.update_extra_info("is_recovering", True)
        alert.update_extra_info("ignore_unshield_notice", True)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)
        self.assertFalse(alert.get_extra_info("is_recovering"))
        self.assertFalse(alert.get_extra_info("ignore_unshield_notice"))
        self.assertTrue(alert.get_extra_info("need_unshield_notice"))
        self.assertTrue(alert.should_refresh_db())
        self.assertEqual(alert.logs[-1]["op_type"], AlertLog.OpType.ABORT_RECOVER)

    def test_has_no_trigger(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i < 1:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        self.assertEqual(alert.get_extra_info("is_recovering"), True)
        self.assertEqual(alert.get_extra_info("end_description"), "连续 5 个周期不满足触发条件，告警已恢复，当前值为0%")

    def test_has_no_trigger_multi_metrics(self):
        multi_strategy = copy.deepcopy(STRATEGY)
        # 五个周期满足四次则触发告警
        multi_strategy["detects"][1]["trigger_config"]["count"] = 4
        multi_strategy["items"][0]["query_configs"].insert(
            0,
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
        )
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for size in range(2):
            for i in range(5):
                ts = check_time - 60
                if i > 1:
                    # 配置一个过期的数据
                    CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
                else:
                    CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})
                check_time = ts
        alert = self.get_alert(multi_strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        self.assertEqual(alert.get_extra_info("is_recovering"), True)
        self.assertEqual(alert.get_extra_info("end_description"), "连续 5 个周期不满足触发条件，告警已恢复，当前值为0%")

        # 汇聚周期较大的情况下，五个周期满足4次，告警不恢复
        multi_strategy["items"][0]["query_configs"].pop(1)
        alert = self.get_alert(multi_strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_has_no_trigger2(self):
        check_time = arrow.now().replace(seconds=-500).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i % 5 == 0:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        self.assertEqual(alert.get_extra_info("end_description"), "连续 5 个周期不满足触发条件，告警已恢复，当前值为0%")

        context = ActionContext(action=0, alerts=[alert.to_document()])
        self.assertEqual(context.alarm.end_description, "连续 5 个周期不满足触发条件，告警已恢复，当前值为0%")
        self.assertEqual(context.content.content, "内容: 连续 5 个周期不满足触发条件，告警已恢复，当前值为0%")

    def test_check_no_data_true(self):
        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        self.assertEqual(alert.get_extra_info("end_description"), "在恢复检测周期内无数据上报，告警已恢复")

    def test_check_no_data_false(self):
        check_time = arrow.now().replace(seconds=-200).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i < 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_data_report_no_delay(self):
        check_time = arrow.now().replace(seconds=-200).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(8):
            ts = check_time - 60 * i
            if i < 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})
            else:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|0".format(ts): ts})

        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_data_report_delay(self):
        """
        数据上报有延迟的时候, 恢复检测讲以最近的数据上报点为结束点，以最近上报时间向前推 恢复配置周期+触发周期 的时间范围为起点
        """
        _set_recovery_with_event_id("55a76cf628e46c04a052f4e19bdb9dbf")
        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        #  以数据上报的时间点作为恢复检测时间，数据延迟不影响告警恢复
        self.assertEqual(alert.status, EventStatus.RECOVERED)

    def test_close_alert_without_data(self):
        """
        数据上报有延迟的时候, 恢复检测讲以最近的数据上报点为结束点，以最近上报时间向前推 恢复配置周期+触发周期 的时间范围为起点
        """
        # 40分钟以前存在过数据
        _set_recovery_with_event_id("55a76cf628e46c04a052f4e19bdb9dbf", timedelta=40 * 60)
        alert = self.get_alert()
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        # 获取不到数据点，默认返回False， 由close检测进行关闭
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

        checker = CloseStatusChecker([alert])
        checker.check_all()
        # 检测到最近30分钟之前没有数据点，直接关闭
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_recover_for_event_true(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["data_type_label"] = "event"

        check_time = arrow.now().replace(seconds=-900).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i < 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert(strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)

    def test_recover_for_event_false(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["data_type_label"] = "event"

        check_time = arrow.now().replace(seconds=-200).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 60 * i
            if i < 3:
                CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert(strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_event_type_big_window_unit_false(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["data_type_label"] = "event"
        strategy["items"][0]["query_configs"][0]["data_source_label"] = "custom"
        strategy["items"][0]["query_configs"][0]["agg_interval"] = 300
        strategy["detects"][1] = {
            "expression": "",
            "level": 2,
            "connector": "and",
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "trigger_config": {"count": 1, "check_window": 1},
        }
        # 一个周期之前写入的数据
        check_time = arrow.now().replace(seconds=-300 - 60).timestamp
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 300 * i
            CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert(strategy=strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)
        # 当前告警为大周期， 1个周期安之前存在数据点，最近周期还未统计，所以不应该是恢复
        self.assertIsNone(alert.get_extra_info("is_recovering"))

    def test_event_type_big_window_unit_recovering(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["data_type_label"] = "event"
        strategy["items"][0]["query_configs"][0]["agg_interval"] = 300
        strategy["detects"][1] = {
            "expression": "",
            "level": 2,
            "connector": "and",
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "trigger_config": {"count": 1, "check_window": 1},
        }
        # 一个周期之前写入的数据
        check_time = arrow.now().replace(seconds=-600 - 60).timestamp
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 300 * i
            CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert(strategy=strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)
        # 当前告警为大周期， 2个周期安之前存在最后一个数据点，最近周期还未统计，所以不应该是恢复
        self.assertTrue(alert.get_extra_info("is_recovering"))

    def test_event_type_big_window_unit_recovered(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["data_type_label"] = "event"
        strategy["items"][0]["query_configs"][0]["agg_interval"] = 300
        strategy["detects"][1] = {
            "expression": "",
            "level": 2,
            "connector": "and",
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "trigger_config": {"count": 1, "check_window": 1},
        }
        # 恢复期窗口 + 触发器窗口 6个周期之前写入的数据， 此时满足恢复条件
        check_time = arrow.now().replace(seconds=-300 * 6).timestamp
        cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=1,
            item_id=1,
            dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
            level=2,
        )
        for i in range(20):
            ts = check_time - 300 * i
            CHECK_RESULT_CACHE_KEY.client.zadd(cache_key, {"{}|ANOMALY".format(ts): ts})

        alert = self.get_alert(strategy=strategy)
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
        # 当前告警为大周期， 2个周期安之前存在最后一个数据点，最近周期还未统计，所以不应该是恢复
        self.assertTrue(alert.get_extra_info("is_recovering"))

    def test_strategy_no_data_alarm_recovered(self):
        new_strategy = copy.deepcopy(STRATEGY)
        new_strategy["items"][0]["no_data_config"]["is_enabled"] = True

        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )

        new_event = copy.deepcopy(ANOMALY_EVENT)
        new_event["data"]["dimensions"]["__NO_DATA_DIMENSION__"] = True

        alert = self.get_alert(event=new_event)
        self.assertTrue(alert.is_no_data())
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)

    def test_strategy_recovered_by_status_setter(self):
        new_strategy = copy.deepcopy(STRATEGY)
        for detect in new_strategy["detects"]:
            detect["recovery_config"]["status_setter"] = "recovery-nodata"
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )
        new_event = copy.deepcopy(ANOMALY_EVENT)

        alert = self.get_alert(event=new_event)
        self.assertFalse(alert.is_no_data())
        checker = RecoverStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.RECOVERED)
