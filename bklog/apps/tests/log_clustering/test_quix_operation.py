import datetime
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.utils import timezone

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import BkFaraConflictException, BkFaraResultUnknownException
from apps.log_clustering.handlers.quix.adapter import build_clustering_config
from apps.log_clustering.handlers.quix.operation import (
    POLL_INTERVAL_SECONDS,
    WAIT_TIMEOUT_SECONDS,
    QuixClusteringOperationRunner,
)
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime

INDEX_SET_ID = 24466
TASK_ID = "task-uuid"
KAFKA = {"cluster_ref": "quix-e2e", "input_topic": f"lc-{TASK_ID}-in", "partitions": 2}
QUIX_CONFIG = {
    "task_template": {"base_model_ref": {"uri": "base"}},
    "resource_profile_ref": {"uri": "profile"},
    "kafka": {
        "cluster_ref": "quix-e2e",
        "partitions": 2,
        "retention_ms": 604800000,
        "recovery_window_ms": 86400000,
        "source_namespace": "bklog",
        "mapping_revision": "log-v1",
        "input_topic": "lc-{task_id}-in",
        "output_topic": "lc-{task_id}-out",
        "consumer_group": "lc-{task_id}-worker",
        "result_group": "lc-{task_id}-result",
    },
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "pattern_es"},
}
SET_RESULT = {
    "revision": 1,
    "attached": True,
    "applied_scope": "datalink",
    "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_1001_abc"},
    "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_databus"},
    "raw_sink": {"kind": "ElasticSearchBinding", "namespace": "bklog", "name": "bklog_binding"},
}
ADOPTED_STATUS = {"revision": 1, "sink_referenced": True, "sink_resource": {"status": {"phase": "Ok"}}}


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
            "pattern_index": "log-clustering-24466-pattern",
            "state_index": "log-clustering-24466-state",
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
            ("apps.log_clustering.handlers.quix.operation.BkFaraClient", Mock(return_value=self.bkfara)),
            ("apps.log_clustering.handlers.quix.operation.get_quix_config", Mock(return_value=QUIX_CONFIG)),
            ("apps.log_clustering.handlers.quix.operation.TransferApi", self.transfer),
            ("apps.log_clustering.handlers.quix.operation.LogIndexSet.set_tag", Mock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_operation(self):
        return QuixClusteringOperationRunner(self.operation.operation_id).run()

    def test_enable_runs_through_and_activates_config(self):
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

        self.assertIsNone(self.run_operation())

        runtime = LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.RUNNING.value)
        self.assertEqual((runtime.bkfara_task_id, runtime.control_version, runtime.input_revision), (TASK_ID, 1, 1))
        self.assertEqual(runtime.kafka_binding, KAFKA)
        self.assertEqual((runtime.sink, runtime.metadata_revision), (SET_RESULT["sink"], 1))
        self.assertIsNone(runtime.pending_config)
        self.assertEqual(runtime.active_config["distance_threshold"], "0.5")
        self.assertTrue(ClusteringConfig.objects.get(index_set_id=INDEX_SET_ID).access_finished)
        self.assertEqual(
            LogClusteringOperation.objects.get(pk=self.operation.pk).status,
            ClusteringOperationStatusEnum.SUCCESS.value,
        )

        set_params = self.transfer.set_log_clustering_config.call_args.args[0]
        self.assertEqual(set_params["operation_id"], f"{self.operation.operation_id}-metadata_set")
        self.assertEqual(set_params["expected_revision"], 0)
        self.assertEqual(set_params["binding"]["task_id"], TASK_ID)
        self.assertEqual(set_params["binding"]["config_revision"], 1)
        configure_payload = self.bkfara.configure_clustering.call_args.args[1]
        self.assertEqual(configure_payload["kafka"]["input_topic"], f"lc-{TASK_ID}-in")

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
        self.bkfara.create_task.side_effect = [BkFaraResultUnknownException(), {"task_id": TASK_ID}]

        delay = self.run_operation()
        self.run_operation()

        self.assertGreater(delay, POLL_INTERVAL_SECONDS)
        first_key, second_key = (call.args[1] for call in self.bkfara.create_task.call_args_list)
        self.assertEqual(first_key, second_key)
        self.assertEqual(LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).bkfara_task_id, TASK_ID)

    def test_control_version_conflict_fails_without_retry(self):
        self.bkfara.configure_clustering.side_effect = BkFaraConflictException()

        self.assertIsNone(self.run_operation())

        operation = LogClusteringOperation.objects.get(pk=self.operation.pk)
        self.assertEqual(operation.status, ClusteringOperationStatusEnum.FAILED.value)
        self.assertEqual(operation.step, "configure_clustering")
        self.transfer.set_log_clustering_config.assert_not_called()

    def test_adoption_waits_until_databus_references_sink(self):
        self.transfer.get_log_clustering_status.return_value = {**ADOPTED_STATUS, "sink_referenced": False}

        self.assertEqual(self.run_operation(), POLL_INTERVAL_SECONDS)
        self.assertEqual(
            LogClusteringRuntime.objects.get(index_set_id=INDEX_SET_ID).phase,
            ClusteringRuntimePhaseEnum.ENABLING.value,
        )
