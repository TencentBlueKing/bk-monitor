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

    def _run(self, keys, side_effect=None, finalized=False):
        # 隔离 DB/Redis：mock 替换 AlertManager，仅驱动 process 的成功 / 异常分支；
        # mock report_all 避免其 push 后 clear_data 把待断言的计数清零。
        # finalized 模拟 AlertManager.alerts_finalized(save_alerts 是否已完成)，供 handle_alerts 分阶段归类。
        with mock.patch.object(tasks, "AlertManager") as MockManager:
            with mock.patch.object(tasks.metrics, "report_all"):
                manager = MockManager.return_value
                manager.alerts_finalized = finalized
                if side_effect is not None:
                    manager.process.side_effect = side_effect
                else:
                    manager.process.return_value = None
                tasks.handle_alerts(alert_keys=keys)

    def _assert_deferred(self, exc, exc_name, n=3, finalized=False):
        """异常 exc 应计入 deferred(n 条)，不计 failed。"""
        keys = self._keys(n)
        d0, f0 = self._deferred(exc_name), self._failed(exc_name)
        self._run(keys, side_effect=exc, finalized=finalized)
        self.assertEqual(self._deferred(exc_name) - d0, n, f"{exc_name} 应计 deferred")
        self.assertEqual(self._failed(exc_name) - f0, 0, f"{exc_name} 不应计 failed")

    def _assert_failed(self, exc, exc_name, n=3, finalized=False):
        """异常 exc 应计入 failed(n 条)，不被漂白成 deferred。"""
        keys = self._keys(n)
        f0, d0 = self._failed(exc_name), self._deferred(exc_name)
        self._run(keys, side_effect=exc, finalized=finalized)
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

    def test_kombu_broker_error_before_finalize_deferred(self):
        # broker 建连/通道超时发生在 finalize 前(check_all 的 create_actions.delay)，本批未落库，重跑可自愈
        self._assert_deferred(KombuOperationalError("timed out"), "OperationalError", finalized=False)

    # ---- 非瞬态(代码 / 数据 / 配置) → failed，不得漂白 ----
    def test_kombu_broker_error_after_finalize_failed(self):
        # 同一 broker 异常若发生在 finalize 后(send_signal)，告警状态已落库、终态不会被下周期重发 signal，
        # 属实际丢 signal 的失败，必须计 failed、不得漂白成 deferred。
        self._assert_failed(KombuOperationalError("timed out"), "OperationalError", finalized=True)

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


