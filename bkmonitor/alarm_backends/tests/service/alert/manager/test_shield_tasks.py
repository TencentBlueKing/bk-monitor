"""独立屏蔽关闭任务：配置快照、分批、并发复读与部分写入失败。"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase, mock

import arrow
from elasticsearch.helpers import BulkIndexError

from alarm_backends.service.alert.manager import shield_tasks
from constants.alert import EventStatus


class TestShieldTasks(TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.mget = self.patch("Alert.mget")
        self.lock = self.patch("multi_service_lock").return_value.__enter__.return_value
        self.lock.is_locked.return_value = True
        self.configs = self.patch("Shield.origin_objects.in_bulk")
        self.save = self.patch("AlertDocument.bulk_create")
        self.cache = self.patch("AlertCache.update_alert_to_cache")
        self.snapshot = self.patch("AlertCache.save_alert_snapshot")
        self.logs = self.patch("AlertLog.bulk_create")
        self.patch("business_timezone").return_value = "UTC"

    def patch(self, name):
        return self.stack.enter_context(mock.patch(f"{shield_tasks.__name__}.{name}"))

    @staticmethod
    def alert(alert_id, shield_id=1):
        alert = mock.Mock()
        alert.id = str(alert_id)
        alert.dedupe_md5 = str(alert_id)
        alert.shield_end_close = True
        alert.is_abnormal.return_value = True
        alert.get_extra_info.return_value = {"shield_id": shield_id}
        alert.list_log_documents.return_value = [f"log-{alert_id}"]
        return alert

    @staticmethod
    def config(enabled=True, deleted=False, begin="2026-09-09T10:00:00Z", end="2026-09-09T11:00:00Z"):
        return SimpleNamespace(
            bk_biz_id=2,
            is_enabled=enabled,
            is_deleted=deleted,
            begin_time=arrow.get(begin).datetime,
            end_time=arrow.get(end).datetime,
            cycle_config={"type": 1},
        )

    def test_not_due_does_not_write(self):
        alert = self.alert(1)
        self.mget.return_value = [alert]
        self.configs.return_value = {1: self.config()}
        self.patch("arrow.now").return_value = arrow.get("2026-09-09T10:30:00Z")
        shield_tasks.check_shield_end_close_finished([alert.key])
        self.save.assert_not_called()
        self.cache.assert_not_called()
        alert.set_end_status.assert_not_called()

    def test_disabled_and_soft_deleted_close(self):
        for config in (self.config(enabled=False), self.config(deleted=True)):
            with self.subTest(config=config):
                alert = self.alert(1)
                self.mget.return_value = [alert]
                self.configs.return_value = {1: config}
                shield_tasks.check_shield_end_close_finished([alert.key])
                alert.set_end_status.assert_called_once_with(
                    EventStatus.CLOSED,
                    shield_tasks.AlertLog.OpType.CLOSE,
                    description="屏蔽结束，期间产生的告警已关闭",
                )
                self.cache.assert_called_with([alert])

    def test_reread_terminal_or_unmarked_is_skipped(self):
        for terminal in (True, False):
            before = self.alert(1)
            after = self.alert(1)
            after.is_abnormal.return_value = not terminal
            after.shield_end_close = terminal
            self.mget.side_effect = [[before], [after]]
            shield_tasks.check_shield_end_close_finished([before.key])
        self.configs.assert_not_called()
        self.save.assert_not_called()

    def test_lock_failure_does_not_process_candidate(self):
        alert = self.alert(1)
        self.lock.is_locked.return_value = False
        self.mget.side_effect = [[alert], []]
        shield_tasks.check_shield_end_close_finished([alert.key])
        self.configs.assert_not_called()
        self.save.assert_not_called()

    def test_invalid_time_config_keeps_alert(self):
        alert = self.alert(1)
        config = self.config()
        config.cycle_config = {"type": "invalid"}
        self.mget.return_value = [alert]
        self.configs.return_value = {1: config}
        shield_tasks.check_shield_end_close_finished([alert.key])
        alert.set_end_status.assert_not_called()
        self.save.assert_not_called()

    def test_missing_owner_is_not_treated_as_expired(self):
        alert = self.alert(1)
        self.mget.return_value = [alert]
        self.configs.return_value = {}
        shield_tasks.check_shield_end_close_finished([alert.key])
        self.save.assert_not_called()

    def test_config_read_failure_does_not_close(self):
        alert = self.alert(1)
        self.mget.return_value = [alert]
        self.configs.side_effect = RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            shield_tasks.check_shield_end_close_finished([alert.key])
        alert.set_end_status.assert_not_called()
        self.save.assert_not_called()

    def test_partial_bulk_failure_updates_successful_ids_only(self):
        first, second = self.alert(1), self.alert(2)
        self.mget.return_value = [first, second]
        self.configs.return_value = {1: self.config(enabled=False)}
        self.save.side_effect = BulkIndexError("failed", [{"update": {"_id": "2", "status": 429}}])
        shield_tasks.check_shield_end_close_finished([first.key, second.key])
        self.configs.assert_called_once_with({1})
        self.cache.assert_called_once_with([first])
        self.snapshot.assert_called_once_with([first])
        self.logs.assert_called_once_with(["log-1"])

    def test_current_time_config_overrides_initial_window(self):
        config = self.config(end="2026-09-09T12:00:00Z")
        self.assertTrue(shield_tasks.shield_is_active(config, arrow.get("2026-09-09T11:30:00Z")))
        self.assertFalse(shield_tasks.shield_is_active(config, arrow.get("2026-09-09T12:01:00Z")))

    def test_scanner_streams_batches_and_filters_cluster(self):
        search = self.patch("AlertDocument.search")
        self.patch("get_cluster_bk_biz_ids").return_value = [2]
        self.patch("_search_after_hits").return_value = iter(
            [{"_source": {"id": str(i), "strategy_id": 7, "event": {"bk_biz_id": 2}}} for i in range(401)]
            + [{"_source": {"id": "other", "event": {"bk_biz_id": 3}}}]
        )
        process = self.patch("check_shield_end_close_finished")
        shield_tasks.check_shield_end_close_alert()
        self.assertEqual([len(call.args[0]) for call in process.call_args_list], [200, 200, 1])
        search.assert_called_once_with(all_indices=True)
