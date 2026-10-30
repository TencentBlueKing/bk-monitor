from unittest.mock import Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import ClusteringOperationStatusEnum
from apps.log_clustering.exceptions import ClusteringConfigHasExistException, QuixClusteringParamsInvalidException
from apps.log_clustering.handlers.quix.handler import QuixClusteringHandler
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.models import LogIndexSet
from apps.tests.log_clustering.test_quix_operation import INDEX_SET_ID, QUIX_CONFIG, create_enable_operation


@patch("apps.log_clustering.tasks.quix.run_quix_clustering_operation.delay")
class TestQuixClusteringHandler(TestCase):
    def setUp(self):
        self.index_set = LogIndexSet(
            index_set_id=INDEX_SET_ID, space_uid="bkcc__2", collector_config_id=10, category_id="other_rt"
        )
        collector_config = Mock(
            collector_config_id=10,
            collector_config_name_en="demo",
            bk_biz_id=2,
            table_id="2_bklog.demo",
            bk_data_id=1001,
        )
        self.collector_config = collector_config
        collector_config.get_etl_config.return_value = {"fields": [{"field_name": "message", "alias_name": "content"}]}
        for target, kwargs in (
            (
                "apps.log_clustering.handlers.quix.handler.CollectorConfig.objects.get",
                {"return_value": collector_config},
            ),
            ("apps.log_clustering.handlers.quix.handler.Space.get_tenant_id", {"return_value": "system"}),
            ("apps.log_clustering.handlers.quix.handler.get_quix_config", {"return_value": QUIX_CONFIG}),
            (
                "apps.log_clustering.handlers.quix.handler.RegexTemplateHandler.list_templates",
                {"return_value": [{"id": 1, "predefined_varibles": "W10="}]},
            ),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_enable_saves_runtime_config_and_schedules_operation(self, mock_delay):
        result = QuixClusteringHandler(self.index_set).enable(
            {"clustering_fields": "log", "filter_rules": [{"fields_name": "level", "op": "=", "value": ["ERROR"]}]}
        )

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.pending_config["log_filter"][0]["method"], "eq")
        self.assertEqual(runtime.pattern_index, "log-clustering-42-pattern")
        self.assertFalse(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)
        mock_delay.assert_called_once_with(result["operation_id"])

    def test_missing_custom_field_is_rejected_before_writes(self, mock_delay):
        with self.assertRaises(ValueError):
            QuixClusteringHandler(self.index_set).enable({"clustering_fields": "missing"})
        self.assertFalse(LogClusteringRuntime.objects.exists())
        self.assertFalse(LogClusteringOperation.objects.exists())
        self.assertFalse(ClusteringConfig.objects.exists())
        mock_delay.assert_not_called()

    def test_custom_field_alias_is_accepted(self, mock_delay):
        QuixClusteringHandler(self.index_set).enable({"clustering_fields": "content"})
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.pending_config["input_mapping"]["log"], "content")
        mock_delay.assert_called_once()

    def test_default_log_field_remains_allowed_without_explicit_etl_field(self, mock_delay):
        self.collector_config.get_etl_config.return_value = {"fields": []}
        QuixClusteringHandler(self.index_set).enable({})
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).pending_config["input_mapping"]["log"], "log"
        )
        mock_delay.assert_called_once()

    def test_finish_failure_and_retry_are_shown_in_flow_run(self, mock_delay):
        from apps.log_clustering.handlers.quix.operation import QuixClusteringOperationRunner

        operation = create_enable_operation()
        for step in QuixClusteringOperationRunner.STEPS[operation.operation_type]:
            operation.record_step(step, ClusteringOperationStatusEnum.SUCCESS.value)
        operation.step = "finish"
        operation.last_error = "finish: tag update failed"
        for status, expected in (
            (ClusteringOperationStatusEnum.FAILED.value, "FAILED"),
            (ClusteringOperationStatusEnum.RUNNING.value, "RUNNING"),
        ):
            with self.subTest(status=status):
                operation.status = status
                operation.save()
                result = QuixClusteringHandler(self.index_set).get_access_status()
                self.assertEqual(result["flow_create"]["status"], "SUCCESS")
                self.assertEqual(result["flow_run"]["status"], expected)
                if expected == "FAILED":
                    self.assertEqual(result["flow_run"]["message"], operation.last_error)
                self.assertFalse(result["access_finished"])
        operation.status = ClusteringOperationStatusEnum.SUCCESS.value
        operation.save()
        LogClusteringRuntime.objects.filter(index_set_id=INDEX_SET_ID).update(phase="running")
        result = QuixClusteringHandler(self.index_set).get_access_status()
        self.assertTrue(result["access_finished"])
        self.assertEqual(result["flow_run"]["status"], "SUCCESS")

    def test_enable_passes_saved_model_parameters_to_bkfara(self, mock_delay):
        from apps.log_clustering.handlers.quix.operation import QuixClusteringOperationRunner

        result = QuixClusteringHandler(self.index_set).enable({"delimeter": "Ilxccysi", "min_members": 7})
        operation = LogClusteringOperation.objects.get(operation_id=result["operation_id"])
        parameters = operation.request_snapshot["model_parameters"]
        self.assertEqual(parameters["delimeter"], "Ilxccysi")
        self.assertEqual(parameters["predefined_variables"], "W10=")
        self.assertEqual(parameters["min_members"], 7)
        self.assertEqual(parameters["max_dist_list"], "0.5")
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(delimeter="changed")
        with (
            patch("apps.log_clustering.handlers.quix.operation.get_quix_config", return_value=QUIX_CONFIG),
            patch(
                "apps.log_clustering.handlers.quix.operation.BkFaraApi.create_task",
                return_value={"task_id": "test-task"},
            ) as create_task,
        ):
            QuixClusteringOperationRunner(operation.operation_id)._step_create_task()
        self.assertEqual(create_task.call_args.args[0]["training"], {"parameters": parameters})
        self.assertEqual(create_task.call_args.args[0]["training"]["parameters"]["depth"], 7)
        self.assertEqual(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).depth, 7)
        self.assertEqual(create_task.call_args.args[0]["profile"], QUIX_CONFIG["profile"])

    def test_enable_rolls_back_operation_if_business_config_fails(self, mock_delay):
        with patch(
            "apps.log_clustering.handlers.quix.handler.RegexTemplateHandler.list_templates",
            side_effect=RuntimeError("template unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "template unavailable"):
                QuixClusteringHandler(self.index_set).enable({"clustering_fields": "log"})

        self.assertFalse(LogClusteringRuntime.objects.exists())
        self.assertFalse(LogClusteringOperation.objects.exists())
        self.assertFalse(ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).exists())
        mock_delay.assert_not_called()

    def test_invalid_filter_rule_rejected_before_any_write(self, mock_delay):
        with self.assertRaises(QuixClusteringParamsInvalidException):
            QuixClusteringHandler(self.index_set).enable(
                {"clustering_fields": "log", "filter_rules": [{"fields_name": "log", "op": "LIKE", "value": ["a%b"]}]}
            )

        self.assertFalse(LogClusteringRuntime.objects.exists())
        mock_delay.assert_not_called()

    def test_existing_online_clustering_cannot_switch(self, mock_delay):
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            min_members=1,
            max_dist_list="0.5",
            predefined_varibles="",
            delimeter="",
            max_log_length=1000,
            clustering_fields="log",
        )

        with self.assertRaises(ClusteringConfigHasExistException):
            QuixClusteringHandler(self.index_set).enable({"clustering_fields": "log"})
        mock_delay.assert_not_called()

    def test_resubmit_resumes_failed_enable(self, mock_delay):
        operation = create_enable_operation()
        LogClusteringOperation.objects.filter(pk=operation.pk).update(
            status=ClusteringOperationStatusEnum.FAILED.value, retry_count=5
        )
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            min_members=1,
            max_dist_list="0.5",
            predefined_varibles="",
            delimeter="",
            max_log_length=1000,
            clustering_fields="log",
        )

        result = QuixClusteringHandler(self.index_set).enable({"clustering_fields": "log"})

        resumed = LogClusteringOperation.objects.get(pk=operation.pk)
        self.assertEqual((resumed.status, resumed.retry_count), (ClusteringOperationStatusEnum.PENDING.value, 0))
        self.assertEqual(result["operation_id"], operation.operation_id)
        mock_delay.assert_called_once_with(operation.operation_id)

    def test_access_status_maps_enable_steps(self, mock_delay):
        operation = create_enable_operation()
        for step in ("create_task", "wait_task_ready", "wait_worker_ready"):
            operation.record_step(step, ClusteringOperationStatusEnum.SUCCESS.value)
        operation.step = "metadata_set"
        operation.status = ClusteringOperationStatusEnum.FAILED.value
        operation.last_error = "metadata_set: boom"
        operation.save()

        status = QuixClusteringHandler(self.index_set).get_access_status()

        self.assertNotIn("coverage_gaps", status["quix"])
        self.assertFalse(status["access_finished"])
        self.assertEqual(status["flow_create"]["status"], "SUCCESS")
        self.assertEqual(status["flow_run"], {"status": "FAILED", "message": "metadata_set: boom"})
        self.assertEqual(status["data_check"]["status"], "PENDING")
        self.assertEqual(status["quix"]["operation"]["operation_id"], operation.operation_id)

    def test_access_status_shows_awaiting_receipt_as_unfinished(self, mock_delay):
        operation = create_enable_operation()
        for step in ("create_task", "wait_task_ready", "wait_worker_ready", "metadata_set"):
            operation.record_step(step, ClusteringOperationStatusEnum.SUCCESS.value)
        operation.record_step("wait_adoption", ClusteringOperationStatusEnum.SUCCESS.value)
        operation.step = "confirm_adoption"
        operation.status = ClusteringOperationStatusEnum.AWAITING_RECEIPT.value
        operation.save()

        status = QuixClusteringHandler(self.index_set).get_access_status()

        self.assertNotIn("coverage_gaps", status["quix"])
        self.assertFalse(status["access_finished"])
        self.assertEqual(status["flow_create"]["status"], "SUCCESS")
        self.assertEqual(status["flow_run"]["status"], "RUNNING")
        self.assertEqual(status["flow_run"]["message"], "配置已下发，待采用确认")
        self.assertEqual(status["data_check"]["status"], "PENDING")
