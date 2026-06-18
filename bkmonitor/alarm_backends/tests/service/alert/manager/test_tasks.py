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

from django.db.utils import OperationalError as DjangoOperationalError
from django.test import TestCase
from elasticsearch.exceptions import ConnectionTimeout, RequestError, TransportError
from elasticsearch.helpers.errors import ScanError
from kombu.exceptions import OperationalError as KombuOperationalError
from redis.exceptions import BusyLoadingError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import DataError, ReadOnlyError, ResponseError

from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.storage.redis_cluster import PipelineResultMismatch
from alarm_backends.service.alert.manager import tasks
from core.prometheus import metrics


class TestHandleAlertsMetrics(TestCase):
    """
    handle_alerts 指标归类：仅"下一周期重跑可自愈"的瞬态基础设施异常计 deferred；代码 / 数据 / 配置类
    错误(不会自愈)仍计 failed，避免把真实逻辑故障漂白成 deferred、从成功率口径里抹掉。
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
        # 隔离 DB/Redis：mock 替换 AlertManager，仅驱动 process 的成功 / 异常分支；
        # mock report_all 避免其 push 后 clear_data 把待断言的计数清零。
        with mock.patch.object(tasks, "AlertManager") as MockManager:
            with mock.patch.object(tasks.metrics, "report_all"):
                manager = MockManager.return_value
                if side_effect is not None:
                    manager.process.side_effect = side_effect
                else:
                    manager.process.return_value = None
                tasks.handle_alerts(alert_keys=keys)

    def _assert_deferred(self, exc, exc_name, n=3):
        """异常 exc 应计入 deferred(n 条)，不计 failed。"""
        keys = self._keys(n)
        d0, f0 = self._deferred(exc_name), self._failed(exc_name)
        self._run(keys, side_effect=exc)
        self.assertEqual(self._deferred(exc_name) - d0, n, f"{exc_name} 应计 deferred")
        self.assertEqual(self._failed(exc_name) - f0, 0, f"{exc_name} 不应计 failed")

    def _assert_failed(self, exc, exc_name, n=3):
        """异常 exc 应计入 failed(n 条)，不被漂白成 deferred。"""
        keys = self._keys(n)
        f0, d0 = self._failed(exc_name), self._deferred(exc_name)
        self._run(keys, side_effect=exc)
        self.assertEqual(self._failed(exc_name) - f0, n, f"{exc_name} 应计 failed")
        self.assertEqual(self._deferred(exc_name) - d0, 0, f"{exc_name} 不应漂白成 deferred")

    def test_success_counts_success_only(self):
        keys = self._keys(3)
        s0, d0 = self._success(), self._deferred("ConnectionError")
        self._run(keys)
        self.assertEqual(self._success() - s0, 3)
        self.assertEqual(self._deferred("ConnectionError") - d0, 0)

    # ---- 瞬态可恢复 → deferred ----
    def test_redis_connection_error_deferred(self):
        self._assert_deferred(RedisConnectionError("server closed connection"), "ConnectionError")

    def test_redis_busyloading_error_deferred(self):
        # BusyLoadingError 是 ConnectionError 子类(实例重启后载入数据)，可自愈
        self._assert_deferred(BusyLoadingError("Redis is loading the dataset in memory"), "BusyLoadingError")

    def test_redis_readonly_error_deferred(self):
        # 主从切换后从节点只读，客户端重定向后可恢复
        self._assert_deferred(ReadOnlyError("READONLY You can't write against a read only replica"), "ReadOnlyError")

    def test_pipeline_result_mismatch_deferred(self):
        self._assert_deferred(PipelineResultMismatch("result count mismatch"), "PipelineResultMismatch")

    def test_es_scan_error_deferred(self):
        self._assert_deferred(
            ScanError("scroll-id", "Scroll request has only succeeded on 2 shards out of 9"), "ScanError"
        )

    def test_es_transport_429_deferred(self):
        self._assert_deferred(TransportError(429, "circuit_breaking_exception"), "TransportError")

    def test_es_transport_5xx_deferred(self):
        self._assert_deferred(
            TransportError(503, "search_phase_execution_exception", "too many scroll contexts"), "TransportError"
        )

    def test_es_connection_timeout_deferred(self):
        self._assert_deferred(ConnectionTimeout("TIMEOUT", "connection timed out"), "ConnectionTimeout")

    def test_kombu_broker_operational_error_deferred(self):
        # Celery broker(RabbitMQ/AMQP)建连/通道超时等可恢复连接错误，本批 finalize 前抛出，重跑可自愈
        self._assert_deferred(KombuOperationalError("timed out"), "OperationalError")

    # ---- 非瞬态(代码 / 数据 / 配置) → failed，不得漂白 ----
    def test_redis_response_error_failed(self):
        # WRONGTYPE / 错误命令等服务端响应错，不会靠重跑自愈
        self._assert_failed(
            ResponseError("WRONGTYPE Operation against a key holding the wrong kind of value"), "ResponseError"
        )

    def test_redis_data_error_failed(self):
        # 传给 redis 的数据非法，代码 / 数据问题
        self._assert_failed(DataError("Invalid input of type"), "DataError")

    def test_es_transport_4xx_failed(self):
        # 400 查询写错等客户端错误，重跑不恢复
        self._assert_failed(RequestError(400, "parsing_exception", "bad query"), "RequestError")

    def test_logic_error_failed(self):
        self._assert_failed(IndexError("list index out of range"), "IndexError")

    def test_django_db_operational_error_failed(self):
        # 与 kombu broker 同名(都叫 OperationalError)，但 DB(MySQL)操作错按类型匹配不归 broker 瞬态，
        # 仍计 failed、不被漂白；锁定按异常类型(而非类名字符串)区分的语义。
        self._assert_failed(DjangoOperationalError("(2006, 'MySQL server has gone away')"), "OperationalError")

    def test_empty_alert_keys_short_circuits(self):
        s0 = self._success()
        with mock.patch.object(tasks, "AlertManager") as MockManager:
            with mock.patch.object(tasks.metrics, "report_all"):
                tasks.handle_alerts(alert_keys=[])
                MockManager.assert_not_called()
        self.assertEqual(self._success() - s0, 0)
