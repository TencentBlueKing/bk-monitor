from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    BkFaraResultUnknownException,
    ClusteringAccessNotSupportedException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import RECEIPT_POLL_INTERVAL_SECONDS, QuixClusteringOperationRunner
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, KAFKA, QUIX_CONFIG
from apps.tests.log_clustering.test_quix_update import create_running_runtime

ADOPTED = {"sink_referenced": True, "sink_resource": {"status": {"phase": "Ok"}}}


class TestQuixReopenRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(
            phase=ClusteringRuntimePhaseEnum.REOPENING.value,
            candidate_boundary={"0": 10},
            outbox_boundary={"0": 100},
            control_version=2,
            kafka_binding=KAFKA,
            input_revision=1,
        )
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.REOPEN.value, {}
        )
        self.bkfara = MagicMock()
        self.bkfara.get_task.return_value = {"control_version": 5}
        self.bkfara.get_clustering.return_value = {
            "state": "RUNNING",
            "target_model_ref": {"uri": "model"},
            "all_ready_model_ref": {"uri": "model"},
            "kafka": KAFKA,
            "input_revision": 1,
        }
        self.transfer = MagicMock()
        self.transfer.get_log_clustering_status.side_effect = [
            ADOPTED,
            {"clustering_status": {"state": "STOPPED"}},
            ADOPTED,
        ]
        self.receipt = Mock(return_value=True)
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraClient", Mock(return_value=self.bkfara)),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.runtime_adoption_confirmed", self.receipt),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.set_tag", Mock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_reopen_stops_at_awaiting_receipt(self):
        self.receipt.return_value = False

        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        )
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase,
            ClusteringRuntimePhaseEnum.REOPENING.value,
        )

    def test_changed_bkfara_binding_fails_without_overwriting_runtime(self):
        self.bkfara.get_clustering.return_value = {**self.bkfara.get_clustering.return_value, "input_revision": 2}

        self.assertIsNone(self.run_operation())

        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(
            (operation.status, operation.step), (ClusteringOperationStatusEnum.FAILED.value, "wait_worker_ready")
        )
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).input_revision, 1)
        self.transfer.operate_log_clustering.assert_not_called()

    def test_reopen_restarts_task_then_reattaches_and_resumes(self):
        self.assertIsNone(self.run_operation())

        self.bkfara.restart_clustering.assert_called_once_with("task-uuid", 5, f"{self.operation.operation_id}-restart")
        self.bkfara.create_task.assert_not_called()
        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["attach", "resume"])
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertEqual((runtime.candidate_boundary, runtime.outbox_boundary), (None, None))
        self.assertTrue(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)

    def test_resume_retries_unknown_status_instead_of_completing_step(self):
        self.transfer.get_log_clustering_status.side_effect = None
        runner = QuixClusteringOperationRunner(self.operation.operation_id)
        for status in ({"errors": [{"source": "clustering_status"}], "clustering_status": None}, {}):
            with self.subTest(status=status):
                self.transfer.get_log_clustering_status.return_value = status
                self.assertFalse(runner._step_resume())
                self.transfer.operate_log_clustering.assert_not_called()

        self.transfer.get_log_clustering_status.return_value = {"clustering_status": {"state": "STOPPED"}}
        self.assertTrue(runner._step_resume())
        self.assertEqual(self.transfer.operate_log_clustering.call_args.args[0]["action"], "resume")

    def test_running_binding_does_not_resume(self):
        self.transfer.get_log_clustering_status.side_effect = [
            ADOPTED,
            {"clustering_status": {"state": "RUNNING"}},
            ADOPTED,
        ]

        self.run_operation()

        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["attach"])

    def test_restart_retry_keeps_idempotency_key(self):
        self.bkfara.restart_clustering.side_effect = [BkFaraResultUnknownException(), {}]

        self.run_operation()
        self.run_operation()

        keys = {call.args[2] for call in self.bkfara.restart_clustering.call_args_list}
        self.assertEqual(keys, {f"{self.operation.operation_id}-restart"})


@patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay")
class TestQuixClusteringHandlerReopen(TestCase):
    def setUp(self):
        self.runtime = create_running_runtime()
        self.index_set = LogIndexSet(index_set_id=INDEX_SET_ID, space_uid="bkcc__2")

    def test_reopen_from_stopped(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)

        operation_id = QuixClusteringHandler(self.index_set).reopen()

        self.assertEqual(
            LogClusteringRuntime.objects.get(pk=self.runtime.pk).phase, ClusteringRuntimePhaseEnum.REOPENING.value
        )
        mock_delay.assert_called_once_with(operation_id)

    def test_reopen_rolls_back_operation_when_phase_save_fails(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)
        original_save = LogClusteringRuntime.save

        def fail_after_save(runtime, *args, **kwargs):
            original_save(runtime, *args, **kwargs)
            if "phase" in kwargs.get("update_fields", []):
                raise RuntimeError("phase save interrupted")

        with patch.object(LogClusteringRuntime, "save", fail_after_save):
            with self.assertRaisesRegex(RuntimeError, "phase save interrupted"):
                QuixClusteringHandler(self.index_set).reopen()

        self.runtime.refresh_from_db()
        self.assertEqual(self.runtime.phase, ClusteringRuntimePhaseEnum.STOPPED.value)
        self.assertFalse(
            LogClusteringOperation.objects.filter(operation_type=ClusteringOperationTypeEnum.REOPEN.value).exists()
        )
        mock_delay.assert_not_called()

    def test_disable_keeps_reopen_with_unconfirmed_external_write(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)
        operation_id = QuixClusteringHandler(self.index_set).reopen()
        operation = LogClusteringOperation.objects.get(operation_id=operation_id)
        mock_delay.reset_mock()
        for step in ("restart", "attach"):
            with self.subTest(step=step):
                operation.status = ClusteringOperationStatusEnum.FAILED.value
                operation.step = step
                operation.idempotency_keys = {"restart": "fixed-key"} if step == "restart" else {}
                operation.save()
                with self.assertRaises(QuixClusteringParamsInvalidException):
                    QuixClusteringHandler(self.index_set).disable()
                operation.refresh_from_db()
                self.assertEqual(operation.status, ClusteringOperationStatusEnum.FAILED.value)
        mock_delay.assert_not_called()

    def test_running_runtime_cannot_reopen(self, mock_delay):
        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).reopen()
        mock_delay.assert_not_called()

    def test_reopen_requires_quix_runtime(self, mock_delay):
        LogClusteringRuntime.objects.all().delete()

        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler(index_set_id=INDEX_SET_ID).reopen()
