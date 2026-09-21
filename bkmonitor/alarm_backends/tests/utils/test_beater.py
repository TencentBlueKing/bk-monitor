"""调度快照和刷新结果之间的并发回归。"""

from threading import Event, Thread
from unittest import TestCase
from unittest.mock import Mock, patch

from bkmonitor.utils.beater import MonitorBeater


class TestMonitorBeater(TestCase):
    def setUp(self):
        with patch("bkmonitor.utils.beater.signal.signal"), patch.dict("os.environ", MONITOR_BEAT_EXEC_TYPE="dumy"):
            self.beater = MonitorBeater()
        self.addCleanup(self.beater.executor.shutdown)

    def entry(self):
        entry = Mock(args=(50,))
        entry.task = Mock(__name__="task")
        entry.is_due.return_value = (True, 0.5)
        return entry

    def test_refresh_removes_later_entry(self):
        first, later = self.entry(), self.entry()
        self.beater.entries = {"refresh": first, 50: later}

        def maybe_due(entry):
            if entry is first:
                with self.beater.entries_lock:
                    self.beater.entries.pop(50)
            return 0.5, entry.next()

        self.beater.maybe_due = Mock(side_effect=maybe_due)
        self.assertEqual(self.beater.tick(), 0.5)
        self.assertNotIn(50, self.beater.entries)
        self.assertIs(self.beater.entries["refresh"], first.next())

    def test_refresh_replacement_is_not_overwritten(self):
        original, replacement = self.entry(), self.entry()
        self.beater.entries = {50: original}

        def maybe_due(entry):
            with self.beater.entries_lock:
                self.beater.entries[50] = replacement
            return 0.5, entry.next()

        self.beater.maybe_due = maybe_due
        self.beater.tick()
        self.assertIs(self.beater.entries[50], replacement)

    def test_error_logging_uses_snapshot_after_removal(self):
        self.beater.entries = {50: self.entry()}

        def maybe_due(entry):
            with self.beater.entries_lock:
                self.beater.entries.pop(50)
            raise RuntimeError("executor stopped")

        self.beater.maybe_due = maybe_due
        with self.assertLogs("bkmonitor.utils.beater", level="ERROR"):
            self.assertEqual(self.beater.tick(), 1)
        self.assertEqual(self.beater.entries, {})

    def test_normal_due_and_pending_entries(self):
        due, pending = self.entry(), self.entry()
        pending.is_due.return_value = (False, 0.25)
        self.beater.entries = {50: due, 60: pending}
        with patch.object(self.beater.executor, "execute") as execute:
            self.assertEqual(self.beater.tick(), 0.25)
        execute.assert_called_once_with(due)
        self.assertIs(self.beater.entries[50], due.next())
        self.assertIs(self.beater.entries[60], pending)

    def test_dummy_task_allows_refresh_from_another_thread(self):
        entry = self.entry()
        self.beater.entries = {50: entry}
        refreshed = Event()
        threads = []

        def refresh():
            with self.beater.entries_lock:
                self.beater.entries.pop(50)
            refreshed.set()

        def task(interval):
            thread = Thread(target=refresh)
            threads.append(thread)
            thread.start()
            # 另一线程必须能在任务返回前取得锁，RLock 同线程重入不算通过。
            if not refreshed.wait(2):
                raise RuntimeError("task execution held entries lock")

        entry.task = task
        with (
            patch("bkmonitor.utils.beater.close_old_connections"),
            patch.object(self.beater.executor, "_run_job_error") as error,
        ):
            self.beater.tick()
        for thread in threads:
            thread.join(2)
        error.assert_not_called()
        self.assertTrue(refreshed.is_set())
        self.assertNotIn(50, self.beater.entries)