class TestBlockedAlertLifecycle(TestCase):
    @staticmethod
    def make_locked_context():
        lock = mock.Mock()
        lock.is_locked.return_value = True
        lock_context = mock.MagicMock()
        lock_context.__enter__.return_value = lock
        lock_context.__exit__.return_value = False
        return lock_context

    @staticmethod
    def make_blocked_alert():
        alert = mock.Mock()
        alert.id = "blocked-alert"
        alert.strategy_id = 1
        alert.dedupe_md5 = "dedupe-md5"
        alert.status = "ABNORMAL"
        alert.is_blocked = True
        alert.is_abnormal.return_value = True
        alert.should_refresh_db.return_value = False
        return alert

    def test_periodic_scan_includes_long_lived_blocked_alerts(self):
        search = mock.Mock()
        search.filter.return_value = search
        search.source.return_value = search

        with (
            mock.patch.object(tasks.AlertDocument, "search", return_value=search) as build_search,
            mock.patch.object(tasks, "get_cluster_bk_biz_ids", return_value=[]),
            mock.patch.object(tasks, "_search_after_hits", return_value=[]),
        ):
            tasks.check_blocked_alert()

        build_search.assert_called_once_with(all_indices=True)

    def test_timeout_rechecks_terminal_conditions_and_successor_ownership_under_alert_lock(self):
        alert = mock.Mock()
        alert.id = "blocked-alert"
        alert.strategy_id = 1
        alert.dedupe_md5 = "dedupe-md5"
        alert.status = "ABNORMAL"
        alert.is_abnormal.return_value = True
        alert.should_refresh_db.return_value = False
        lock = mock.Mock()
        lock.is_locked.return_value = True
        lock_context = mock.MagicMock()
        lock_context.__enter__.return_value = lock
        lock_context.__exit__.return_value = False

        with (
            mock.patch.object(tasks.Alert, "mget", return_value=[alert]),
            mock.patch.object(tasks, "multi_service_lock", return_value=lock_context, create=True) as acquire_lock,
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=True) as check_close,
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)])

        acquire_lock.assert_called_once()
        check_close.assert_called_once_with(alert, skip_circuit_breaking=True)
        alert.move_to_next_status.assert_not_called()

    def test_timeout_stops_when_close_checker_finishes_alert_without_truthy_result(self):
        alert = mock.Mock()
        alert.id = "blocked-alert"
        alert.strategy_id = 1
        alert.dedupe_md5 = "dedupe-md5"
        alert.status = "ABNORMAL"
        alert.is_abnormal.side_effect = [True, False]
        alert.should_refresh_db.return_value = False

        with (
            mock.patch.object(tasks.Alert, "mget", return_value=[alert]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=None),
            mock.patch.object(tasks.RecoverStatusChecker, "check_new_series_lifecycle") as check_lifecycle,
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)])

        check_lifecycle.assert_not_called()
        alert.move_to_next_status.assert_not_called()

    def test_timeout_reloads_same_alert_after_acquiring_alert_lock(self):
        stale_alert = mock.Mock()
        stale_alert.id = "blocked-alert"
        stale_alert.strategy_id = 1
        stale_alert.dedupe_md5 = "dedupe-md5"
        stale_alert.status = "ABNORMAL"
        stale_alert.is_abnormal.return_value = True
        stale_alert.should_refresh_db.return_value = False

        current_alert = mock.Mock()
        current_alert.id = stale_alert.id
        current_alert.strategy_id = stale_alert.strategy_id
        current_alert.dedupe_md5 = stale_alert.dedupe_md5
        current_alert.status = "ABNORMAL"
        current_alert.is_abnormal.return_value = True
        current_alert.should_refresh_db.return_value = False

        lock = mock.Mock()
        lock.is_locked.return_value = True
        lock_context = mock.MagicMock()
        lock_context.__enter__.return_value = lock
        lock_context.__exit__.return_value = False

        with (
            mock.patch.object(tasks.Alert, "mget", side_effect=[[stale_alert], [current_alert]]) as load_alerts,
            mock.patch.object(tasks, "multi_service_lock", return_value=lock_context, create=True),
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=False),
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=stale_alert.id, strategy_id=stale_alert.strategy_id)])

        self.assertEqual(load_alerts.call_count, 2)
        stale_alert.move_to_next_status.assert_not_called()
        current_alert.move_to_next_status.assert_called_once_with()

    def test_timeout_keeps_active_continuous_new_series_alert(self):
        alert = self.make_blocked_alert()
        alert.check_circuit_breaking.return_value = True
        latest_strategy = {"id": alert.strategy_id}

        with (
            mock.patch.object(tasks.Alert, "mget", return_value=[alert]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=False),
            mock.patch.object(tasks.StrategyCacheManager, "get_strategy_by_id", return_value=latest_strategy),
            mock.patch(
                "alarm_backends.service.alert.manager.checker.recover.RecoverStatusChecker.check_new_series_lifecycle",
                return_value=True,
            ) as check_lifecycle,
            mock.patch.object(tasks.AlertManager, "send_signal") as send_signal,
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)])

        check_lifecycle.assert_called_once_with(alert, latest_strategy)
        alert.check_circuit_breaking.assert_called_once()
        alert.qos_check.assert_not_called()
        alert.update_qos_status.assert_not_called()
        send_signal.assert_not_called()
        alert.move_to_next_status.assert_not_called()

    def test_timeout_keeps_active_continuous_new_series_alert_when_qos_still_blocks(self):
        alert = self.make_blocked_alert()
        alert.check_circuit_breaking.return_value = False
        alert.qos_check.return_value = {"is_blocked": True, "message": "仍被流控"}
        latest_strategy = {"id": alert.strategy_id}

        with (
            mock.patch.object(tasks.Alert, "mget", return_value=[alert]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=False),
            mock.patch.object(tasks.StrategyCacheManager, "get_strategy_by_id", return_value=latest_strategy),
            mock.patch.object(tasks.RecoverStatusChecker, "check_new_series_lifecycle", return_value=True),
            mock.patch.object(tasks.AlertManager, "send_signal") as send_signal,
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)])

        alert.check_circuit_breaking.assert_called_once()
        alert.qos_check.assert_called_once_with()
        alert.update_qos_status.assert_not_called()
        send_signal.assert_not_called()
        alert.move_to_next_status.assert_not_called()

    def test_timeout_releases_active_continuous_new_series_alert_and_sends_signal(self):
        alert = self.make_blocked_alert()
        alert.key = AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)
        alert.should_refresh_db.return_value = True
        alert.to_document.return_value = {"id": alert.id}
        alert.list_log_documents.return_value = []
        alert.check_circuit_breaking.return_value = False
        alert.qos_check.return_value = {"is_blocked": False, "message": "告警流控已解除"}
        alert.update_qos_status.side_effect = lambda is_blocked: setattr(alert, "is_blocked", is_blocked)
        latest_strategy = {"id": alert.strategy_id}

        with (
            mock.patch.object(tasks.Alert, "mget", return_value=[alert]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check", return_value=False),
            mock.patch.object(tasks.StrategyCacheManager, "get_strategy_by_id", return_value=latest_strategy),
            mock.patch.object(tasks.RecoverStatusChecker, "check_new_series_lifecycle", return_value=True),
            mock.patch.object(tasks.AlertDocument, "bulk_create"),
            mock.patch.object(tasks.AlertCache, "save_alert_to_cache"),
            mock.patch.object(tasks.AlertCache, "save_alert_snapshot"),
            mock.patch("alarm_backends.service.alert.processor.check_action_and_composite.delay") as send_signal,
        ):
            tasks.check_blocked_alert_finished([AlertKey(alert_id=alert.id, strategy_id=alert.strategy_id)])

        alert.check_circuit_breaking.assert_called_once()
        alert.qos_check.assert_called_once_with()
        alert.update_qos_status.assert_called_once_with(False)
        alert.add_log.assert_called_once()
        send_signal.assert_called_once_with(alert_key=alert.key, alert_status=alert.status)
        alert.move_to_next_status.assert_not_called()

    def test_timeout_ignores_alert_unblocked_while_waiting_for_lock(self):
        candidate_alert = mock.Mock()
        candidate_alert.id = "blocked-alert"
        candidate_alert.strategy_id = 1
        candidate_alert.dedupe_md5 = "dedupe-md5"

        unblocked_alert = mock.Mock()
        unblocked_alert.id = candidate_alert.id
        unblocked_alert.strategy_id = candidate_alert.strategy_id
        unblocked_alert.dedupe_md5 = candidate_alert.dedupe_md5
        unblocked_alert.is_blocked = False
        unblocked_alert.is_abnormal.return_value = True
        unblocked_alert.should_refresh_db.return_value = False

        with (
            mock.patch.object(tasks.Alert, "mget", side_effect=[[candidate_alert], [unblocked_alert]]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check") as check_close,
            mock.patch.object(tasks.AlertManager, "send_signal") as send_signal,
        ):
            tasks.check_blocked_alert_finished(
                [AlertKey(alert_id=candidate_alert.id, strategy_id=candidate_alert.strategy_id)]
            )

        check_close.assert_not_called()
        send_signal.assert_not_called()

    def test_timeout_ignores_alert_that_finished_while_waiting_for_lock(self):
        candidate_alert = mock.Mock()
        candidate_alert.id = "blocked-alert"
        candidate_alert.strategy_id = 1
        candidate_alert.dedupe_md5 = "dedupe-md5"

        finished_alert = mock.Mock()
        finished_alert.id = candidate_alert.id
        finished_alert.strategy_id = candidate_alert.strategy_id
        finished_alert.dedupe_md5 = candidate_alert.dedupe_md5
        finished_alert.is_abnormal.return_value = False

        with (
            mock.patch.object(tasks.Alert, "mget", side_effect=[[candidate_alert], [finished_alert]]),
            mock.patch.object(tasks, "multi_service_lock", return_value=self.make_locked_context()),
            mock.patch.object(tasks.CloseStatusChecker, "check") as check_close,
        ):
            tasks.check_blocked_alert_finished(
                [AlertKey(alert_id=candidate_alert.id, strategy_id=candidate_alert.strategy_id)]
            )

        check_close.assert_not_called()
        finished_alert.move_to_next_status.assert_not_called()
