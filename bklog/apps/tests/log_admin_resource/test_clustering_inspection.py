import json
import threading
import time
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from pipeline.engine.models import Data, PipelineProcess, ProcessCeleryTask, Status

from apps.api.base import DataAPI, DataResponse
from apps.api.modules.bkdata_databus import _BkDataDatabusApi
from apps.api.modules.bkdata_dataflow import _BkDataDataFlowApi
from apps.exceptions import ApiResultError, ValidationError
from apps.log_admin_resource.handlers.bkdata_inspection import (
    batch_get_bkdata_result_table_snapshots,
    get_bkdata_clean_snapshot,
    get_bkdata_flow_snapshot,
    get_bkdata_raw_snapshot,
)
from apps.log_admin_resource.handlers.clustering_config import (
    get_clustering_config_detail,
    list_clustering_configs,
)
from apps.log_admin_resource.handlers.clustering_pipeline import (
    force_fail_clustering_pipeline_node,
    get_clustering_access_pipeline,
    retry_clustering_pipeline_node,
    skip_clustering_pipeline_node,
)
from apps.log_admin_resource.handlers.index_set import get_index_set_detail, list_index_sets
from apps.log_admin_resource.handlers.inspection import (
    build_bkdata_context,
    call_bkdata,
    sanitize_json,
    serialize_tail_rows,
)
from apps.log_admin_resource.registry import FUNCTIONS, HANDLERS
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.constants import IndexSetDataType
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario


BKDATA_CONTEXT = {
    "bk_biz_id": 2,
    "bk_username": "bkdata-admin",
    "operator": "bkdata-admin",
    "bkdata_authentication_method": "user",
    "no_request": True,
    "bk_tenant_id": "system",
}
APIGW_MIDDLEWARE = "apps.tests.log_admin_resource.test_resource_call.AdminApiGatewayMiddleware"


def create_clustering_config(**overrides):
    defaults = {
        "index_set_id": 755,
        "bk_biz_id": 2,
        "collector_config_id": 10402,
        "collector_config_name_en": "bcs_checkinsvr",
        "group_fields": ["serverIp"],
        "sample_set_id": 1001,
        "model_id": "log-clustering-model",
        "min_members": 3,
        "max_dist_list": "0.1,0.2",
        "st_list": "0.5",
        "predefined_varibles": "<IP>=.*",
        "delimeter": "_",
        "max_log_length": 1024,
        "clustering_fields": "log",
        "filter_rules": [{"field": "level", "operator": "neq", "value": "debug"}],
        "bkdata_data_id": 590089,
        "bkdata_etl_processing_id": "2_bklog_bcs_checkinsvr",
        "bkdata_etl_result_table_id": "2_bklog_bcs_checkinsvr",
        "source_rt_name": "2_bklog.bcs_checkinsvr",
        "predict_flow_id": 66341,
        "log_count_aggregation_flow_id": 66342,
        "model_output_rt": "2_bklog_755_clustering_output",
        "clustered_rt": "2_bklog_755_clustered",
        "signature_pattern_rt": "2_bklog_755_pattern",
        "signature_enable": True,
        "access_finished": False,
        "options": {"nested": {"password": "do-not-return"}, "custom_node": "kept"},
    }
    defaults.update(overrides)
    return ClusteringConfig.objects.create(**defaults)


