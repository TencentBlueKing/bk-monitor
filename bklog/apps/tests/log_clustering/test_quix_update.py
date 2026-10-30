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
ADOPTED = {
    "sink_referenced": True,
    "sink_resource": {"status": {"phase": "Ok"}},
    "clustering_status": {"configuration_applied": True},
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
        self.transfer.get_log_clustering_status.return_value = ADOPTED
        self.bkfara = MagicMock()
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.BkFaraApi", self.bkfara),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_update_stops_at_awaiting_receipt_without_promoting_rules(self):
        self.transfer.get_log_clustering_status.return_value = {**ADOPTED, "clustering_status": {}}

        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        )
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.UPDATING.value)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])
        self.assertEqual(runtime.pending_config["log_filter"][0]["value"], ["WARN"])

    def test_filter_update_applies_config_without_draining_or_touching_model(self):
        self.assertIsNone(self.run_operation())
        self.transfer.operate_log_clustering.assert_not_called()
        self.assertEqual(self.bkfara.mock_calls, [])
        set_params = self.transfer.set_log_clustering_config.call_args.args[0]
        self.assertEqual(set_params["binding"]["log_filter"][0]["value"], ["WARN"])
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["WARN"])
        self.assertIsNone(runtime.pending_config)

    def test_resource_not_ready_does_not_promote_filter(self):
        self.transfer.get_log_clustering_status.return_value = {"errors": ["not ready"]}
        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])
        self.transfer.operate_log_clustering.assert_not_called()

    def test_receipt_retry_does_not_repeat_config_write(self):
        self.transfer.get_log_clustering_status.return_value = {**ADOPTED, "clustering_status": {}}
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.transfer.get_log_clustering_status.return_value = ADOPTED
        self.assertIsNone(self.run_operation())
        self.transfer.set_log_clustering_config.assert_called_once()

    def prepare_model_update(self, mixed=False):
        self.parameters = {"predefined_variables": "encoded-regex", "delimeter": "encoded-delimiter", "depth": 7}
        self.operation.operation_type = (
            ClusteringOperationTypeEnum.UPDATE.value if mixed else ClusteringOperationTypeEnum.UPDATE_MODEL.value
        )
        self.operation.request_snapshot = {"update_model": True, "model_parameters": self.parameters}
        self.operation.save()
        if not mixed:
            LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(pending_config=None)
        self.bkfara.get_task_parameters.side_effect = [
            {"control_version": 4},
            {"control_version": 5, "training": {"parameters": self.parameters}},
        ]

    def test_model_update_uses_existing_task_and_version_without_metadata(self):
        self.prepare_model_update()
        self.assertIsNone(self.run_operation())
        payload = self.bkfara.update_task_parameters.call_args.args[0]
        self.assertEqual(
            payload,
            {
                "task_id": "task-uuid",
                "expected_control_version": 4,
                "training": {"parameters": self.parameters},
                "Idempotency-Key": self.operation.get_idempotency_key("update_model_parameters"),
            },
        )
        self.assertEqual(
            {call[0] for call in self.bkfara.mock_calls}, {"get_task_parameters", "update_task_parameters"}
        )
        self.assertEqual(self.transfer.mock_calls, [])
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual((runtime.bkfara_task_id, runtime.control_version, runtime.phase), ("task-uuid", 5, "running"))
        self.assertEqual(runtime.active_config["log_filter"][0]["value"], ["ERROR"])

    def test_model_write_retry_preserves_version_payload_and_idempotency(self):
        from apps.exceptions import ApiRequestError

        self.prepare_model_update()
        self.bkfara.update_task_parameters.side_effect = [ApiRequestError("timeout"), {}]
        self.assertIsNotNone(self.run_operation())
        self.assertIsNone(self.run_operation())
        first, second = self.bkfara.update_task_parameters.call_args_list
        self.assertEqual(first, second)
        self.assertEqual(self.bkfara.get_task_parameters.call_count, 2)

    def test_model_parameters_must_be_read_back_before_success(self):
        self.prepare_model_update()
        self.bkfara.get_task_parameters.side_effect = [{"control_version": 4}, {"control_version": 4, "training": {}}]
        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.operation.refresh_from_db()
        self.assertNotEqual(self.operation.status, ClusteringOperationStatusEnum.SUCCESS.value)
        self.bkfara.get_task_parameters.side_effect = None
        self.bkfara.get_task_parameters.return_value = {
            "control_version": 5,
            "training": {"parameters": self.parameters},
        }
        self.assertIsNone(self.run_operation())
        self.bkfara.update_task_parameters.assert_called_once()

    def test_model_rejection_does_not_rebuild_or_apply_filter(self):
        from apps.log_clustering.handlers.quix.operation import MAX_STEP_RETRIES

        self.prepare_model_update(mixed=True)
        self.bkfara.get_task_parameters.side_effect = None
        self.bkfara.get_task_parameters.return_value = {"control_version": 4}
        self.bkfara.update_task_parameters.side_effect = RuntimeError("TRAINING_STATE_REBUILD_REQUIRED")
        for _ in range(MAX_STEP_RETRIES):
            self.run_operation()
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.status, ClusteringOperationStatusEnum.FAILED.value)
        self.assertIn("TRAINING_STATE_REBUILD_REQUIRED", self.operation.last_error)
        self.assertEqual(
            {call[0] for call in self.bkfara.mock_calls}, {"get_task_parameters", "update_task_parameters"}
        )
        self.assertEqual(self.transfer.mock_calls, [])

    def test_mixed_update_applies_filter_only_after_model_config_confirmed(self):
        self.prepare_model_update(mixed=True)
        self.bkfara.get_task_parameters.side_effect = [{"control_version": 4}, {"control_version": 4, "training": {}}]
        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.transfer.set_log_clustering_config.assert_not_called()
        self.bkfara.get_task_parameters.side_effect = None
        self.bkfara.get_task_parameters.return_value = {
            "control_version": 5,
            "training": {"parameters": self.parameters},
        }
        self.assertIsNone(self.run_operation())
        self.transfer.set_log_clustering_config.assert_called_once()
        self.transfer.operate_log_clustering.assert_not_called()


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

    def test_unchanged_rules_start_model_update_when_parameters_changed(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).update({"filter_rules": ERROR_RULES, "max_log_length": 2000})
        operation = LogClusteringOperation.objects.get(operation_id=result)
        self.assertEqual(operation.operation_type, ClusteringOperationTypeEnum.UPDATE_MODEL.value)
        self.assertEqual(operation.request_snapshot["model_parameters"]["max_log_length"], 2000)
        self.runtime.refresh_from_db()
        self.assertIsNone(self.runtime.pending_config)
        mock_delay.assert_called_once_with(result)

    @patch("apps.log_clustering.handlers.quix.operation.TransferApi")
    @patch("apps.log_clustering.handlers.quix.operation.BkFaraApi")
    def test_model_fields_reach_existing_task_from_handler(self, bkfara, transfer, mock_delay):
        params = {
            "min_members": 5,
            "predefined_varibles": "encoded-regex",
            "delimeter": "encoded-delimiter",
            "max_log_length": 2000,
            "is_case_sensitive": 1,
        }
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(depth=7)
        operation_id = QuixClusteringHandler(self.index_set).update(params)
        expected = {
            "min_members": 5,
            "predefined_variables": "encoded-regex",
            "delimeter": "encoded-delimiter",
            "max_log_length": 2000,
            "is_case_sensitive": 1,
            "depth": 7,
            "max_dist_list": "0.5",
            "st_list": "0.875",
            "max_child": 100,
            "use_offline_model": 0,
        }
        # 异步执行使用已提交的快照，不读取后来变化的页面配置。
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(delimeter="later-change")
        bkfara.get_task_parameters.side_effect = [
            {"control_version": 4},
            {"control_version": 5, "training": {"parameters": expected}},
        ]
        self.assertIsNone(QuixClusteringOperationRunner(operation_id).run())
        self.assertEqual(bkfara.update_task_parameters.call_args.args[0]["training"]["parameters"], expected)
        self.assertEqual(bkfara.update_task_parameters.call_args.args[0]["task_id"], "task-uuid")
        self.assertEqual(transfer.mock_calls, [])

    def test_unchanged_parameters_do_not_create_operation(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).update({"max_log_length": 1000})
        self.assertIsNone(result)
        mock_delay.assert_not_called()

    def test_mixed_update_snapshots_both_changes(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).update({"filter_rules": WARN_RULES, "delimeter": "new"})
        operation = LogClusteringOperation.objects.get(operation_id=result)
        self.assertEqual(operation.operation_type, ClusteringOperationTypeEnum.UPDATE.value)
        self.assertEqual(operation.request_snapshot["filter_rules"], WARN_RULES)
        self.assertEqual(operation.request_snapshot["model_parameters"]["delimeter"], "new")
        self.assertTrue(operation.request_snapshot["update_model"])

    def test_model_update_can_resume_same_target_but_rejects_new_target(self, mock_delay):
        handler = QuixClusteringHandler(self.index_set)
        first_id = handler.update({"delimeter": "new"})
        LogClusteringOperation.objects.filter(operation_id=first_id).update(
            status=ClusteringOperationStatusEnum.FAILED.value
        )
        self.assertEqual(handler.update({"delimeter": "new"}), first_id)
        with self.assertRaises(QuixClusteringParamsInvalidException):
            handler.update({"delimeter": "different"})
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).delimeter, "new")

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

        self.assertIsNotNone(result)
        clustering_config = ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual((clustering_config.filter_rules, clustering_config.max_log_length), (ERROR_RULES, 2000))
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.UPDATING.value)
        mock_delay.assert_called_once_with(result)

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
            status=ClusteringOperationStatusEnum.RUNNING.value, step="confirm_adoption"
        )

        status = QuixClusteringHandler(self.index_set).get_access_status()

        self.assertEqual(status["flow_create"]["status"], "SUCCESS")
        self.assertEqual(status["flow_run"], {"status": "RUNNING", "message": "confirm_adoption"})
