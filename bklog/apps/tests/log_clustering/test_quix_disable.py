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

BOUNDARY = {"0": 10, "1": 10}
SINK = {"name": "sink"}
CLOSED = {
    "configured": True,
    "attached": True,
    "sink_resource": {"spec": {"clustering": {"enabled": False}}, "status": {"phase": "Ok"}},
    "clustering_status": {
        "requested_epoch": "20",
        "applied_epoch": "20",
        "configuration_applied": True,
        "clustering_closed": True,
        "input_boundary": BOUNDARY,
    },
}
DETACHED = {
    "configured": True,
    "attached": False,
    "sink_referenced": False,
    "raw_sink_referenced": True,
    "databus_resource": {"status": {"phase": "Ok"}},
}


class TestQuixDisableRunner(TestCase):
    def setUp(self):
        create_running_runtime()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(phase="disabling", sink=SINK)
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.DISABLE.value, {}
        )
        self.bkfara = MagicMock()
        self.transfer = MagicMock()
        self.transfer.get_log_clustering_status.side_effect = [CLOSED, DETACHED]
        self.delete_tag = Mock()
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraApi", self.bkfara),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.delete_tag_by_name", self.delete_tag),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_closed_receipt_allows_detach_but_not_false_runtime_completion(self):
        self.assertIsNone(self.run_operation())
        self.operation.refresh_from_db()
        self.assertEqual(
            [c.args[0]["action"] for c in self.transfer.operate_log_clustering.call_args_list], ["disable", "detach"]
        )
        self.assertEqual((self.operation.status, self.operation.step), ("failed", "confirm_detached"))
        self.assertIn("Runtime 实际解绑回执", self.operation.last_error)
        self.bkfara.stop_clustering.assert_not_called()
        self.delete_tag.assert_not_called()
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.candidate_boundary, BOUNDARY)
        self.assertEqual(runtime.phase, "disabling")

    def test_stale_or_incomplete_close_receipts_do_not_detach(self):
        from copy import deepcopy

        cases = [
            {"applied_epoch": "19"},
            {"requested_epoch": None},
            {"configuration_applied": False},
            {"clustering_closed": False},
            {"input_boundary": None},
            {"input_boundary": {}},
            {"input_boundary": {"0": -1}},
            {"input_boundary": {"0": True}},
        ]
        runner = QuixClusteringOperationRunner(self.operation.operation_id)
        self.transfer.get_log_clustering_status.side_effect = None
        for changes in cases:
            with self.subTest(changes=changes):
                status = deepcopy(CLOSED)
                status["clustering_status"].update(changes)
                self.transfer.get_log_clustering_status.return_value = status
                self.assertFalse(runner._step_confirm_closed())
        self.transfer.operate_log_clustering.assert_not_called()
        self.bkfara.stop_clustering.assert_not_called()

    def test_enabled_resource_and_remote_errors_do_not_confirm_closed(self):
        from copy import deepcopy

        self.transfer.get_log_clustering_status.side_effect = None
        runner = QuixClusteringOperationRunner(self.operation.operation_id)
        for case in ("enabled", "pending", "error"):
            status = deepcopy(CLOSED)
            if case == "enabled":
                status["sink_resource"]["spec"]["clustering"]["enabled"] = True
            elif case == "pending":
                status["sink_resource"]["status"]["phase"] = "Pending"
            else:
                status["errors"] = [{"source": "sink_resource"}]
            self.transfer.get_log_clustering_status.return_value = status
            self.assertFalse(runner._step_confirm_closed())

    def test_waiting_for_closed_does_not_repeat_disable_on_resume(self):
        self.transfer.get_log_clustering_status.side_effect = None
        self.transfer.get_log_clustering_status.return_value = {"configured": True}
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.transfer.operate_log_clustering.assert_called_once()
        self.bkfara.stop_clustering.assert_not_called()

    def test_local_detached_flag_does_not_skip_business_close(self):
        self.transfer.get_log_clustering_status.side_effect = None
        self.transfer.get_log_clustering_status.return_value = {"configured": True, "attached": False}
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.assertEqual(self.transfer.operate_log_clustering.call_args.args[0]["action"], "disable")
        self.bkfara.stop_clustering.assert_not_called()
        self.assertIsNone(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).candidate_boundary)

    def test_detach_errors_or_old_reference_cannot_confirm_configuration(self):
        self.transfer.get_log_clustering_status.side_effect = None
        runner = QuixClusteringOperationRunner(self.operation.operation_id)
        for patch_value in (
            {"errors": ["unavailable"]},
            {"sink_referenced": True},
            {"raw_sink_referenced": False},
            {"databus_resource": {}},
        ):
            with self.subTest(patch_value=patch_value):
                self.transfer.get_log_clustering_status.return_value = {**DETACHED, **patch_value}
                self.assertFalse(runner._step_wait_detached())

    def prepare_unbound(self):
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(sink={}, candidate_boundary=None)
        self.bkfara.get_clustering.return_value = {"kafka": {"partitions": 2}}
        self.bkfara.stop_clustering.return_value = {"state": "STOPPED", "stop_boundary": {"0": 0, "1": 0}}

    def test_never_bound_task_uses_actual_partitions_and_confirms_stop(self):
        self.prepare_unbound()
        self.assertIsNone(self.run_operation())
        self.assertEqual(self.transfer.mock_calls, [])
        self.bkfara.stop_clustering.assert_called_once_with(
            {
                "task_id": "task-uuid",
                "boundary": {"0": 0, "1": 0},
                "completion": {"input_boundary": {"0": 0, "1": 0}, "storage_complete": True, "binding_removed": True},
            }
        )
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase, "stopped")
        self.delete_tag.assert_called_once()

    def test_never_bound_task_does_not_guess_missing_partitions(self):
        self.prepare_unbound()
        self.bkfara.get_clustering.return_value = {}
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.bkfara.stop_clustering.assert_not_called()

    def test_unbound_without_task_does_not_call_provider(self):
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(sink={}, bkfara_task_id="")
        self.assertIsNone(self.run_operation())
        self.assertEqual(self.bkfara.mock_calls, [])
        self.assertEqual(self.transfer.mock_calls, [])

    def test_stop_retry_reuses_boundary_and_waits_for_stopped(self):
        self.prepare_unbound()
        self.bkfara.stop_clustering.return_value = {"state": "DRAINING"}
        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.bkfara.stop_clustering.return_value = {"state": "STOPPED", "stop_boundary": {"0": 0, "1": 0}}
        self.assertIsNone(self.run_operation())
        first, second = self.bkfara.stop_clustering.call_args_list
        self.assertEqual(first, second)
        self.bkfara.get_clustering.assert_called_once()


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
        for step in ("create_task", "update_model_parameters", "metadata_set"):
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
        collector_config.get_etl_config.return_value = {"fields": []}
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