class ClusteringConfigResourceTest(TestCase):
    def setUp(self):
        self.index_set = LogIndexSet.objects.create(
            index_set_id=755,
            index_set_name="bcs-checkinsvr-container",
            space_uid="bkcc__2",
            category_id="container",
            collector_config_id=10402,
            scenario_id=Scenario.LOG,
        )
        self.group = LogIndexSet.objects.create(
            index_set_id=901,
            index_set_name="all-logs",
            space_uid="bkcc__2",
            category_id="container",
            scenario_id=Scenario.LOG,
            is_group=True,
        )
        LogIndexSetData.objects.create(
            index_id=1901,
            index_set_id=self.group.index_set_id,
            bk_biz_id=2,
            result_table_id=str(self.index_set.index_set_id),
            result_table_name=self.index_set.index_set_name,
            scenario_id=Scenario.LOG,
            type=IndexSetDataType.INDEX_SET.value,
        )
        self.config = create_clustering_config()

    def test_all_twelve_operations_have_machine_readable_contracts(self):
        operation_names = {
            "bklog.index_set.list",
            "bklog.index_set.detail",
            "bklog.clustering_config.list",
            "bklog.clustering_config.detail",
            "bklog.clustering_config.access_pipeline",
            "bklog.clustering_config.pipeline.retry",
            "bklog.clustering_config.pipeline.skip",
            "bklog.clustering_config.pipeline.force_fail",
            "bklog.bkdata.raw.snapshot",
            "bklog.bkdata.clean.snapshot",
            "bklog.bkdata.flow.snapshot",
            "bklog.bkdata.result_table.snapshot_batch",
        }
        self.assertTrue(operation_names.issubset(FUNCTIONS))
        self.assertTrue(operation_names.issubset(HANDLERS))
        for operation_name in operation_names:
            operation = FUNCTIONS[operation_name]
            self.assertIn("params_schema", operation)
            self.assertIn("response_schema", operation)
            self.assertTrue(operation["examples"])
            self.assertIn(operation["safety_level"], {"read", "inspect", "write", "destructive"})
            self.assertTrue(operation["response_schema"]["required"])

    @override_settings(MIDDLEWARE=(APIGW_MIDDLEWARE,))
    def test_config_detail_is_reachable_through_admin_resource_dispatcher(self):
        response = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps(
                {
                    "func_name": "bklog.clustering_config.detail",
                    "params": {"config_id": self.config.id},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = response.json()
        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["result"]["config"]["id"], self.config.id)

    def test_config_detail_uses_exact_config_id_and_returns_all_parameters(self):
        other = create_clustering_config(
            index_set_id=755,
            predict_flow_id=70000,
            predict_flow={"nodes": [{"id": 1}], "password": "flow-secret"},
        )

        result = get_clustering_config_detail({"config_id": other.id})

        self.assertEqual(result["config"]["id"], other.id)
        self.assertEqual(result["config"]["min_members"], 3)
        self.assertEqual(result["config"]["sample_set_id"], 1001)
        self.assertEqual(result["config"]["model_id"], "log-clustering-model")
        self.assertEqual(result["config"]["filter_rules"][0]["field"], "level")
        self.assertEqual(result["config"]["options"]["nested"]["password"], "***")
        self.assertIn({"role": "predict", "flow_id": 70000}, result["flow_references"])
        self.assertNotIn("predict_flow", result["config"])
        self.assertNotIn("task_records", result["config"])
        self.assertNotIn("task_details", result["config"])
        self.assertFalse(result["generated_flow_configs"]["included"])
        self.assertIn("predict_flow", result["generated_flow_configs"]["available_fields"])

        with_flow_configs = get_clustering_config_detail({"config_id": other.id, "include_flow_configs": True})
        self.assertTrue(with_flow_configs["generated_flow_configs"]["included"])
        self.assertEqual(with_flow_configs["generated_flow_configs"]["values"]["predict_flow"]["password"], "***")

    def test_config_list_supports_relation_filters_and_navigation_fields(self):
        result = list_clustering_configs({"related_index_set_id": 755, "page": 1, "page_size": 20})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["config_id"], self.config.id)
        self.assertEqual(result["items"][0]["index_set_name"], self.index_set.index_set_name)
        self.assertFalse(result["items"][0]["access_finished_stored"])

    def test_index_set_list_and_group_detail_return_clustering_relationships(self):
        listed = list_index_sets({"has_clustering_config": True, "ordering": "index_set_id"})
        by_id = {item["index_set_id"]: item for item in listed["items"]}

        self.assertEqual(set(by_id), {755, 901})
        self.assertEqual(by_id[755]["clustering"]["navigation_config_id"], self.config.id)
        self.assertEqual(by_id[901]["clustering"]["configured_member_count"], 1)

        detail = get_index_set_detail({"index_set_id": 901})
        self.assertEqual(detail["clustering_relations"][0]["relation_type"], "group_member_primary")
        self.assertEqual(detail["clustering_relations"][0]["config_id"], self.config.id)

    def test_index_set_list_can_filter_unconfigured_index_sets(self):
        LogIndexSet.objects.create(
            index_set_id=990,
            index_set_name="not-configured",
            space_uid="bkcc__2",
            category_id="host",
            scenario_id=Scenario.LOG,
        )

        result = list_index_sets({"has_clustering_config": False, "ordering": "index_set_id"})

        self.assertEqual([item["index_set_id"] for item in result["items"]], [990])

    def test_unconfigured_filter_rejects_config_only_filters(self):
        with self.assertRaises(ValidationError):
            list_index_sets({"has_clustering_config": False, "signature_enable": False})


