from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    ClusteringAccessNotSupportedException,
    ClusteringConfigHasExistException,
    ClusteringOperationConflictException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import (
    POLL_INTERVAL_SECONDS,
    RECEIPT_POLL_INTERVAL_SECONDS,
    QuixClusteringOperationRunner,
)
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, QUIX_CONFIG
from apps.tests.log_clustering.test_quix_update import WARN_RULES, create_running_runtime

DRAINED = {"can_unbind": True, "storage_complete": True, "outbox_drained": True, "source_committed": True}
BOUNDARY = {"0": 10, "1": 10}
ATTACHED = {"configured": True, "attached": True}
BOUNDARY_READY = {"clustering_status": {"boundary_ready": True, "boundary": BOUNDARY, "outbox_boundary": {"0": 100}}}
DETACHED = {
    "raw_sink_referenced": True,
    "sink_referenced": False,
    "databus_resource": {"status": {"phase": "Ok"}},
}
SINK = {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_1001_abc"}


class TestQuixDisableRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(
            phase=ClusteringRuntimePhaseEnum.DISABLING.value, sink=SINK
        )
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.DISABLE.value, {}
        )
        self.bkfara = MagicMock()
        self.transfer = MagicMock()
        self.transfer.get_log_clustering_status.side_effect = [
            ATTACHED,
            BOUNDARY_READY,
            {"clustering_status": {**DRAINED, "coverage_complete": True}},
            DETACHED,
            DETACHED,
        ]
        self.receipt = Mock(return_value=True)
        self.delete_tag = Mock()
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraApi", self.bkfara),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.runtime_detach_confirmed", self.receipt),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.delete_tag_by_name", self.delete_tag),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_final_stop_waits_for_detach_receipt(self):
        self.receipt.return_value = False

        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

        self.assertEqual(self.bkfara.stop_clustering.call_count, 1)
        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(
            (operation.status, operation.step),
            (ClusteringOperationStatusEnum.AWAITING_RECEIPT.value, "confirm_detached"),
        )
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase,
            ClusteringRuntimePhaseEnum.DISABLING.value,
        )

    def test_disable_stops_twice_around_storage_and_detach(self):
        self.assertIsNone(self.run_operation())

        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["drain", "finish", "detach"])
        first_stop, final_stop = self.bkfara.stop_clustering.call_args_list
        self.assertEqual(first_stop.args, ({"task_id": "task-uuid", "boundary": BOUNDARY},))
        self.assertEqual(first_stop.kwargs, {})
        self.assertEqual(
            final_stop.args[0]["completion"],
            {"input_boundary": BOUNDARY, "storage_complete": True, "binding_removed": True},
        )

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.STOPPED.value)
        self.assertEqual((runtime.candidate_boundary, runtime.outbox_boundary), (BOUNDARY, {"0": 100}))
        [gap] = runtime.coverage_gaps
        self.assertTrue(gap["coverage_complete"])
        self.assertIsNotNone(gap["ended_at"])
        self.assertFalse(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)
        self.delete_tag.assert_called_once()

    def test_attached_binding_discards_stale_boundary(self):
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(candidate_boundary={"0": 7})

        self.run_operation()

        self.assertEqual(
            self.bkfara.stop_clustering.call_args_list[0].args, ({"task_id": "task-uuid", "boundary": BOUNDARY},)
        )

    def test_waits_for_boundary_before_first_stop(self):
        self.transfer.get_log_clustering_status.side_effect = [
            ATTACHED,
            {"clustering_status": {"boundary_ready": False}},
        ]

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)

        self.bkfara.stop_clustering.assert_not_called()
        self.assertIsNone(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).candidate_boundary)

    def test_fixed_boundary_is_reused_when_resumed(self):
        self.operation.record_step("check_binding", ClusteringOperationStatusEnum.SUCCESS.value)
        self.operation.request_snapshot = {"binding_attached": True}
        self.operation.save()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(candidate_boundary={"0": 7})
        self.transfer.get_log_clustering_status.side_effect = [
            {"clustering_status": {**DRAINED, "coverage_complete": True}},
            DETACHED,
            DETACHED,
        ]

        self.run_operation()

        self.assertEqual(
            self.bkfara.stop_clustering.call_args_list[0].args, ({"task_id": "task-uuid", "boundary": {"0": 7}},)
        )
        self.assertEqual(
            self.bkfara.stop_clustering.call_args_list[1].args[0]["completion"]["input_boundary"], {"0": 7}
        )

    def test_unbound_clustering_only_stops_bkfara_with_zero_boundary(self):
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(sink={}, kafka_binding={"partitions": 2})

        self.assertIsNone(self.run_operation())

        self.transfer.operate_log_clustering.assert_not_called()
        self.transfer.get_log_clustering_status.assert_not_called()
        first_stop, final_stop = self.bkfara.stop_clustering.call_args_list
        self.assertEqual(first_stop.args, ({"task_id": "task-uuid", "boundary": {"0": 0, "1": 0}},))
        self.assertTrue(final_stop.args[0]["completion"]["binding_removed"])
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase,
            ClusteringRuntimePhaseEnum.STOPPED.value,
        )

    def test_final_stop_waits_for_raw_sink_restored(self):
        self.transfer.get_log_clustering_status.side_effect = [
            ATTACHED,
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
        operation_id = QuixClusteringHandler(self.index_set).disable()

        runtime = LogClusteringRuntime.objects.get(pk=self.runtime.pk)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.DISABLING.value)
        mock_delay.assert_called_once_with(operation_id)

    def start_update(self, status: str, applied: bool) -> LogClusteringOperation:
        update_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        operation = LogClusteringOperation.objects.get(operation_id=update_id)
        if applied:
            operation.record_step("metadata_set", ClusteringOperationStatusEnum.SUCCESS.value)
        operation.status = status
        operation.save()
        return operation

    def test_disable_supersedes_failed_update_and_drops_unapplied_rules(self, mock_delay):
        update = self.start_update(ClusteringOperationStatusEnum.FAILED.value, applied=False)

        QuixClusteringHandler(self.index_set).disable()

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=update.pk).status, ClusteringOperationStatusEnum.CANCELED.value
        )
        runtime = LogClusteringRuntime.objects.get(pk=self.runtime.pk)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.DISABLING.value)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])
        self.assertIsNone(runtime.pending_config)

    def test_disable_supersedes_awaiting_update_and_keeps_applied_rules(self, mock_delay):
        update = self.start_update(ClusteringOperationStatusEnum.AWAITING_RECEIPT.value, applied=True)

        QuixClusteringHandler(self.index_set).disable()

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=update.pk).status, ClusteringOperationStatusEnum.CANCELED.value
        )
        runtime = LogClusteringRuntime.objects.get(pk=self.runtime.pk)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["WARN"])
        self.assertIsNone(runtime.pending_config)

    def test_disable_keeps_update_with_unconfirmed_metadata_write(self, mock_delay):
        update = self.start_update(ClusteringOperationStatusEnum.FAILED.value, applied=False)
        update.request_payloads = {"metadata_set": {"binding": {"task_id": "task-uuid"}}}
        update.step = "metadata_set"
        update.save()
        mock_delay.reset_mock()

        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).disable()

        update.refresh_from_db()
        self.runtime.refresh_from_db()
        self.assertEqual(update.status, ClusteringOperationStatusEnum.FAILED.value)
        self.assertEqual(self.runtime.phase, ClusteringRuntimePhaseEnum.UPDATING.value)
        self.assertEqual(self.runtime.pending_config["log_filter"][0]["value"], ["WARN"])
        mock_delay.assert_not_called()

    def test_disable_does_not_treat_unknown_enable_write_as_unbound(self, mock_delay):
        enable = LogClusteringOperation.objects.get(operation_type=ClusteringOperationTypeEnum.ENABLE.value)
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(
            phase=ClusteringRuntimePhaseEnum.ENABLING.value, sink={}
        )
        for step in ("create_task", "configure_clustering", "metadata_set"):
            with self.subTest(step=step):
                enable.status = ClusteringOperationStatusEnum.FAILED.value
                enable.step = step
                enable.steps = []
                enable.request_payloads = {step: {"request": "persisted before sending"}}
                enable.save()

                with self.assertRaises(QuixClusteringParamsInvalidException):
                    QuixClusteringHandler(self.index_set).disable()

                enable.refresh_from_db()
                self.assertEqual(enable.status, ClusteringOperationStatusEnum.FAILED.value)
        self.assertFalse(
            LogClusteringOperation.objects.filter(operation_type=ClusteringOperationTypeEnum.DISABLE.value).exists()
        )
        mock_delay.assert_not_called()

    def test_disable_does_not_supersede_running_operation(self, mock_delay):
        update = self.start_update(ClusteringOperationStatusEnum.RUNNING.value, applied=False)
        mock_delay.reset_mock()

        with self.assertRaises(ClusteringOperationConflictException):
            QuixClusteringHandler(self.index_set).disable()

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=update.pk).status, ClusteringOperationStatusEnum.RUNNING.value
        )
        mock_delay.assert_not_called()

    def test_unbound_stopped_clustering_can_be_enabled_again(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(
            phase=ClusteringRuntimePhaseEnum.STOPPED.value, sink={}, bkfara_task_id="old-task"
        )
        collector_config = Mock(
            collector_config_id=10, collector_config_name_en="demo", bk_biz_id=2, table_id="2_bklog.demo", bk_data_id=1
        )
        with (
            patch("apps.log_clustering.handlers.quix.handler.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            patch(
                "apps.log_clustering.handlers.quix.handler.CollectorConfig.objects.get",
                Mock(return_value=collector_config),
            ),
            patch("apps.log_clustering.handlers.quix.handler.Space.get_tenant_id", Mock(return_value="system")),
            patch(
                "apps.log_clustering.handlers.quix.handler.RegexTemplateHandler.list_templates",
                Mock(return_value=[{"id": 1, "predefined_varibles": "W10="}]),
            ),
        ):
            result = QuixClusteringHandler(self.index_set).enable({"clustering_fields": "log"})

        runtime = LogClusteringRuntime.objects.get(pk=self.runtime.pk)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.ENABLING.value)
        self.assertEqual((runtime.bkfara_task_id, runtime.active_config), ("", {}))
        mock_delay.assert_called_once_with(result["operation_id"])

    def test_bound_stopped_clustering_cannot_be_enabled_again(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(
            phase=ClusteringRuntimePhaseEnum.STOPPED.value, sink=SINK
        )

        with self.assertRaises(ClusteringConfigHasExistException):
            QuixClusteringHandler(self.index_set).enable({"clustering_fields": "log"})
        mock_delay.assert_not_called()

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
