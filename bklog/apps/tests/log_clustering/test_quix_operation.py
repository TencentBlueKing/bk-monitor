import datetime
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.utils import timezone

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.exceptions import ApiRequestError
from apps.log_clustering.exceptions import QuixClusteringConfigInvalidException
from apps.log_clustering.handlers.quix.adapter import build_clustering_config
from apps.log_clustering.handlers.quix.operation import (
    POLL_INTERVAL_SECONDS,
    RECEIPT_POLL_INTERVAL_SECONDS,
    WAIT_TIMEOUT_SECONDS,
    QuixClusteringOperationRunner,
)
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime

INDEX_SET_ID = 42
TASK_ID = "task-uuid"
KAFKA = {"cluster_ref": "quix-e2e", "input_topic": f"lc-{TASK_ID}-in", "partitions": 2}
QUIX_CONFIG = {
    "profile": "test-clustering-es",
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "pattern_es"},
}
SET_RESULT = {
    "attached": True,
    "applied_scope": "datalink",
    "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_1001_abc"},
    "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_databus"},
}
ADOPTED_STATUS = {"sink_referenced": True, "sink_resource": {"status": {"phase": "Ok"}}, "errors": []}


def create_enable_operation():
    _, operation = LogClusteringRuntime.start_operation(
        INDEX_SET_ID,
        ClusteringOperationTypeEnum.ENABLE.value,
        {},
        defaults={
            "bk_biz_id": 2,
            "collector_config_id": 10,
            "table_id": "2_bklog.demo",
            "bk_data_id": 1001,
            "phase": ClusteringRuntimePhaseEnum.ENABLING.value,
            "pending_config": build_clustering_config("log", []),
            "pattern_index": "log-clustering-42-pattern",
            "state_index": "log-clustering-42-state",
        },
    )
    return operation


