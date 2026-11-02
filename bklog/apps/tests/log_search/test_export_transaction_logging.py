"""分片导出状态日志必须在事务提交后输出。"""

from unittest.mock import Mock, patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase

from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportStage
from apps.log_search.export import config, state
from apps.log_search.export.logging import log_after_commit
from apps.log_search.export.models import ExportJob, ExportPart
from apps.tests.log_search.test_sharded_export import create_job


class ExportTransactionLoggingTests(TransactionTestCase):
    def setUp(self):
        self.job = create_job(status=ExportJobStatus.RUNNING, plan_version=1, end_time=1000, actual_total=10)
        self.part = ExportPart.objects.create(
            job=self.job,
            part_no=1,
            plan_version=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            actual_rows=10,
        )

    @patch("apps.log_search.export.state.logger")
    def test_finalization_log_observes_committed_claim(self, logger):
        observed = []

        def inspect_claim(*args):
            saved = ExportJob.objects.get(pk=self.job.pk)
            observed.append((connection.in_atomic_block, saved.status, saved.finalization_attempts))

        logger.info.side_effect = inspect_claim

        claimed = state.claim_finalization(self.job.pk)

        self.assertEqual(claimed.status, ExportJobStatus.FINALIZING)
        logger.info.assert_called_once()
        self.assertEqual(observed, [(False, ExportJobStatus.FINALIZING, 1)])

    @patch("apps.log_search.export.state.logger")
    def test_finalization_log_waits_for_outer_transaction(self, logger):
        observed = []
        logger.info.side_effect = lambda *args: observed.append(connection.in_atomic_block)

        with transaction.atomic():
            state.claim_finalization(self.job.pk)
            logger.info.assert_not_called()

        logger.info.assert_called_once()
        self.assertEqual(observed, [False])

    @patch("apps.log_search.export.state.logger")
    def test_rollback_discards_state_log(self, logger):
        with self.assertRaisesMessage(ValueError, "rollback"):
            with transaction.atomic():
                state.claim_finalization(self.job.pk)
                raise ValueError("rollback")

        logger.info.assert_not_called()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
        self.assertEqual(self.job.finalization_attempts, 0)

    @patch("django.db.backends.base.base.logger")
    @patch("apps.log_search.export.state.logger")
    def test_log_failure_does_not_fail_committed_claim(self, logger, database_logger):
        logger.info.side_effect = RuntimeError("log unavailable")

        claimed = state.claim_finalization(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(claimed.status, ExportJobStatus.FINALIZING)
        self.assertEqual(self.job.status, ExportJobStatus.FINALIZING)
        self.assertEqual(self.job.finalization_attempts, 1)
        database_logger.error.assert_called_once()

    @patch("apps.log_search.export.state.logger")
    def test_retry_log_keeps_original_execution_identity(self, logger):
        ExportPart.objects.filter(pk=self.part.pk).update(
            status=ExportPartStatus.UPLOADING,
            stage=ExportStage.UPLOAD,
            task_id="upload-task",
            attempts=1,
        )

        with transaction.atomic():
            state.fail_part(
                self.part.pk,
                state.PartFence(task_id="upload-task", attempts=1),
                error_code="UPLOAD_FAILED",
                error_detail="上传失败",
            )
            self.part.refresh_from_db()
            self.assertEqual(self.part.status, ExportPartStatus.WAITING)
            self.assertEqual(self.part.stage, "")
            self.assertEqual(self.part.task_id, "")
            logger.warning.assert_not_called()

        message, *args = logger.warning.call_args.args
        rendered = message % tuple(args)
        for expected in (
            f"job_id={self.job.pk}",
            f"part_id={self.part.pk}",
            "attempts=1",
            "task_id=upload-task",
            "status=UPLOADING",
            "stage=UPLOAD",
            "error_code=UPLOAD_FAILED",
        ):
            self.assertIn(expected, rendered)

    @patch("apps.log_search.export.config.logger")
    def test_invalid_snapshot_warning_waits_for_commit(self, logger):
        observed = []
        logger.warning.side_effect = lambda *args: observed.append(connection.in_atomic_block)

        with transaction.atomic():
            policy = config.policy_from_snapshot({"target_rows": 0})
            self.assertEqual(policy.target_rows, config.ExportPolicy().target_rows)
            logger.warning.assert_not_called()

        logger.warning.assert_called_once()
        self.assertEqual(observed, [False])

    @patch("apps.log_search.export.config.logger")
    def test_non_mapping_snapshot_warning_is_discarded_on_rollback(self, logger):
        with self.assertRaisesMessage(ValueError, "rollback"):
            with transaction.atomic():
                config.policy_from_snapshot([])
                raise ValueError("rollback")

        logger.warning.assert_not_called()

    def test_log_arguments_are_snapshotted_before_commit(self):
        log_method = Mock()
        context = {"task_id": "old-task", "attempts": 1}

        with transaction.atomic():
            log_after_commit(log_method, "context=%s", context)
            context.update(task_id="new-task", attempts=2)
            log_method.assert_not_called()

        log_method.assert_called_once_with("context=%s", {"task_id": "old-task", "attempts": 1})


class ExportLoggingWithoutTransactionTests(SimpleTestCase):
    def test_log_without_transaction_is_immediate_without_database_access(self):
        log_method = Mock()

        log_after_commit(log_method, "task_id=%s", "task")

        log_method.assert_called_once_with("task_id=%s", "task")

    @patch("apps.log_search.export.config.logger")
    def test_invalid_snapshot_warning_does_not_require_database_access(self, logger):
        policy = config.policy_from_snapshot({"target_rows": 0})

        self.assertEqual(policy.target_rows, config.ExportPolicy().target_rows)
        logger.warning.assert_called_once()
