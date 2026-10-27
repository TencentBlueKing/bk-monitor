from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import ClusteringAccessNotSupportedException, QuixClusteringParamsInvalidException
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import POLL_INTERVAL_SECONDS, QuixClusteringOperationRunner
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, QUIX_CONFIG
from apps.tests.log_clustering.test_quix_update import DRAINED, create_running_runtime

BOUNDARY = {"0": 10, "1": 10}
BOUNDARY_READY = {"clustering_status": {"boundary_ready": True, "boundary": BOUNDARY, "outbox_boundary": {"0": 100}}}
DETACHED = {
    "revision": 4,
    "raw_sink_referenced": True,
    "sink_referenced": False,
    "databus_resource": {"status": {"phase": "Ok"}},
}


class TestQuixDisableRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(
            phase=ClusteringRuntimePhaseEnum.DISABLING.value
        )
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.DISABLE.value, {}
        )
        self.bkfara = MagicMock()
        self.transfer = MagicMock()
        self.transfer.operate_log_clustering.side_effect = [{"revision": 2}, {"revision": 3}, {"revision": 4}]
        self.transfer.get_log_clustering_status.side_effect = [
            BOUNDARY_READY,
            {"clustering_status": {**DRAINED, "coverage_complete": True}},
            DETACHED,
        ]
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

    def test_disable_stops_twice_around_storage_and_detach(self):
        self.assertIsNone(self.run_operation())

        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["drain", "finish", "detach"])
        first_stop, final_stop = self.bkfara.stop_clustering.call_args_list
        self.assertEqual(first_stop.args, ("task-uuid", BOUNDARY))
        self.assertEqual(first_stop.kwargs, {})
        self.assertEqual(
            final_stop.kwargs["completion"],
            {"input_boundary": BOUNDARY, "storage_complete": True, "binding_removed": True},
        )

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.STOPPED.value)
        self.assertEqual((runtime.candidate_boundary, runtime.outbox_boundary), (BOUNDARY, {"0": 100}))
        [gap] = runtime.coverage_gaps
        self.assertTrue(gap["coverage_complete"])
        self.assertIsNotNone(gap["ended_at"])

    def test_waits_for_boundary_before_first_stop(self):
        self.transfer.get_log_clustering_status.side_effect = None
        self.transfer.get_log_clustering_status.return_value = {"clustering_status": {"boundary_ready": False}}

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)

        self.bkfara.stop_clustering.assert_not_called()
        self.assertIsNone(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).candidate_boundary)

    def test_fixed_boundary_is_reused(self):
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(candidate_boundary={"0": 7})
        self.transfer.get_log_clustering_status.side_effect = [
            {"clustering_status": {**DRAINED, "coverage_complete": True}},
            DETACHED,
        ]

        self.run_operation()

        self.assertEqual(self.bkfara.stop_clustering.call_args_list[0].args, ("task-uuid", {"0": 7}))
        self.assertEqual(self.bkfara.stop_clustering.call_args_list[1].kwargs["completion"]["input_boundary"], {"0": 7})

    def test_final_stop_waits_for_raw_sink_restored(self):
        self.transfer.get_log_clustering_status.side_effect = [
            BOUNDARY_READY,
            {"clustering_status": DRAINED},
            {**DETACHED, "sink_referenced": True},
        ]

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)

        self.assertEqual(self.bkfara.stop_clustering.call_count, 1)
        self.assertEqual(LogClusteringOperation.objects.get(pk=self.operation.pk).step, "wait_detached")


@patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay")
class TestQuixClusteringHandlerDisable(TestCase):
    def setUp(self):
        self.runtime = create_running_runtime()
        self.index_set = LogIndexSet(index_set_id=INDEX_SET_ID, space_uid="bkcc__2")

    def test_disable_from_running(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(candidate_boundary={"0": 1})

        operation_id = QuixClusteringHandler(self.index_set).disable()

        runtime = LogClusteringRuntime.objects.get(pk=self.runtime.pk)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.DISABLING.value)
        self.assertIsNone(runtime.candidate_boundary)
        mock_delay.assert_called_once_with(operation_id)

    def test_stopped_runtime_cannot_disable_again(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)

        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).disable()
        mock_delay.assert_not_called()

    def test_resubmit_resumes_failed_disable_with_fixed_boundary(self, mock_delay):
        first_id = QuixClusteringHandler(self.index_set).disable()
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(candidate_boundary=BOUNDARY)
        LogClusteringOperation.objects.filter(operation_id=first_id).update(
            status=ClusteringOperationStatusEnum.FAILED.value
        )

        second_id = QuixClusteringHandler(self.index_set).disable()

        self.assertEqual(second_id, first_id)
        self.assertEqual(LogClusteringRuntime.objects.get(pk=self.runtime.pk).candidate_boundary, BOUNDARY)

    def test_close_requires_quix_runtime(self, mock_delay):
        LogClusteringRuntime.objects.all().delete()
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(filter_rules=[])

        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler(index_set_id=INDEX_SET_ID).close()
        mock_delay.assert_not_called()
