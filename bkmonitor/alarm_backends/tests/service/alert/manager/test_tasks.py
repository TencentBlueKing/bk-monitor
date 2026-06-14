"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.test import TestCase
from elasticsearch.exceptions import TransportError
from elasticsearch.helpers.errors import ScanError
from redis.exceptions import ConnectionError as RedisConnectionError

from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.service.alert.manager import tasks
from core.prometheus import metrics


class TestHandleAlertsMetrics(TestCase):
    """
    handle_alerts 指标归类: 瞬态基础设施失败(本批未 finalize、下周期重跑)计入 deferred,
    非瞬态(逻辑类)异常仍计 failed, 避免一次节点抖动 / ES 瞬态被批级放大成整批 failed、压垮成功率指标。
    """

    @staticmethod
    def _keys(n):
        return [AlertKey(alert_id=str(1000 + i), strategy_id=1) for i in range(n)]

    @staticmethod
    def _success():
        return metrics.ALERT_MANAGE_COUNT.labels(status="success", exception=None)._value.get()

    @staticmethod
    def _failed(exception):
        return metrics.ALERT_MANAGE_COUNT.labels(status="failed", exception=exception)._value.get()

    @staticmethod
    def _deferred(exception):
        return metrics.ALERT_MANAGE_DEFERRED_COUNT.labels(exception=exception)._value.get()

    def _run(self, keys, side_effect=None):
        # 隔离 DB/Redis: 用 mock 替换 AlertManager, 仅驱动 process 的成功/异常分支;
        # mock report_all 避免其 push 后 clear_data 把待断言的计数清零。
        with mock.patch.object(tasks, "AlertManager") as MockManager:
            with mock.patch.object(tasks.metrics, "report_all"):
                manager = MockManager.return_value
                if side_effect is not None:
                    manager.process.side_effect = side_effect
                else:
                    manager.process.return_value = None
                tasks.handle_alerts(alert_keys=keys)

    def test_success_counts_success_only(self):
        keys = self._keys(3)
        s0, d0 = self._success(), self._deferred("ConnectionError")
        self._run(keys)
        self.assertEqual(self._success() - s0, 3)
        self.assertEqual(self._deferred("ConnectionError") - d0, 0)

    def test_redis_connection_error_counts_deferred_not_failed(self):
        keys = self._keys(5)
        d0, f0 = self._deferred("ConnectionError"), self._failed("ConnectionError")
        self._run(keys, side_effect=RedisConnectionError("server closed connection"))
        self.assertEqual(self._deferred("ConnectionError") - d0, 5)
        self.assertEqual(self._failed("ConnectionError") - f0, 0)

    def test_es_scan_error_counts_deferred(self):
        keys = self._keys(2)
        d0 = self._deferred("ScanError")
        self._run(keys, side_effect=ScanError("scroll-id", "Scroll request has only succeeded on 2 shards out of 9"))
        self.assertEqual(self._deferred("ScanError") - d0, 2)

    def test_es_transport_error_counts_deferred(self):
        keys = self._keys(2)
        d0 = self._deferred("TransportError")
        self._run(keys, side_effect=TransportError(500, "search_phase_execution_exception", "too many scroll contexts"))
        self.assertEqual(self._deferred("TransportError") - d0, 2)

    def test_logic_error_counts_failed_not_deferred(self):
        # 非瞬态(逻辑类)异常不应被漂白成 deferred, 须保留 failed 可见性。
        keys = self._keys(4)
        f0, d0 = self._failed("IndexError"), self._deferred("IndexError")
        self._run(keys, side_effect=IndexError("list index out of range"))
        self.assertEqual(self._failed("IndexError") - f0, 4)
        self.assertEqual(self._deferred("IndexError") - d0, 0)

    def test_empty_alert_keys_short_circuits(self):
        s0 = self._success()
        with mock.patch.object(tasks, "AlertManager") as MockManager:
            with mock.patch.object(tasks.metrics, "report_all"):
                tasks.handle_alerts(alert_keys=[])
                MockManager.assert_not_called()
        self.assertEqual(self._success() - s0, 0)
