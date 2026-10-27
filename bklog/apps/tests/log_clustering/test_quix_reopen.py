from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import ClusteringOperationTypeEnum, ClusteringRuntimePhaseEnum
from apps.log_clustering.exceptions import (
    BkFaraResultUnknownException,
    ClusteringAccessNotSupportedException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import QuixClusteringOperationRunner
from apps.log_clustering.models import LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, KAFKA, QUIX_CONFIG
from apps.tests.log_clustering.test_quix_update import create_running_runtime

ADOPTED = {"revision": 2, "sink_referenced": True, "sink_resource": {"status": {"phase": "Ok"}}}


class TestQuixReopenRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(
            phase=ClusteringRuntimePhaseEnum.REOPENING.value, candidate_boundary={"0": 10}, control_version=2
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
        self.transfer.operate_log_clustering.side_effect = [{"revision": 2}, {"revision": 3}]
        self.transfer.get_log_clustering_status.side_effect = [ADOPTED, {"clustering_status": {"state": "STOPPED"}}]
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraClient", Mock(return_value=self.bkfara)),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_reopen_restarts_task_then_reattaches_and_resumes(self):
        self.assertIsNone(self.run_operation())

        self.bkfara.restart_clustering.assert_called_once_with("task-uuid", 5, f"{self.operation.operation_id}-restart")
        self.bkfara.create_task.assert_not_called()
        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["attach", "resume"])
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertIsNone(runtime.candidate_boundary)
        self.assertEqual(runtime.metadata_revision, 3)

    def test_running_binding_does_not_resume(self):
        self.transfer.get_log_clustering_status.side_effect = [ADOPTED, {"clustering_status": {"state": "RUNNING"}}]

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

    def test_running_runtime_cannot_reopen(self, mock_delay):
        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).reopen()
        mock_delay.assert_not_called()

    def test_reopen_requires_quix_runtime(self, mock_delay):
        LogClusteringRuntime.objects.all().delete()

        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler(index_set_id=INDEX_SET_ID).reopen()