class ClusteringPipelineResourceTest(TestCase):
    def test_pipeline_returns_serial_runtime_and_persistent_steps(self):
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}],
            task_details={
                "root-pipeline": [
                    {
                        "node_id": "node-1",
                        "node_name": "create flow",
                        "status": "RUNNING",
                        "message": "working",
                    }
                ]
            },
        )
        Status.objects.create(id="root-pipeline", state="RUNNING", name="pipeline", version="1")
        Status.objects.create(id="node-1", state="RUNNING", name="create flow", version="1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
        )
        Data.objects.create(id="node-1", inputs={"flow_id": 66341}, outputs={}, ex_data=None)
        ProcessCeleryTask.objects.create(process_id="process-1", celery_task_id="celery-1")

        result = get_clustering_access_pipeline({"config_id": config.id})

        pipeline = result["pipeline"]["data"]
        self.assertEqual(result["task_selection"], "latest")
        self.assertEqual(pipeline["root_status"]["state"], "RUNNING")
        self.assertEqual(pipeline["process"]["current_node_id"], "node-1")
        self.assertEqual(pipeline["current_node"]["data"]["inputs"]["value"]["flow_id"], 66341)
        self.assertEqual(pipeline["celery_task"]["celery_task_id"], "celery-1")
        self.assertEqual(pipeline["persistent_task_steps"][0]["node_name"], "create flow")
        self.assertNotIn("ack_num", pipeline["process"])
        self.assertNotIn("loop", pipeline["root_status"])

    def test_pipeline_keeps_persistent_steps_when_engine_rows_are_gone(self):
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "gone", "time": 1786503128}],
            task_details={"gone": [{"node_id": "node-1", "status": "FAILED"}]},
        )

        result = get_clustering_access_pipeline({"config_id": config.id, "task_id": "gone"})

        self.assertTrue(result["pipeline"]["exists"])
        self.assertIsNone(result["pipeline"]["data"]["process"])
        self.assertEqual(result["pipeline"]["data"]["persistent_task_steps"][0]["status"], "FAILED")
        self.assertEqual(result["pipeline"]["warnings"][0]["code"], "PIPELINE_ENGINE_ROW_NOT_FOUND")

    @override_settings(
        MIDDLEWARE=(APIGW_MIDDLEWARE,),
        ESQUERY_WHITE_LIST=["bkmonitorv3"],
    )
    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_endpoint_runs_the_authenticated_registry_handler_chain(self, retry_activity):
        retry_activity.return_value = MagicMock(result=True, message="success")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        response = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps(
                {
                    "func_name": "bklog.clustering_config.pipeline.retry",
                    "params": {
                        "config_id": config.id,
                        "task_id": "root-pipeline",
                        "node_id": "node-1",
                        "expected_version": "version-1",
                        "reason": "依赖已修复",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = response.json()
        self.assertTrue(content["result"])
        self.assertEqual(content["data"]["result"]["action"], "retry")
        retry_activity.assert_called_once_with("node-1")

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_requires_owned_current_failed_node_and_returns_refreshed_pipeline(self, retry_activity):
        retry_activity.return_value = MagicMock(result=True, message="success")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        result = retry_clustering_pipeline_node(
            {
                "config_id": config.id,
                "task_id": "root-pipeline",
                "node_id": "node-1",
                "expected_version": "version-1",
                "reason": "依赖已修复",
            }
        )

        retry_activity.assert_called_once_with("node-1")
        self.assertTrue(result["result"])
        self.assertEqual(result["before"]["status"]["state"], "FAILED")
        self.assertEqual(result["pipeline"]["selected_task_id"], "root-pipeline")

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_rejects_stale_node_version_without_calling_engine(self, retry_activity):
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-2")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        with self.assertRaisesMessage(ValidationError, "pipeline node version changed"):
            retry_clustering_pipeline_node(
                {
                    "config_id": config.id,
                    "task_id": "root-pipeline",
                    "node_id": "node-1",
                    "expected_version": "version-1",
                    "reason": "依赖已修复",
                }
            )

        retry_activity.assert_not_called()

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.skip_activity")
    def test_skip_requires_explicit_external_effect_acknowledgement(self, skip_activity):
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        with self.assertRaisesMessage(ValidationError, "acknowledge_external_effects=true"):
            skip_clustering_pipeline_node(
                {
                    "config_id": config.id,
                    "task_id": "root-pipeline",
                    "node_id": "node-1",
                    "expected_version": "version-1",
                    "reason": "外部副作用已完成",
                }
            )

        skip_activity.assert_not_called()

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.forced_fail")
    def test_force_fail_only_operates_the_current_running_node(self, forced_fail):
        forced_fail.return_value = MagicMock(result=True, message="success")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="RUNNING", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        result = force_fail_clustering_pipeline_node(
            {
                "config_id": config.id,
                "task_id": "root-pipeline",
                "node_id": "node-1",
                "expected_version": "version-1",
                "reason": "节点长时间没有刷新",
            }
        )

        forced_fail.assert_called_once_with("node-1", ex_data="Admin forced failure: 节点长时间没有刷新")
        self.assertEqual(result["action"], "force_fail")

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.skip_activity")
    def test_skip_accepts_explicit_external_effect_acknowledgement(self, skip_activity):
        skip_activity.return_value = MagicMock(result=True, message="success")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        result = skip_clustering_pipeline_node(
            {
                "config_id": config.id,
                "task_id": "root-pipeline",
                "node_id": "node-1",
                "expected_version": "version-1",
                "reason": "外部副作用已完成",
                "acknowledge_external_effects": True,
            }
        )

        skip_activity.assert_called_once_with("node-1")
        self.assertEqual(result["action"], "skip")

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_rejects_ambiguous_root_process(self, retry_activity):
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        for process_id in ("process-1", "process-2"):
            PipelineProcess.objects.create(
                id=process_id,
                root_pipeline_id="root-pipeline",
                current_node_id="node-1",
                is_alive=True,
                is_frozen=False,
            )

        with self.assertRaisesMessage(ValidationError, "multiple root pipeline processes"):
            retry_clustering_pipeline_node(
                {
                    "config_id": config.id,
                    "task_id": "root-pipeline",
                    "node_id": "node-1",
                    "expected_version": "version-1",
                    "reason": "依赖已修复",
                }
            )

        retry_activity.assert_not_called()

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_rejects_engine_failure(self, retry_activity):
        retry_activity.return_value = MagicMock(result=False, message="node is not retryable")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        with self.assertRaisesMessage(ValidationError, "pipeline engine rejected retry"):
            retry_clustering_pipeline_node(
                {
                    "config_id": config.id,
                    "task_id": "root-pipeline",
                    "node_id": "node-1",
                    "expected_version": "version-1",
                    "reason": "依赖已修复",
                }
            )

    @patch("apps.log_admin_resource.handlers.clustering_pipeline.get_clustering_access_pipeline")
    @patch("apps.log_admin_resource.handlers.clustering_pipeline.task_service.retry_activity")
    def test_retry_reports_snapshot_failure_without_hiding_committed_operation(self, retry_activity, get_snapshot):
        retry_activity.return_value = MagicMock(result=True, message="success")
        get_snapshot.side_effect = RuntimeError("snapshot unavailable")
        config = create_clustering_config(
            task_records=[{"operate": "create", "task_id": "root-pipeline", "time": 1786503128}]
        )
        Status.objects.create(id="node-1", state="FAILED", name="create flow", version="version-1")
        PipelineProcess.objects.create(
            id="process-1",
            root_pipeline_id="root-pipeline",
            current_node_id="node-1",
            is_alive=True,
            is_frozen=False,
        )

        result = retry_clustering_pipeline_node(
            {
                "config_id": config.id,
                "task_id": "root-pipeline",
                "node_id": "node-1",
                "expected_version": "version-1",
                "reason": "依赖已修复",
            }
        )

        self.assertTrue(result["result"])
        self.assertEqual(result["pipeline"]["pipeline"]["probe_status"], "failed")
        self.assertEqual(result["pipeline"]["pipeline"]["error"]["upstream_message"], "snapshot unavailable")


class InspectionEvidenceTest(TestCase):
    def test_tail_preserves_log_original_and_extracts_decoded_event_time(self):
        payload = {"log": "systemd: Started Session 1", "utctime": "2026-08-12 02:52:08"}
        row = {"topic": "raw-topic", "value": json.dumps(payload), "offset": 12}

        result = serialize_tail_rows([row], 10, decode_wrapped=True)

        sample = result["samples"][0]
        self.assertEqual(sample["raw"]["value"]["value"], row["value"])
        self.assertEqual(sample["decoded"]["value"]["log"], payload["log"])
        self.assertEqual(sample["decode_status"], "success")
        self.assertEqual(result["time_evidence"]["selected"]["field_name"], "utctime")
        self.assertEqual(result["time_evidence"]["selected"]["timezone_assumption"], "UTC")

    def test_tail_truncates_each_oversized_sample_with_explicit_sizes(self):
        result = serialize_tail_rows([{"log": "x" * (70 * 1024)}], 10)

        raw = result["samples"][0]["raw"]
        self.assertTrue(raw["truncated"])
        self.assertGreater(raw["original_size_bytes"], raw["returned_size_bytes"])
        self.assertLessEqual(raw["returned_size_bytes"], 64 * 1024)
        self.assertEqual(result["warnings"][0]["code"], "SAMPLE_TRUNCATED")

    def test_raw_and_decoded_payload_share_the_per_sample_byte_budget(self):
        row = {
            "value": json.dumps(
                {
                    "log": "x" * (40 * 1024),
                    "dtEventTime": "2026-08-12 10:52:08",
                }
            )
        }

        result = serialize_tail_rows([row], 10, decode_wrapped=True)

        sample = result["samples"][0]
        returned_content_bytes = sample["raw"]["returned_size_bytes"] + sample["decoded"]["returned_size_bytes"]
        self.assertLessEqual(returned_content_bytes, 64 * 1024)
        self.assertEqual(result["time_evidence"]["selected"]["field_name"], "dtEventTime")

    def test_tail_successfully_distinguishes_empty_from_not_found(self):
        result = serialize_tail_rows([], 10)

        self.assertEqual(result["sample_count"], 0)

        probe = call_bkdata(MagicMock(return_value=[]), dict(BKDATA_CONTEXT))
        self.assertEqual(probe["probe_status"], "success")
        self.assertTrue(probe["exists"])
        self.assertTrue(probe["empty"])

    def test_tail_supports_bkbase_datetime_and_compact_utc_fields(self):
        result = serialize_tail_rows(
            [
                {"dtEventTime": "2026-08-12 10:52:08", "utctime": "20260812025208"},
            ],
            10,
        )

        candidates = {item["field_name"]: item for item in result["time_evidence"]["candidates"]}
        self.assertEqual(result["time_evidence"]["selected"]["field_name"], "dtEventTime")
        self.assertEqual(candidates["dtEventTime"]["timezone_assumption"], "Asia/Shanghai")
        self.assertEqual(candidates["utctime"]["timezone_assumption"], "UTC")
        self.assertEqual(candidates["utctime"]["parsed_time"], "2026-08-12T02:52:08+00:00")

    def test_tail_selects_latest_value_from_the_highest_priority_time_field(self):
        result = serialize_tail_rows(
            [
                {"dtEventTimeStamp": 1786503000000, "localTime": "2026-08-12 10:59:59"},
                {"dtEventTimeStamp": 1786503128000, "localTime": "2026-08-12 10:52:14"},
            ],
            10,
        )

        selected = result["time_evidence"]["selected"]
        self.assertEqual(selected["field_name"], "dtEventTimeStamp")
        self.assertEqual(selected["raw_value"], 1786503128000)
        self.assertEqual(result["time_evidence"]["selection_strategy"], "highest_priority_field_latest_value")

    def test_sanitizer_masks_config_secrets_but_not_log_text(self):
        value = {"password": "secret", "nested": {"access_token": "token"}, "log": "password=visible-log"}

        sanitized = sanitize_json(value)

        self.assertEqual(sanitized["password"], "***")
        self.assertEqual(sanitized["nested"]["access_token"], "***")
        self.assertEqual(sanitized["log"], "password=visible-log")

    def test_upstream_error_codes_do_not_guess_permission_from_1511001(self):
        generic_api = MagicMock(side_effect=ApiResultError("generic failure", code=1511001))
        auth_api = MagicMock(side_effect=ApiResultError("No verified user in JWT", code=1511009))

        generic = call_bkdata(generic_api, dict(BKDATA_CONTEXT))
        auth = call_bkdata(auth_api, dict(BKDATA_CONTEXT))

        self.assertEqual(generic["error"]["code"], "UPSTREAM_REQUEST_FAILED")
        self.assertEqual(auth["error"]["code"], "UPSTREAM_AUTH_FAILED")

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_flow_graph")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_latest_deploy_data")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_dataflow")
    def test_invalid_upstream_shape_has_stable_error_code(self, detail_api, deploy_api, graph_api, _context):
        detail_api.return_value = ["unexpected"]
        deploy_api.return_value = {}
        graph_api.return_value = {}

        result = get_bkdata_flow_snapshot({"flow_id": 1, "bk_biz_id": 2})

        self.assertEqual(result["detail"]["probe_status"], "failed")
        self.assertEqual(result["detail"]["error"]["code"], "UPSTREAM_INVALID_RESPONSE")

    def test_data_api_attaches_the_propagated_request_id_to_result_errors(self):
        api = DataAPI(method="GET", url="http://example.test/", module="test")
        response = DataResponse(
            {"result": False, "code": 500, "message": "failed", "data": None},
            "propagated-request-id",
        )
        with patch.object(api, "_send_request", return_value=response), self.assertRaises(ApiResultError) as raised:
            api(params={})

        self.assertEqual(raised.exception.request_id, "propagated-request-id")

    def test_handlers_reject_caller_supplied_bkdata_identity(self):
        with self.assertRaises(ValidationError):
            get_bkdata_raw_snapshot({"raw_data_id": 1, "bk_biz_id": 2, "bk_username": "attacker"})

    @patch("apps.log_admin_resource.handlers.inspection.Space.get_tenant_id", return_value="tenant-a")
    @patch(
        "apps.log_admin_resource.handlers.inspection.get_online_clustering_config",
        return_value={"bk_username": "bkdata-admin"},
    )
    def test_bkdata_context_resolves_internal_user_and_strict_tenant(self, _config, tenant_getter):
        context = build_bkdata_context(2)

        self.assertEqual(context["bk_username"], "bkdata-admin")
        self.assertEqual(context["operator"], "bkdata-admin")
        self.assertEqual(context["bk_tenant_id"], "tenant-a")
        tenant_getter.assert_called_once_with(bk_biz_id=2, is_need_default=False)

    @patch(
        "apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context",
        side_effect=ValidationError("bkdata username is not configured for bk_biz_id=2"),
    )
    def test_missing_internal_bkdata_identity_returns_stable_probe_errors(self, _context):
        result = get_bkdata_flow_snapshot({"flow_id": 1, "bk_biz_id": 2})

        self.assertEqual(result["detail"]["error"]["code"], "BKDATA_IDENTITY_NOT_CONFIGURED")
        self.assertFalse(result["detail"]["error"]["retryable"])
        self.assertEqual(result["latest_deploy"]["probe_status"], "failed")
        self.assertEqual(result["graph"]["probe_status"], "failed")


class BkDataSnapshotResourceTest(TestCase):
    def test_formal_databus_read_apis_are_uncached_and_use_expected_paths(self):
        api = _BkDataDatabusApi()

        expected_paths = {
            "get_clean": "cleans/{processing_id}/",
            "get_tasks": "tasks/{result_table_id}/",
            "get_raw_data_tail": "rawdatas/{raw_data_id}/tail/",
            "get_result_table": "result_tables/{result_table_id}/",
            "get_result_table_tail": "result_tables/{result_table_id}/tail/",
        }
        for name, path in expected_paths.items():
            data_api = getattr(api, name)
            self.assertTrue(data_api.url.endswith(path))
            self.assertEqual(data_api.method, "GET")
            self.assertEqual(data_api.cache_time, 0)

        flow_api = _BkDataDataFlowApi()
        self.assertEqual(flow_api.get_dataflow.cache_time, 0)
        self.assertEqual(flow_api.get_latest_deploy_data.cache_time, 0)
        self.assertEqual(flow_api.get_flow_graph.cache_time, 0)

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_raw_data_tail")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataAccessApi.get_deploy_summary")
    def test_raw_snapshot_returns_deploy_and_full_tail(self, deploy_api, tail_api, _context):
        deploy_api.return_value = {"data_id": 590089, "active": True, "topic": "raw-topic"}
        tail_api.return_value = [{"value": json.dumps({"log": "original", "utctime": "2026-08-12 02:52:08"})}]

        result = get_bkdata_raw_snapshot({"raw_data_id": 590089, "bk_biz_id": 2})

        self.assertEqual(result["deploy"]["data"]["summary"]["topic"], "raw-topic")
        self.assertEqual(result["tail"]["data"]["samples"][0]["decoded"]["value"]["log"], "original")
        self.assertFalse(result["tail"]["empty"])

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_tasks")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_clean")
    def test_clean_snapshot_derives_result_table_and_keeps_task_probe_independent(self, clean_api, tasks_api, _context):
        clean_api.return_value = {
            "processing_id": "2_clean",
            "status": "success",
            "raw_data_id": 590089,
            "result_table_id": "2_bklog_clean",
        }
        tasks_api.side_effect = ApiResultError("task lookup failed", code=500)

        result = get_bkdata_clean_snapshot({"processing_id": "2_clean", "bk_biz_id": 2})

        self.assertEqual(result["result_table_id"], "2_bklog_clean")
        self.assertEqual(result["detail"]["probe_status"], "success")
        self.assertEqual(result["tasks"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_tasks")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_clean")
    def test_clean_task_probe_runs_when_explicit_rt_is_given_even_if_detail_fails(self, clean_api, tasks_api, _context):
        clean_api.side_effect = ApiResultError("clean lookup failed", code=500)
        tasks_api.return_value = [{"id": 1, "status": "running", "result_table_id": "2_clean"}]

        result = get_bkdata_clean_snapshot({"processing_id": "2_clean", "result_table_id": "2_clean", "bk_biz_id": 2})

        self.assertEqual(result["detail"]["probe_status"], "failed")
        self.assertEqual(result["tasks"]["probe_status"], "success")
        self.assertEqual(result["tasks"]["data"]["summary"][0]["status"], "running")

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_flow_graph")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_latest_deploy_data")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDataFlowApi.get_dataflow")
    def test_flow_snapshot_accepts_arbitrary_flow_and_returns_actual_graph(
        self, detail_api, deploy_api, graph_api, _context
    ):
        detail_api.return_value = {"flow_id": 77777, "flow_name": "custom", "status": "RUNNING"}
        deploy_api.return_value = {"deploy_status": "success", "nodes_status": {"1": "running"}}
        graph_api.return_value = {
            "nodes": [{"node_id": 1, "node_name": "source", "node_type": "stream_source"}],
            "links": [{"source": 1, "target": 2}],
        }

        result = get_bkdata_flow_snapshot({"flow_id": 77777, "bk_biz_id": 2})

        self.assertEqual(result["detail"]["data"]["summary"]["flow_id"], 77777)
        self.assertEqual(result["graph"]["data"]["summary"]["node_count"], 1)
        self.assertEqual(result["graph"]["data"]["summary"]["link_count"], 1)

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_result_table_tail")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_result_table")
    def test_result_table_batch_preserves_order_and_partial_success(self, detail_api, tail_api, _context):
        def detail_result(params, **_kwargs):
            return {"result_table_id": params["result_table_id"], "processing_type": "realtime"}

        def tail_result(params, **_kwargs):
            if params["result_table_id"].endswith("failed"):
                raise ApiResultError("tail failed", code=500)
            return [{"log": params["result_table_id"], "dtEventTimeStamp": 1786503128000}]

        detail_api.side_effect = detail_result
        tail_api.side_effect = tail_result

        result = batch_get_bkdata_result_table_snapshots(
            {
                "items": [
                    {"result_table_id": "2_first", "bk_biz_id": 2},
                    {"result_table_id": "2_failed", "bk_biz_id": 2},
                ]
            }
        )

        self.assertEqual([item["result_table_id"] for item in result["items"]], ["2_first", "2_failed"])
        self.assertEqual(result["items"][0]["tail"]["probe_status"], "success")
        self.assertEqual(result["items"][1]["tail"]["probe_status"], "failed")
        self.assertEqual(result["max_concurrency"], 5)
        self.assertEqual(_context.call_count, 1)

    @patch("apps.log_admin_resource.handlers.bkdata_inspection.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_result_table_tail")
    @patch("apps.log_admin_resource.handlers.bkdata_inspection.BkDataDatabusApi.get_result_table")
    def test_result_table_batch_enforces_external_concurrency_limit(self, detail_api, tail_api, _context):
        lock = threading.Lock()
        active_calls = 0
        max_active_calls = 0

        def observe_concurrency(result_factory):
            def call(params, **_kwargs):
                nonlocal active_calls, max_active_calls
                with lock:
                    active_calls += 1
                    max_active_calls = max(max_active_calls, active_calls)
                time.sleep(0.02)
                with lock:
                    active_calls -= 1
                return result_factory(params)

            return call

        detail_api.side_effect = observe_concurrency(lambda params: {"result_table_id": params["result_table_id"]})
        tail_api.side_effect = observe_concurrency(
            lambda params: [{"log": params["result_table_id"], "dtEventTimeStamp": 1786503128000}]
        )

        result = batch_get_bkdata_result_table_snapshots(
            {"items": [{"result_table_id": f"2_rt_{index}", "bk_biz_id": 2} for index in range(10)]}
        )

        self.assertEqual(result["item_count"], 10)
        self.assertGreater(max_active_calls, 1)
        self.assertLessEqual(max_active_calls, 5)
