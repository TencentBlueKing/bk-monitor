"""分片导出入队时单任务锁冲突的隔离。"""

from datetime import timedelta
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError
from django.db.models import QuerySet
from django.test import TestCase
from django.utils import timezone

from apps.log_search.constants import ExportJobStatus, ExportPartStatus
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.scheduler import enqueue_finalization
from apps.tests.log_search.test_sharded_export import create_job


class ExportEnqueueIsolationTests(TestCase):
    def setUp(self):
        self.old_lease = timezone.now() - timedelta(minutes=5)
        self.blocked = self._create_ready_job(finalization_enqueued_at=self.old_lease)
        self.next_job = self._create_ready_job()

    def _create_ready_job(self, **overrides):
        job = create_job(status=ExportJobStatus.RUNNING, plan_version=1, end_time=1000, **overrides)
        ExportPart.objects.create(
            job=job,
            part_no=1,
            plan_version=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            actual_rows=1,
        )
        return job

    def _update_with_error(self, error):
        original_update = QuerySet.update

        def update(queryset, **values):
            if (
                queryset.model is ExportJob
                and "finalization_enqueued_at" in values
                and queryset.filter(pk=self.blocked.pk).exists()
            ):
                raise error
            return original_update(queryset, **values)

        return patch.object(QuerySet, "update", autospec=True, side_effect=update)

    def _assert_lock_conflict_isolated(self, code):
        with (
            self._update_with_error(OperationalError(code, "lock conflict")),
            patch("apps.log_search.export.scheduler._send") as send,
            patch("apps.log_search.export.scheduler.logger") as logger,
        ):
            self.assertEqual(enqueue_finalization(10), [self.next_job.pk])

        self.blocked.refresh_from_db()
        self.next_job.refresh_from_db()
        self.assertEqual(self.blocked.finalization_enqueued_at, self.old_lease)
        self.assertEqual(self.blocked.status, ExportJobStatus.RUNNING)
        self.assertEqual(self.blocked.finalization_attempts, 0)
        self.assertIsNotNone(self.next_job.finalization_enqueued_at)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[1], self.next_job.pk)
        self.assertEqual(logger.warning.call_args.args[1:], (self.blocked.pk, "finalization_enqueued_at", code))

    def test_lock_wait_timeout_does_not_block_next_job(self):
        self._assert_lock_conflict_isolated(1205)

    def test_deadlock_does_not_block_next_job(self):
        self._assert_lock_conflict_isolated(1213)

    def test_other_database_errors_propagate(self):
        with (
            self._update_with_error(OperationalError(2006, "server gone")),
            patch("apps.log_search.export.scheduler._send") as send,
            self.assertRaises(OperationalError),
        ):
            enqueue_finalization(10)
        send.assert_not_called()
        self.next_job.refresh_from_db()
        self.assertIsNone(self.next_job.finalization_enqueued_at)

    def test_soft_time_limit_propagates(self):
        with (
            self._update_with_error(SoftTimeLimitExceeded()),
            patch("apps.log_search.export.scheduler._send") as send,
            self.assertRaises(SoftTimeLimitExceeded),
        ):
            enqueue_finalization(10)
        send.assert_not_called()
