from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import ClusteringOperationConflictException
from apps.log_clustering.models import LogClusteringOperation, LogClusteringRuntime

INDEX_SET_ID = 24466
RUNTIME_DEFAULTS = {
    "bk_biz_id": 2,
    "collector_config_id": 10,
    "table_id": "2_bklog.demo",
    "bk_data_id": 1001,
    "phase": ClusteringRuntimePhaseEnum.ENABLING.value,
}


class TestLogClusteringRuntimeStartOperation(TestCase):
    def test_first_enable_creates_runtime_and_pending_operation(self):
        runtime, operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.ENABLE.value, {"filter_rules": []}, defaults=RUNTIME_DEFAULTS
        )

        self.assertEqual(runtime.index_set_id, INDEX_SET_ID)
        self.assertEqual(runtime.phase, ClusteringRuntimePhaseEnum.ENABLING.value)
        self.assertEqual(operation.status, ClusteringOperationStatusEnum.PENDING.value)
        self.assertEqual(operation.request_snapshot, {"filter_rules": []})
        self.assertEqual(LogClusteringRuntime.objects.count(), 1)

    def test_unfinished_operation_blocks_new_operation(self):
        _, first = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.ENABLE.value, {}, defaults=RUNTIME_DEFAULTS
        )

        for status in ClusteringOperationStatusEnum.unfinished_statuses():
            LogClusteringOperation.objects.filter(pk=first.pk).update(status=status)
            with self.assertRaises(ClusteringOperationConflictException):
                LogClusteringRuntime.start_operation(INDEX_SET_ID, ClusteringOperationTypeEnum.UPDATE.value, {})

        self.assertEqual(LogClusteringOperation.objects.filter(index_set_id=INDEX_SET_ID).count(), 1)

    def test_finished_operation_allows_next_operation_on_same_runtime(self):
        runtime, first = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.ENABLE.value, {}, defaults=RUNTIME_DEFAULTS
        )
        LogClusteringOperation.objects.filter(pk=first.pk).update(status=ClusteringOperationStatusEnum.SUCCESS.value)

        same_runtime, second = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.UPDATE.value, {"filter_rules": [{"fields_name": "level"}]}
        )

        self.assertEqual(same_runtime.pk, runtime.pk)
        self.assertNotEqual(second.operation_id, first.operation_id)
        self.assertEqual(second.operation_type, ClusteringOperationTypeEnum.UPDATE.value)

    def test_index_set_has_single_runtime(self):
        LogClusteringRuntime.objects.create(index_set_id=INDEX_SET_ID, **RUNTIME_DEFAULTS)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LogClusteringRuntime.objects.create(index_set_id=INDEX_SET_ID, **RUNTIME_DEFAULTS)

    def test_model_update_keeps_its_request_separate_from_filter_update(self):
        model_parameters = {"predefined_varibles": [{"regex": r"\d+", "name": "number"}], "delimeter": ","}
        runtime, first = LogClusteringRuntime.start_operation(
            INDEX_SET_ID,
            ClusteringOperationTypeEnum.UPDATE_MODEL.value,
            {"model_parameters": model_parameters},
            defaults=RUNTIME_DEFAULTS,
        )
        first.refresh_from_db()
        self.assertEqual(first.operation_type, ClusteringOperationTypeEnum.UPDATE_MODEL.value)
        self.assertEqual(first.request_snapshot["model_parameters"], model_parameters)

        LogClusteringOperation.objects.filter(pk=first.pk).update(status=ClusteringOperationStatusEnum.SUCCESS.value)
        same_runtime, second = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.UPDATE.value, {"filter_rules": []}
        )
        self.assertEqual(same_runtime.pk, runtime.pk)
        self.assertNotEqual(first.operation_type, second.operation_type)
        self.assertEqual(second.request_snapshot, {"filter_rules": []})


class TestLogClusteringOperation(TestCase):
    def setUp(self):
        _, self.operation = LogClusteringRuntime.start_operation(
            INDEX_SET_ID, ClusteringOperationTypeEnum.ENABLE.value, {}, defaults=RUNTIME_DEFAULTS
        )

    def test_idempotency_key_is_stable_across_retries(self):
        with self.assertNumQueries(0):
            first_key = self.operation.get_idempotency_key("create_task")

        reloaded = LogClusteringOperation.objects.get(pk=self.operation.pk)

        with self.assertNumQueries(0):
            self.assertEqual(reloaded.get_idempotency_key("create_task"), first_key)
            self.assertNotEqual(reloaded.get_idempotency_key("configure_clustering"), first_key)

    def test_different_operations_use_different_idempotency_keys(self):
        LogClusteringOperation.objects.filter(pk=self.operation.pk).update(
            status=ClusteringOperationStatusEnum.SUCCESS.value
        )
        _, another = LogClusteringRuntime.start_operation(INDEX_SET_ID, ClusteringOperationTypeEnum.REOPEN.value, {})
        self.assertNotEqual(
            self.operation.get_idempotency_key("create_task"), another.get_idempotency_key("create_task")
        )

    def test_record_step_persists_history(self):
        self.operation.record_step("create_task", ClusteringOperationStatusEnum.SUCCESS.value)
        self.operation.record_step("wait_task_ready", ClusteringOperationStatusEnum.RUNNING.value, "waiting")

        reloaded = LogClusteringOperation.objects.get(pk=self.operation.pk)

        self.assertEqual(reloaded.step, "wait_task_ready")
        self.assertEqual([item["step"] for item in reloaded.steps], ["create_task", "wait_task_ready"])
        self.assertEqual(reloaded.steps[-1]["message"], "waiting")