class TestQuixEnableRunner(TestCase):
    def setUp(self):
        self.operation = create_enable_operation()
        self.bkfara = MagicMock()
        self.bkfara.create_task.return_value = {"task_id": TASK_ID}
        self.bkfara.get_task.return_value = {
            "status": "READY",
            "trained_model_ref": {"uri": "model"},
            "control_version": 1,
            "current_generation": 1,
        }
        self.bkfara.get_clustering.return_value = {
            "state": "RUNNING",
            "target_model_ref": {"uri": "model"},
            "all_ready_model_ref": {"uri": "model"},
            "kafka": KAFKA,
            "input_revision": 1,
        }
        self.transfer = MagicMock()
        self.transfer.set_log_clustering_config.return_value = SET_RESULT
        self.transfer.get_log_clustering_status.return_value = ADOPTED_STATUS
        for target, value in (
            ("apps.log_clustering.handlers.quix.operation.BkFaraApi", self.bkfara),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.set_tag", Mock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def create_clustering_config(self):
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            min_members=1,
            max_dist_list="0.5",
            predefined_varibles="",
            delimeter="",
            max_log_length=1000,
            clustering_fields="log",
            access_finished=False,
        )

    def confirm_receipt(self, confirmed=True):
        self.transfer.get_log_clustering_status.return_value = {
            **ADOPTED_STATUS,
            "clustering_status": {"configuration_applied": confirmed},
        }

    def test_canceled_operation_is_not_restarted_by_stale_runner(self):
        runner = QuixClusteringOperationRunner(self.operation.operation_id)
        LogClusteringOperation.objects.filter(pk=self.operation.pk).update(
            status=ClusteringOperationStatusEnum.CANCELED.value
        )

        self.assertIsNone(runner.run())

        self.bkfara.create_task.assert_not_called()
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.CANCELED.value,
        )

    def test_receipt_poll_is_running_until_external_request_finishes(self):
        self.run_operation()
        observed_statuses = []

        def get_status(params):
            observed_statuses.append(LogClusteringOperation.objects.get(pk=self.operation.pk).status)
            return ADOPTED_STATUS

        self.transfer.get_log_clustering_status.side_effect = get_status
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.assertEqual(observed_statuses, [ClusteringOperationStatusEnum.RUNNING.value])
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        )

    def test_enable_stops_at_awaiting_receipt_without_claiming_running(self):
        self.create_clustering_config()

        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(operation.status, ClusteringOperationStatusEnum.AWAITING_RECEIPT.value)
        self.assertEqual(operation.step, "confirm_adoption")
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.ENABLING.value)
        self.assertIsNotNone(runtime.pending_config)
        self.assertFalse(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)

        # 回执到位前不按等待超时判失败
        operation.steps[-1]["time"] = "2000-01-01 00:00:00"
        operation.save()
        self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        )

    def test_enable_runs_through_and_activates_config_after_receipt(self):
        self.create_clustering_config()
        self.run_operation()
        self.confirm_receipt()

        self.assertIsNone(self.run_operation())

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertEqual((runtime.bkfara_task_id, runtime.control_version, runtime.input_revision), (TASK_ID, 1, 1))
        self.assertEqual(runtime.kafka_binding, KAFKA)
        self.assertEqual(runtime.sink, SET_RESULT["sink"])
        self.assertIsNone(runtime.pending_config)
        self.assertEqual(runtime.active_config["distance_threshold"], "0.5")
        self.assertTrue(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.SUCCESS.value,
        )

        set_params = self.transfer.set_log_clustering_config.call_args.args[0]
        self.assertNotIn("operation_id", set_params)
        self.assertEqual(set_params["binding"]["task_id"], TASK_ID)
        self.assertEqual(set_params["binding"]["config_revision"], 1)
        self.bkfara.configure_clustering.assert_not_called()

    def test_waiting_step_reschedules_without_recreating_task(self):
        self.bkfara.get_task.return_value = {"status": "TRAINING"}

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(operation.step, "wait_task_ready")
        self.assertIsNotNone(operation.next_retry_at)

        self.run_operation()

        self.bkfara.create_task.assert_called_once()
        operation.refresh_from_db()
        self.assertEqual([item["step"] for item in operation.steps], ["create_task", "wait_task_ready"])

    def test_wait_timeout_fails_operation(self):
        self.bkfara.get_task.return_value = {"status": "TRAINING"}
        self.run_operation()
        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        expired = timezone.now() - datetime.timedelta(seconds=WAIT_TIMEOUT_SECONDS + 1)
        operation.steps[-1]["time"] = expired.strftime("%Y-%m-%d %H:%M:%S")
        operation.save()

        self.assertIsNone(self.run_operation())
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.FAILED.value,
        )

    def test_unknown_result_retries_with_same_idempotency_key(self):
        self.bkfara.create_task.side_effect = [ApiRequestError("request failed"), {"task_id": TASK_ID}]

        delay = self.run_operation()
        self.run_operation()

        self.assertGreater(delay, POLL_INTERVAL_SECONDS)
        first_key, second_key = (call.args[0]["Idempotency-Key"] for call in self.bkfara.create_task.call_args_list)
        self.assertEqual(first_key, second_key)
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).bkfara_task_id, TASK_ID)

    def test_invalid_environment_fails_without_retry(self):
        with patch(
            "apps.log_clustering.handlers.quix.operation.get_quix_config",
            side_effect=QuixClusteringConfigInvalidException(),
        ):
            self.assertIsNone(self.run_operation())
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status, ClusteringOperationStatusEnum.FAILED.value
        )
        self.bkfara.create_task.assert_not_called()

    def test_model_parameters_are_sent_from_snapshot(self):
        parameters = {"delimeter": "encoded-delimiter", "predefined_variables": "encoded-regex"}
        self.operation.request_snapshot = {"model_parameters": parameters}
        self.operation.save()
        self.run_operation()
        request = self.bkfara.create_task.call_args.args[0]
        self.assertEqual(request["training"], {"parameters": parameters})
        self.assertEqual(request["profile"], QUIX_CONFIG["profile"])
        self.assertNotIn("kafka", request)

    def test_receipt_with_errors_or_detached_sink_cannot_finish(self):
        self.run_operation()
        for changes in (
            {"errors": ["unavailable"]},
            {"sink_referenced": False},
            {"sink_resource": {"status": {"phase": "Pending"}}},
        ):
            self.transfer.get_log_clustering_status.return_value = {
                **ADOPTED_STATUS,
                "clustering_status": {"configuration_applied": True},
                **changes,
            }
            self.assertEqual(self.run_operation(), RECEIPT_POLL_INTERVAL_SECONDS)

    def test_adoption_waits_until_databus_references_sink(self):
        self.transfer.get_log_clustering_status.return_value = {**ADOPTED_STATUS, "sink_referenced": False}

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase,
            ClusteringRuntimePhaseEnum.ENABLING.value,
        )

    def test_adoption_waits_when_remote_status_query_failed(self):
        self.transfer.get_log_clustering_status.return_value = {
            **ADOPTED_STATUS,
            "errors": [{"source": "clustering_status", "message": "timeout"}],
        }

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.assertEqual(LogClusteringOperation.objects.get(pk=self.operation.pk).step, "wait_adoption")

    def test_resumed_wait_after_timeout_restarts_wait_clock(self):
        self.bkfara.get_task.return_value = {"status": "TRAINING"}
        self.run_operation()
        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        operation.steps[-1]["time"] = "2000-01-01 00:00:00"
        operation.save()
        self.run_operation()
        operation.refresh_from_db()
        self.assertEqual(operation.status, ClusteringOperationStatusEnum.FAILED.value)

        operation.status = ClusteringOperationStatusEnum.PENDING.value
        operation.save()

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.RUNNING.value,
        )

    def test_retry_replays_first_request_payload_after_config_change(self):
        self.bkfara.create_task.side_effect = [ApiRequestError("request failed"), {"task_id": TASK_ID}]
        self.run_operation()
        changed_config = {**QUIX_CONFIG, "profile": "changed"}

        with patch("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=changed_config)):
            self.run_operation()

        first_payload, second_payload = (call.args[0] for call in self.bkfara.create_task.call_args_list)
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(second_payload["profile"], QUIX_CONFIG["profile"])

    def test_finish_is_atomic_with_operation_success(self):
        self.create_clustering_config()
        self.confirm_receipt()

        with patch(
            "apps.log_clustering.handlers.quix.operation.LogIndexSet.set_tag", Mock(side_effect=RuntimeError("down"))
        ):
            self.run_operation()

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.ENABLING.value)
        self.assertIsNotNone(runtime.pending_config)
        self.assertNotEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.SUCCESS.value,
        )

    def test_finish_rerun_does_not_promote_cleared_pending_config(self):
        self.create_clustering_config()
        self.confirm_receipt()
        self.run_operation()
        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        active_config = runtime.active_config
        LogClusteringOperation.objects.filter(pk=self.operation.pk).update(
            status=ClusteringOperationStatusEnum.RUNNING.value
        )

        self.assertIsNone(self.run_operation())

        runtime.refresh_from_db()
        self.assertEqual(runtime.active_config, active_config)
        self.assertIsNone(runtime.pending_config)
