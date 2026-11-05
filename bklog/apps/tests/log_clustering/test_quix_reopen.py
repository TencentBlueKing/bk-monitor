from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.exceptions import ApiRequestError

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    ClusteringAccessNotSupportedException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import POLL_INTERVAL_SECONDS, QuixClusteringOperationRunner
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, KAFKA, QUIX_CONFIG
from apps.tests.log_clustering.test_quix_update import create_running_runtime

ADOPTED = {
    "sink_referenced": True,
    "databus_resource": {"status": {"phase": "Ok"}},
    "sink_resource": {"spec": {"clustering": {"enabled": True}}, "status": {"phase": "Ok"}},
    "clustering_status": {
        "requested_epoch": "20",
        "applied_epoch": "20",
        "configuration_applied": True,
        "phase": "RUNNING",
    },
}


class TestQuixReopenRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(
            phase=ClusteringRuntimePhaseEnum.REOPENING.value,
            candidate_boundary={"0": 10},
            sink={"name": "existing-sink"},
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
            "all_ready_model_ref": None,
            "kafka": KAFKA,
            "input_revision": 1,
        }
        self.transfer = MagicMock()
        self.transfer.get_log_clustering_status.return_value = ADOPTED
        self.bkfara.restart_clustering.return_value = {"state": "RUNNING", "control_version": 6}
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraApi", self.bkfara),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.set_tag", Mock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_reopen_completes_without_runtime_receipt(self):
        self.transfer.get_log_clustering_status.return_value = {**ADOPTED, "clustering_status": {}}
        self.assertIsNone(self.run_operation())
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.status, "success")

    def test_changed_input_topic_blocks_enable_while_worker_is_not_ready(self):
        self.bkfara.get_clustering.return_value["kafka"] = {**KAFKA, "input_topic": "changed-topic"}
        self.assertIsNone(self.run_operation())
        self.operation.refresh_from_db()
        self.assertEqual((self.operation.status, self.operation.step), ("failed", "check_reopen_binding"))
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).kafka_binding, KAFKA)
        self.transfer.operate_log_clustering.assert_not_called()

    def test_changed_input_revision_fails_without_overwriting_runtime(self):
        self.bkfara.get_clustering.return_value = {**self.bkfara.get_clustering.return_value, "input_revision": 2}

        self.assertIsNone(self.run_operation())

        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(
            (operation.status, operation.step), (ClusteringOperationStatusEnum.FAILED.value, "check_reopen_binding")
        )
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).input_revision, 1)
        self.transfer.operate_log_clustering.assert_not_called()

    def test_reopen_enables_and_attaches_while_worker_is_not_ready(self):
        self.assertIsNone(self.run_operation())

        self.bkfara.restart_clustering.assert_called_once_with(
            {
                "task_id": "task-uuid",
                "expected_control_version": 5,
                "Idempotency-Key": f"{self.operation.operation_id}-restart",
            }
        )
        self.bkfara.create_task.assert_not_called()
        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["enable", "attach"])
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertIsNone(runtime.candidate_boundary)
        self.assertEqual(runtime.control_version, 6)
        self.assertTrue(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)

    def test_stale_receipts_do_not_finish_or_repeat_provider_writes(self):
        self.transfer.get_log_clustering_status.side_effect = [
            {**ADOPTED, "databus_resource": {"status": {"phase": "Pending"}}},
            {**ADOPTED, "sink_referenced": False},
            ADOPTED,
        ]
        for _ in range(2):
            self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
            runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
            self.assertEqual((runtime.phase, runtime.candidate_boundary), ("reopening", {"0": 10}))
        self.assertIsNone(self.run_operation())
        self.bkfara.restart_clustering.assert_called_once()
        self.assertEqual(
            [c.args[0]["action"] for c in self.transfer.operate_log_clustering.call_args_list], ["enable", "attach"]
        )

    def test_restart_timeout_blocks_close_and_replays_original_request(self):
        self.bkfara.restart_clustering.side_effect = [ApiRequestError("timeout"), {"control_version": 6}]
        self.assertIsNotNone(self.run_operation())
        self.operation.refresh_from_db()
        self.assertEqual(
            self.operation.request_payloads["restart"], {"task_id": "task-uuid", "expected_control_version": 5}
        )
        LogClusteringOperation.objects.filter(pk=self.operation.pk).update(
            status=ClusteringOperationStatusEnum.FAILED.value
        )
        handler = QuixClusteringHandler(LogIndexSet(index_set_id=INDEX_SET_ID, space_uid="bkcc__2"))
        with self.assertRaises(QuixClusteringParamsInvalidException):
            handler.disable()
        with patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay"):
            self.assertEqual(handler.reopen(), self.operation.operation_id)
        self.bkfara.get_task.return_value = {"control_version": 6}
        self.assertIsNone(self.run_operation())
        first, retry = self.bkfara.restart_clustering.call_args_list
        self.assertEqual(first, retry)
        self.assertEqual(first.args[0]["Idempotency-Key"], f"{self.operation.operation_id}-restart")
        self.bkfara.get_task.assert_called_once()


@patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay")
class TestQuixClusteringHandlerReopen(TestCase):
    def setUp(self):
        self.runtime = create_running_runtime()
        self.runtime.sink = {"name": "existing-sink"}
        self.runtime.save(update_fields=["sink"])
        self.index_set = LogIndexSet(index_set_id=INDEX_SET_ID, space_uid="bkcc__2")

    def test_reopen_from_stopped(self, mock_delay):
        self.runtime.active_config["result_mode"] = "append"
        self.runtime.save()
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)

        with self.captureOnCommitCallbacks(execute=True):
            operation_id = QuixClusteringHandler(self.index_set).reopen()

        self.assertEqual(
            LogClusteringRuntime.objects.get(pk=self.runtime.pk).phase, ClusteringRuntimePhaseEnum.REOPENING.value
        )
        self.assertEqual(LogClusteringRuntime.objects.get(pk=self.runtime.pk).active_config["result_mode"], "append")
        mock_delay.assert_called_once_with(operation_id)

    def test_stopped_reopen_requires_original_sink_and_task(self, mock_delay):
        for sink, task_id in (({}, ""), ({}, "existing-task"), ({"name": "existing-sink"}, "")):
            with self.subTest(sink=sink, task_id=task_id):
                LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(
                    phase=ClusteringRuntimePhaseEnum.STOPPED.value, sink=sink, bkfara_task_id=task_id
                )
                with self.assertRaises(QuixClusteringParamsInvalidException):
                    QuixClusteringHandler(self.index_set).reopen()
                self.runtime.refresh_from_db()
                self.assertEqual(self.runtime.phase, ClusteringRuntimePhaseEnum.STOPPED.value)
                self.assertFalse(
                    LogClusteringOperation.objects.filter(
                        index_set_id=INDEX_SET_ID, operation_type=ClusteringOperationTypeEnum.REOPEN.value
                    ).exists()
                )
                mock_delay.assert_not_called()

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
        for step in ("enable_clustering", "attach"):
            with self.subTest(step=step):
                operation.status = ClusteringOperationStatusEnum.FAILED.value
                operation.step = step
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
