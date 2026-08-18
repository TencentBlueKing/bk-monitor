"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
import json
import time

import arrow
from unittest import mock
import pytest
from django.test import TestCase

import settings
from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache import key
from alarm_backends.core.cache.key import (
    ALERT_DEDUPE_CONTENT_KEY,
    LAST_CHECKPOINTS_CACHE_KEY,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.storage.redis_cluster import routed_client
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from alarm_backends.service.alert.manager.checker.utils import terminate_new_series_lifecycle_state
from alarm_backends.service.detect.strategy.new_series import NewSeries
from alarm_backends.tests.service.alert.manager.checker import ANOMALY_EVENT, STRATEGY
from api.cmdb.define import Host, ServiceInstance, TopoNode
from bkmonitor.documents import AlertLog
from bkmonitor.models import CacheNode
from constants.alert import EventStatus

pytestmark = pytest.mark.django_db


class TestCloseStatusChecker(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self) -> None:
        CacheNode.refresh_from_settings()
        LAST_CHECKPOINTS_CACHE_KEY.client.flushall()
        check_time = arrow.now().replace(seconds=-200).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(STRATEGY)
        )

        self.host_manager_patch = mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
        self.host_manager = self.host_manager_patch.start()
        self.host_manager.get.return_value = Host(
            bk_host_innerip="10.0.0.1",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
        )

    def tearDown(self) -> None:
        self.host_manager_patch.stop()

    @classmethod
    def get_alert(cls, strategy=None, event=None):
        event = MonitorEventAdapter(event or ANOMALY_EVENT, strategy or STRATEGY).adapt()
        event["extra_info"]["strategy"] = strategy or STRATEGY
        event["ip"] = "10.0.0.1"
        event["bk_cloud_id"] = "1"
        alert = Alert.from_event(Event(event))
        ALERT_DEDUPE_CONTENT_KEY.client.set(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id, dedupe_md5=alert.dedupe_md5),
            json.dumps(alert.to_dict()),
        )
        return alert

    @staticmethod
    def new_series_strategy():
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["algorithms"] = [
            {
                "type": "NewSeries",
                "level": 2,
                "config": {
                    "detect_range": 60,
                    "effective_delay": 60,
                    "max_series": 100000,
                    "threshold": 0,
                    "alert_mode": "continuous",
                },
            }
        ]
        return strategy

    @staticmethod
    def new_series_state_keys():
        params = {
            "strategy_id": 1,
            "item_id": 1,
            "dimension_signature": NewSeries.signature_from_agg_dimension(["ip", "bk_cloud_id"]),
            "threshold": 0,
            "detect_range": 60,
            "level": 2,
        }
        return (
            NewSeries.active_state_key(**params),
            NewSeries.claimed_state_key(**params),
            NewSeries.terminated_state_key(**params),
        )

    def test_set_closed(self):
        alert = self.get_alert()
        CloseStatusChecker.close(alert, "测试关闭")
        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertEqual(alert.logs[-1]["description"], "测试关闭")
        self.assertEqual(alert.logs[-1]["op_type"], AlertLog.OpType.CLOSE)

    def test_blocked_lifecycle_check_skips_circuit_close(self):
        alert = self.get_alert()
        latest_strategy = mock.Mock()
        latest_strategy.config = copy.deepcopy(STRATEGY)
        latest_strategy.items = []
        latest_strategy.in_alarm_time.return_value = (True, "")
        checker = CloseStatusChecker([alert])

        with (
            mock.patch("alarm_backends.service.alert.manager.checker.close.Strategy", return_value=latest_strategy),
            mock.patch.object(checker, "check_event_expired", return_value=False),
            mock.patch.object(checker, "check_circuit_breaking", return_value=True) as check_circuit_breaking,
            mock.patch.object(checker, "check_strategy_changed", return_value=False),
            mock.patch.object(checker, "check_target_not_included", return_value=False),
            mock.patch.object(checker, "check_no_data", return_value=False),
            mock.patch.object(checker, "check_priority", return_value=False),
        ):
            self.assertFalse(checker.check(alert, skip_circuit_breaking=True))

        check_circuit_breaking.assert_not_called()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_strategy_metric_changed(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["metric_id"] = "bk_monitor.system.cpu_detail.usage"
        alert = self.get_alert(strategy)
        checker = CloseStatusChecker([alert])
        checker.check_all()

        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_deleted(self):
        StrategyCacheManager.cache.delete(StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]))
        alert = self.get_alert()
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_deleted_terminates_new_series_continuous_lifecycle(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, claimed_key, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        key.NEW_SERIES_CLAIMED_KEY.client.zadd(claimed_key, {fingerprint: 1980})
        StrategyCacheManager.cache.delete(StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy["id"]))

        CloseStatusChecker([alert]).check_all()

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertIsNone(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint))
        self.assertIsNone(key.NEW_SERIES_CLAIMED_KEY.client.zscore(claimed_key, fingerprint))
        self.assertIsNotNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_strategy_deleted_retries_when_new_series_lifecycle_termination_fails(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        StrategyCacheManager.cache.delete(StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy["id"]))

        with mock.patch(
            "alarm_backends.service.alert.manager.checker.utils.terminate_new_series_lifecycle_state",
            side_effect=RuntimeError("redis timeout"),
        ):
            CloseStatusChecker([alert]).check_all()

        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_strategy_switches_new_series_to_once_terminates_continuous_lifecycle(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, claimed_key, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        key.NEW_SERIES_CLAIMED_KEY.client.zadd(claimed_key, {fingerprint: 1980})
        latest_strategy = copy.deepcopy(strategy)
        latest_strategy["items"][0]["algorithms"][0]["config"]["alert_mode"] = "once"
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy["id"]),
            json.dumps(latest_strategy),
        )

        CloseStatusChecker([alert]).check_all()

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertIsNone(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint))
        self.assertIsNone(key.NEW_SERIES_CLAIMED_KEY.client.zscore(claimed_key, fingerprint))
        self.assertIsNotNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_strategy_new_series_lifecycle_group_change_closes_alert(self):
        for config_name, value in (("detect_range", 120), ("threshold", 1)):
            with self.subTest(config_name=config_name):
                strategy = self.new_series_strategy()
                alert = self.get_alert(strategy)
                latest_strategy = copy.deepcopy(strategy)
                latest_strategy["items"][0]["algorithms"][0]["config"][config_name] = value

                self.assertTrue(CloseStatusChecker([alert]).check_strategy_changed(alert, latest_strategy))
                self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_new_series_capacity_change_keeps_alert_active(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        latest_strategy = copy.deepcopy(strategy)
        latest_strategy["items"][0]["algorithms"][0]["config"]["max_series"] = 1

        self.assertFalse(CloseStatusChecker([alert]).check_strategy_changed(alert, latest_strategy))
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_blocked_alert_timeout_terminates_new_series_continuous_lifecycle(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, claimed_key, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        key.NEW_SERIES_CLAIMED_KEY.client.zadd(claimed_key, {fingerprint: 1980})
        alert.data.update(
            {
                "is_blocked": True,
                "next_status": EventStatus.CLOSED,
                "next_status_time": int(time.time()) - 1,
            }
        )

        self.assertTrue(alert.move_to_next_status())

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertIsNone(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint))
        self.assertIsNone(key.NEW_SERIES_CLAIMED_KEY.client.zscore(claimed_key, fingerprint))
        self.assertIsNotNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_new_series_lifecycle_termination_retries_when_detector_renews_first(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, _, terminated_key = self.new_series_state_keys()
        client = key.NEW_SERIES_ACTIVE_KEY.client
        client.zadd(active_key, {fingerprint: 1990})

        with routed_client(client, active_key) as active_client:
            first = active_client.pipeline(transaction=True)
            second = active_client.pipeline(transaction=True)
            original_zscore = first.zscore

            def read_then_detector_renews(*args, **kwargs):
                score = original_zscore(*args, **kwargs)
                client.zadd(active_key, {fingerprint: 2000})
                return score

            with (
                mock.patch.object(first, "zscore", side_effect=read_then_detector_renews),
                mock.patch.object(active_client, "pipeline", side_effect=[first, second]),
            ):
                self.assertTrue(terminate_new_series_lifecycle_state(alert, observed_at=2061))

        self.assertIsNone(client.zscore(active_key, fingerprint))
        self.assertEqual(int(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint)), 2061)

    def test_expired_older_alert_preserves_new_series_lifecycle_owned_by_newer_alert(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, _, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        dedupe_key = ALERT_DEDUPE_CONTENT_KEY.get_key(
            strategy_id=alert.strategy_id,
            dedupe_md5=alert.dedupe_md5,
        )
        current_alert = json.loads(ALERT_DEDUPE_CONTENT_KEY.client.get(dedupe_key))
        current_alert["id"] = f"{alert.id}-newer"
        ALERT_DEDUPE_CONTENT_KEY.client.set(dedupe_key, json.dumps(current_alert))

        self.assertTrue(CloseStatusChecker([alert]).check_event_expired(alert))

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertEqual(int(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint)), 1990)
        self.assertIsNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_expired_older_alert_does_not_transfer_lifecycle_to_terminated_newer_alert(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, _, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        dedupe_key = ALERT_DEDUPE_CONTENT_KEY.get_key(
            strategy_id=alert.strategy_id,
            dedupe_md5=alert.dedupe_md5,
        )
        current_alert = json.loads(ALERT_DEDUPE_CONTENT_KEY.client.get(dedupe_key))
        current_alert["id"] = f"{alert.id}-newer"
        current_alert["status"] = EventStatus.CLOSED
        ALERT_DEDUPE_CONTENT_KEY.client.set(dedupe_key, json.dumps(current_alert))

        self.assertTrue(CloseStatusChecker([alert]).check_event_expired(alert))

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertIsNone(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint))
        self.assertIsNotNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_expired_older_alert_terminates_lifecycle_not_owned_by_newer_alert(self):
        strategy = self.new_series_strategy()
        alert = self.get_alert(strategy)
        fingerprint = "55a76cf628e46c04a052f4e19bdb9dbf"
        active_key, _, terminated_key = self.new_series_state_keys()
        key.NEW_SERIES_ACTIVE_KEY.client.zadd(active_key, {fingerprint: 1990})
        dedupe_key = ALERT_DEDUPE_CONTENT_KEY.get_key(
            strategy_id=alert.strategy_id,
            dedupe_md5=alert.dedupe_md5,
        )
        current_alert = json.loads(ALERT_DEDUPE_CONTENT_KEY.client.get(dedupe_key))
        current_alert["id"] = f"{alert.id}-newer"
        current_alert["extra_info"]["strategy"]["items"][0]["algorithms"][0]["config"]["alert_mode"] = "once"
        ALERT_DEDUPE_CONTENT_KEY.client.set(dedupe_key, json.dumps(current_alert))

        self.assertTrue(CloseStatusChecker([alert]).check_event_expired(alert))

        self.assertEqual(alert.status, EventStatus.CLOSED)
        self.assertIsNone(key.NEW_SERIES_ACTIVE_KEY.client.zscore(active_key, fingerprint))
        self.assertIsNotNone(key.NEW_SERIES_TERMINATED_KEY.client.zscore(terminated_key, fingerprint))

    def test_strategy_dimension_changed(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["agg_dimension"] = ["ip"]
        alert = self.get_alert(strategy)
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_condition_changed(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["agg_condition"] = [
            {"key": "bk_target_ip", "value": ["10.1.1.1"], "method": "eq", "condition": "and"}
        ]

        # 有数据告警的情况
        alert = self.get_alert(strategy)
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

        # 无数据告警的情况
        new_event = copy.deepcopy(ANOMALY_EVENT)
        new_event["data"]["dimensions"]["__NO_DATA_DIMENSION__"] = True
        alert = self.get_alert(event=new_event, strategy=strategy)
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_nodata_expired(self):
        strategy = copy.deepcopy(STRATEGY)
        # 无数据告警的情况
        new_event = copy.deepcopy(ANOMALY_EVENT)
        new_event["data"]["dimensions"]["__NO_DATA_DIMENSION__"] = True
        new_event["data"]["time"] = int((datetime.datetime.now() - datetime.timedelta(days=2)).timestamp())
        alert = self.get_alert(event=new_event, strategy=strategy)
        settings.NO_DATA_ALERT_EXPIRED_TIMEDELTA = 24 * 60 * 60
        alert.top_event["target_type"] = ""
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_level_deleted(self):
        new_strategy = copy.deepcopy(STRATEGY)
        new_strategy["detects"] = []
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )
        alert = self.get_alert()
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_level_changed(self):
        new_strategy = copy.deepcopy(STRATEGY)
        for detect in new_strategy["detects"]:
            detect["level"] = 1
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=new_strategy["id"]), json.dumps(new_strategy)
        )
        alert = self.get_alert()
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_no_data_alarm(self):
        new_strategy = copy.deepcopy(STRATEGY)
        new_strategy["items"][0]["no_data_config"]["is_enabled"] = False

        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )

        new_event = copy.deepcopy(ANOMALY_EVENT)
        new_event["data"]["dimensions"]["__NO_DATA_DIMENSION__"] = True

        alert = self.get_alert(event=new_event)
        self.assertEqual("[无数据] test", alert.alert_name)
        self.assertTrue(alert.is_no_data())
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_strategy_no_data_alarm_not_closed(self):
        new_strategy = copy.deepcopy(STRATEGY)
        new_strategy["items"][0]["no_data_config"]["is_enabled"] = True

        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )

        new_event = copy.deepcopy(ANOMALY_EVENT)
        new_event["data"]["dimensions"]["__NO_DATA_DIMENSION__"] = True

        alert = self.get_alert(event=new_event)
        self.assertTrue(alert.is_no_data())
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    def test_no_data_in_30_minutes_close(self):
        alert = self.get_alert()
        alert.top_event["target_type"] = ""

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

        check_time = arrow.now().replace(seconds=-310 - 30 * 60).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        checker.check_all()
        self.assertEqual(EventStatus.CLOSED, alert.status)

    def test_with_big_window_unit_no_closed(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["agg_interval"] = 11 * 60
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert(strategy)
        alert.top_event["target_type"] = ""

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

        # 汇聚周期为11分钟，检测无数据时间应该是 5个周期 * 11分钟， 55分钟之内存在数据即表示不关闭
        check_time = arrow.now().replace(seconds=-40 * 60).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )

        checker.check_all()
        self.assertEqual(EventStatus.ABNORMAL, alert.status)

    def test_no_data_with_big_window_unit_close(self):
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["query_configs"][0]["agg_interval"] = 11 * 60
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert(strategy)
        alert.top_event["target_type"] = ""

        # 汇聚周期为11分钟，检测无数据时间应该是 5个周期 * 11分钟， 55分钟之内不存在数据即表示关闭
        check_time = arrow.now().replace(seconds=-56 * 60).timestamp
        LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=1),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5="55a76cf628e46c04a052f4e19bdb9dbf",
                level=2,
            ),
            check_time,
        )
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(EventStatus.CLOSED, alert.status)

    def test_not_timeseries_event(self):
        new_strategy = copy.deepcopy(STRATEGY)
        new_strategy["items"][0]["data_type_label"] = "event"

        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(new_strategy)
        )

        alert = self.get_alert()
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
    def test_host_target_included(self, HostManager):
        HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.1",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
        )

        alert = self.get_alert()
        alert.top_event["ip"] = "10.0.0.1"
        alert.top_event["bk_cloud_id"] = 0
        alert.top_event["target"] = "10.0.0.1|0"
        alert.top_event["target_type"] = "HOST"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
    def test_host_target_not_found(self, HostManager):
        HostManager.get.return_value = None
        alert = self.get_alert()
        alert.top_event["ip"] = "10.0.0.1"
        alert.top_event["bk_cloud_id"] = 0
        alert.top_event["target"] = "10.0.0.1|0"
        alert.top_event["target_type"] = "HOST"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
    def test_host_target_not_included(self, HostManager):
        HostManager.get.return_value = None
        alert = self.get_alert()
        alert.top_event["ip"] = "10.0.0.1"
        alert.top_event["bk_cloud_id"] = 0
        alert.top_event["target"] = "10.0.0.1|0"
        alert.top_event["target_type"] = "HOST"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
    def test_topo_target_included(self, HostManager):
        HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.2",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
            topo_link={
                "module|16": [{"bk_obj_id": "module", "bk_inst_id": 16}, {"bk_obj_id": "set", "bk_inst_id": 13}],
                "module|28": [{"bk_obj_id": "module", "bk_inst_id": 28}, {"bk_obj_id": "set", "bk_inst_id": 26}],
            },
        )
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["target"][0][0] = {
            "field": "host_topo_node",
            "method": "eq",
            "value": [{"bk_inst_id": 28, "bk_obj_id": "module"}, {"bk_inst_id": 13, "bk_obj_id": "set"}],
        }
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert()
        alert.top_event["ip"] = "10.0.0.2"
        alert.top_event["bk_cloud_id"] = 0
        alert.top_event["target"] = "10.0.0.2|0"
        alert.top_event["target_type"] = "HOST"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.HostManager")
    def test_topo_target_not_included(self, HostManager):
        HostManager.get.return_value = HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.2",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
            topo_link={
                "module|16": [{"bk_obj_id": "module", "bk_inst_id": 16}, {"bk_obj_id": "set", "bk_inst_id": 13}],
                "module|28": [{"bk_obj_id": "module", "bk_inst_id": 28}, {"bk_obj_id": "set", "bk_inst_id": 26}],
            },
        )
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["target"][0][0] = {
            "field": "host_topo_node",
            "method": "eq",
            "value": [{"bk_inst_id": 26, "bk_obj_id": "module"}, {"bk_inst_id": 12, "bk_obj_id": "set"}],
        }
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert()
        alert.top_event["ip"] = "10.0.0.2"
        alert.top_event["bk_cloud_id"] = 0
        alert.top_event["target"] = "10.0.0.2|0"
        alert.top_event["target_type"] = "HOST"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.ServiceInstanceManager")
    def test_service_target_included(self, ServiceInstanceManager):
        ServiceInstanceManager.get.return_value = ServiceInstance(
            123,
            topo_link={
                "module|16": [TopoNode("module", 16), TopoNode("set", 13)],
                "module|28": [TopoNode("module", 28), TopoNode("set", 26)],
            },
        )
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["target"][0][0] = {
            "field": "service_topo_node",
            "method": "eq",
            "value": [{"bk_inst_id": 28, "bk_obj_id": "module"}, {"bk_inst_id": 13, "bk_obj_id": "set"}],
        }
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert()
        alert.top_event["bk_service_instance_id"] = "123"
        alert.top_event["target"] = "123"
        alert.top_event["target_type"] = "SERVICE"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.ServiceInstanceManager")
    def test_service_target_topo_included(self, ServiceInstanceManager):
        ServiceInstanceManager.get.return_value = ServiceInstance(
            2,
            topo_link={
                "module|16": [TopoNode("module", 16), TopoNode("set", 13)],
                "module|28": [TopoNode("module", 28), TopoNode("set", 26)],
            },
        )
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["target"][0][0] = {
            "field": "service_topo_node",
            "method": "eq",
            "value": [{"bk_inst_id": 26, "bk_obj_id": "module"}, {"bk_inst_id": 12, "bk_obj_id": "set"}],
        }
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert()
        alert.top_event["bk_service_instance_id"] = "2"
        alert.top_event["target"] = "2"
        alert.top_event["target_type"] = "SERVICE"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    @mock.patch("alarm_backends.service.alert.manager.checker.close.ServiceInstanceManager")
    def test_service_target_not_found(self, ServiceInstanceManager):
        ServiceInstanceManager.get.return_value = None
        strategy = copy.deepcopy(STRATEGY)
        strategy["items"][0]["target"][0][0] = {
            "field": "service_topo_node",
            "method": "eq",
            "value": [{"bk_inst_id": 26, "bk_obj_id": "module"}, {"bk_inst_id": 12, "bk_obj_id": "set"}],
        }
        StrategyCacheManager.cache.set(
            StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(strategy)
        )
        alert = self.get_alert()
        alert.top_event["bk_service_instance_id"] = "123"
        alert.top_event["target"] = "123"
        alert.top_event["target_type"] = "SERVICE"

        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_expired_event(self):
        alert = self.get_alert()
        new_alert = self.get_alert()
        content_key = ALERT_DEDUPE_CONTENT_KEY.get_key(
            strategy_id=new_alert.strategy_id, dedupe_md5=new_alert.dedupe_md5
        )
        ALERT_DEDUPE_CONTENT_KEY.client.set(content_key, json.dumps(new_alert.to_dict()))
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.CLOSED)

    def test_expired_event__none(self):
        alert = self.get_alert()
        new_alert = self.get_alert()
        content_key = ALERT_DEDUPE_CONTENT_KEY.get_key(
            strategy_id=new_alert.strategy_id, dedupe_md5=new_alert.dedupe_md5
        )
        ALERT_DEDUPE_CONTENT_KEY.client.delete(content_key)
        checker = CloseStatusChecker([alert])
        checker.check_all()
        self.assertEqual(alert.status, EventStatus.ABNORMAL)
