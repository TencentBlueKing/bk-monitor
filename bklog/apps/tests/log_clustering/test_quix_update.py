from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import QuixClusteringParamsInvalidException
from apps.log_clustering.handlers.quix.adapter import build_clustering_config
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.handlers.quix.operation import (
    POLL_INTERVAL_SECONDS,
    RECEIPT_POLL_INTERVAL_SECONDS,
    QuixClusteringOperationRunner,
)
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, QUIX_CONFIG, create_enable_operation

ERROR_RULES = [{"fields_name": "level", "op": "=", "value": ["ERROR"]}]
WARN_RULES = [{"fields_name": "level", "op": "=", "value": ["WARN"]}]
DRAINED = {
    "can_unbind": True,
    "storage_complete": True,
    "outbox_drained": True,
    "source_committed": True,
    "coverage_complete": False,
    "outbox_boundary": {"0": 100},
}


def create_running_runtime() -> LogClusteringRuntime:
    operation = create_enable_operation()
    LogClusteringOperation.objects.filter(pk=operation.pk).update(status=ClusteringOperationStatusEnum.SUCCESS.value)
    runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
    runtime.phase = ClusteringRuntimePhaseEnum.RUNNING.value
    runtime.active_config = build_clustering_config("log", ERROR_RULES)
    runtime.pending_config = None
    runtime.bkfara_task_id = "task-uuid"
    runtime.save()
    ClusteringConfig.objects.create(
        index_set_id=INDEX_SET_ID,
        bk_biz_id=2,
        min_members=1,
        max_dist_list="0.5",
        predefined_varibles="",
        delimeter="",
        max_log_length=1000,
        clustering_fields="log",
        filter_rules=ERROR_RULES,
    )
    return runtime


class TestQuixUpdateRunner(TestCase):
    def setUp(self):
        runtime = create_running_runtime()
        runtime.phase = ClusteringRuntimePhaseEnum.UPDATING.value
        runtime.pending_config = build_clustering_config("log", WARN_RULES)
        runtime.save()
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.UPDATE.value, {"filter_rules": WARN_RULES}
        )
        self.transfer = MagicMock()
        self.transfer.set_log_clustering_config.return_value = {
            "sink": {"name": "sink"},
            "databus": {"name": "databus"},
        }
        adopted = {"sink_referenced": True, "sink_resource": {"status": {"phase": "Ok"}}}
        self.transfer.get_log_clustering_status.side_effect = [{"clustering_status": DRAINED}, adopted, adopted]
        self.receipt = Mock(return_value=True)
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.runtime_adoption_confirmed", self.receipt),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_update_stops_at_awaiting_receipt_without_promoting_rules(self):
        self.receipt.return_value = False

        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        )
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.UPDATING.value)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])
        self.assertEqual(runtime.pending_config["log_filter"][0]["value"], ["WARN"])

    def test_update_drains_old_range_before_applying_new_rules(self):
        self.assertIsNone(self.run_operation())

        actions = [call.args[0]["action"] for call in self.transfer.operate_log_clustering.call_args_list]
        self.assertEqual(actions, ["drain", "finish"])
        set_params = self.transfer.set_log_clustering_config.call_args.args[0]
        self.assertEqual(set_params["binding"]["log_filter"][0]["value"], ["WARN"])

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["WARN"])
        self.assertIsNone(runtime.pending_config)
        self.assertEqual(runtime.outbox_boundary, {"0": 100})
        [gap] = runtime.coverage_gaps
        self.assertEqual(gap["operation_id"], self.operation.operation_id)
        self.assertFalse(gap["coverage_complete"])
        self.assertIsNotNone(gap["started_at"])
        self.assertIsNotNone(gap["ended_at"])

    def test_waits_until_old_range_is_drained(self):
        self.transfer.get_log_clustering_status.side_effect = None
        self.transfer.get_log_clustering_status.return_value = {"clustering_status": {**DRAINED, "can_unbind": False}}

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)

        self.assertEqual(self.transfer.operate_log_clustering.call_count, 1)
        self.transfer.set_log_clustering_config.assert_not_called()
        self.assertEqual(LogClusteringOperation.objects.get(pk=self.operation.pk).step, "wait_drained")

    def test_reentered_drain_check_does_not_duplicate_gap(self):
        self.transfer.get_log_clustering_status.side_effect = None
        self.transfer.get_log_clustering_status.return_value = {"clustering_status": DRAINED}
        runner = QuixClusteringOperationRunner(self.operation.operation_id)

        runner._step_wait_drained()
        runner._step_wait_drained()

        self.assertEqual(len(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).coverage_gaps), 1)


@patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay")
class TestQuixClusteringHandlerUpdate(TestCase):
    def setUp(self):
        self.runtime = create_running_runtime()
        self.index_set = LogIndexSet(index_set_id=INDEX_SET_ID, space_uid="bkcc__2")

    def test_changed_rules_start_update(self, mock_delay):
        operation_id = QuixClusteringHandler(self.index_set).update(
            {"filter_rules": WARN_RULES, "regex_template_id": 3}
        )

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.UPDATING.value)
        self.assertEqual(runtime.pending_config["log_filter"][0]["value"], ["WARN"])
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])
        clustering_config = ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual((clustering_config.filter_rules, clustering_config.regex_template_id), (WARN_RULES, 3))
        mock_delay.assert_called_once_with(operation_id)

    def test_update_rolls_back_operation_when_pending_config_save_fails(self, mock_delay):
        original_save = LogClusteringRuntime.save

        def fail_after_save(runtime, *args, **kwargs):
            original_save(runtime, *args, **kwargs)
            if "pending_config" in kwargs.get("update_fields", []):
                raise RuntimeError("pending config save interrupted")

        with patch.object(LogClusteringRuntime, "save", fail_after_save):
            with self.assertRaisesRegex(RuntimeError, "pending config save interrupted"):
                QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})

        self.runtime.refresh_from_db()
        self.assertEqual(self.runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertIsNone(self.runtime.pending_config)
        self.assertFalse(
            LogClusteringOperation.objects.filter(operation_type=ClusteringOperationTypeEnum.UPDATE.value).exists()
        )
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).filter_rules, ERROR_RULES)
        mock_delay.assert_not_called()

    def test_unchanged_rules_only_save_business_config(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).update({"filter_rules": ERROR_RULES, "max_log_length": 2000})

        self.assertIsNone(result)
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).max_log_length, 2000)
        self.assertEqual(
            LogClusteringOperation.objects.filter(operation_type=ClusteringOperationTypeEnum.UPDATE.value).count(), 0
        )
        mock_delay.assert_not_called()

    def test_inflight_update_cannot_silently_revert_business_filter(self, mock_delay):
        first_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        mock_delay.reset_mock()

        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).update({"filter_rules": ERROR_RULES})

        self.runtime.refresh_from_db()
        self.assertEqual(self.runtime.pending_config["log_filter"][0]["value"], ["WARN"])
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).filter_rules, WARN_RULES)
        self.assertEqual(
            list(
                LogClusteringOperation.objects.filter(
                    operation_type=ClusteringOperationTypeEnum.UPDATE.value
                ).values_list("operation_id", flat=True)
            ),
            [first_id],
        )
        mock_delay.assert_not_called()

    def test_clustering_field_change_is_rejected(self, mock_delay):
        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).update({"clustering_fields": "message", "filter_rules": WARN_RULES})
        mock_delay.assert_not_called()

    def test_stopped_runtime_rejects_update(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(phase=ClusteringRuntimePhaseEnum.STOPPED.value)

        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).filter_rules, ERROR_RULES)

    def test_resubmitting_same_rules_resumes_failed_update(self, mock_delay):
        first_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        LogClusteringOperation.objects.filter(operation_id=first_id).update(
            status=ClusteringOperationStatusEnum.FAILED.value
        )

        second_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})

        self.assertEqual(second_id, first_id)
        self.assertEqual(
            LogClusteringOperation.objects.get(operation_id=first_id).status,
            ClusteringOperationStatusEnum.PENDING.value,
        )

    def test_omitted_filter_rules_keep_existing_rules(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).update({"max_log_length": 2000})

        self.assertIsNone(result)
        clustering_config = ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual((clustering_config.filter_rules, clustering_config.max_log_length), (ERROR_RULES, 2000))
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        mock_delay.assert_not_called()

    def test_update_before_enable_finished_is_rejected(self, mock_delay):
        LogClusteringRuntime.objects.filter(pk=self.runtime.pk).update(
            phase=ClusteringRuntimePhaseEnum.ENABLING.value, active_config={}
        )

        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        mock_delay.assert_not_called()

    def test_resubmitting_same_rules_while_running_returns_current_operation(self, mock_delay):
        first_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        LogClusteringOperation.objects.filter(operation_id=first_id).update(
            status=ClusteringOperationStatusEnum.RUNNING.value
        )
        mock_delay.reset_mock()

        second_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})

        self.assertEqual(second_id, first_id)
        mock_delay.assert_not_called()

    def test_access_status_reports_progress_of_update(self, mock_delay):
        operation_id = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES})
        LogClusteringOperation.objects.filter(operation_id=operation_id).update(
            status=ClusteringOperationStatusEnum.RUNNING.value, step="wait_drained"
        )

        status = QuixClusteringHandler(self.index_set).get_access_status()

        self.assertEqual(status["flow_create"]["status"], "SUCCESS")
        self.assertEqual(status["flow_run"], {"status": "RUNNING", "message": "wait_drained"})
