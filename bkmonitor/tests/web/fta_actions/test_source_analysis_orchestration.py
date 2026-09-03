"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from api.bk_incident.default import (
    BkFaraSourceAnalysisBaseResource,
    EnsureSourceAnalysisSceneResource,
    GetSourceAnalysisSceneStatusResource,
    GetSourceAnalysisTaskResource,
    TriggerSourceAnalysisResource,
)
from bkmonitor.models import IssueSourceAnalysisExecution
from constants.issue import (
    SourceAnalysisFailureMessage,
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStage,
    SourceAnalysisStatus,
)
from fta_web.issue.resources import SourceAnalysisExecutionBaseResource, build_bkfara_client_request_id
from fta_web.tasks import recover_source_analysis_executions, run_source_analysis_execution


class NonRetryableBKFaraError(Exception):
    data = {
        "code": "INVALID_ARGUMENT",
        "message": "invalid source analysis input",
        "retryable": False,
        "request_id": "request-1",
    }


class TestSourceAnalysisContract(TestCase):
    CLIENT_REQUEST_ID = "43c3ca39-d60f-4482-854d-00f771e149fb"

    def test_request_serializers_define_four_interface_contract(self):
        ensure_request = EnsureSourceAnalysisSceneResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "devops_project_id": "project-a",
                "client_request_id": self.CLIENT_REQUEST_ID,
            }
        )
        self.assertTrue(ensure_request.is_valid(), ensure_request.errors)
        self.assertNotIn("issue_id", ensure_request.validated_data)

        scene_request = GetSourceAnalysisSceneStatusResource.RequestSerializer(
            data={"provision_id": "provision-1", "bk_tenant_id": "system"}
        )
        self.assertTrue(scene_request.is_valid(), scene_request.errors)

        trigger_request = TriggerSourceAnalysisResource.RequestSerializer(
            data={
                "issue_id": "issue-1",
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "devops_project_id": "project-a",
                "client_request_id": self.CLIENT_REQUEST_ID,
                "inputs": {
                    "bk_biz_id": 2,
                    "bk_tenant_id": "system",
                    "repository_alias": "repo-a",
                    "agent_id": "agent-a",
                    "skill_ids": ["skill-a"],
                    "knowledge_base_ids": [],
                    "issue_context": {"alert_ids": ["alert-1"]},
                },
            }
        )
        self.assertTrue(trigger_request.is_valid(), trigger_request.errors)

        task_request = GetSourceAnalysisTaskResource.RequestSerializer(
            data={"analysis_task_id": "task-1", "bk_tenant_id": "system"}
        )
        self.assertTrue(task_request.is_valid(), task_request.errors)

    def test_invalid_client_request_id_is_rejected(self):
        request = EnsureSourceAnalysisSceneResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "devops_project_id": "project-a",
                "client_request_id": "not-a-uuid",
            }
        )

        self.assertFalse(request.is_valid())
        self.assertIn("client_request_id", request.errors)

    def test_trigger_inputs_reject_unknown_fields(self):
        request = TriggerSourceAnalysisResource.RequestSerializer(
            data={
                "issue_id": "issue-1",
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "devops_project_id": "project-a",
                "client_request_id": self.CLIENT_REQUEST_ID,
                "inputs": {
                    "bk_biz_id": 2,
                    "bk_tenant_id": "system",
                    "repository_alias": "repo-a",
                    "agent_id": "agent-a",
                    "source_analysis_raw": {},
                },
            }
        )

        self.assertFalse(request.is_valid())
        self.assertIn("source_analysis_raw", request.errors["inputs"])

    def test_resources_bind_formal_endpoints(self):
        self.assertEqual(EnsureSourceAnalysisSceneResource.action, "/incident/issue_analysis/ensure_scene/")
        self.assertEqual(
            GetSourceAnalysisSceneStatusResource.action,
            "/incident/issue_analysis/get_scene_status/",
        )
        self.assertEqual(TriggerSourceAnalysisResource.action, "/incident/issue_analysis/trigger/")
        self.assertEqual(GetSourceAnalysisTaskResource.action, "/incident/issue_analysis/get_task/")

    def test_http_error_body_is_normalized_to_protocol_error(self):
        response = {
            "result": False,
            "code": "ACTIVE_TASK_EXISTS",
            "error": {
                "code": "ACTIVE_TASK_EXISTS",
                "message": "active task exists",
                "retryable": False,
                "details": {},
            },
        }

        error_data = BkFaraSourceAnalysisBaseResource._normalize_error_data(
            {"message": repr(json.dumps(response).encode())}
        )

        self.assertEqual(error_data["code"], "ACTIVE_TASK_EXISTS")
        self.assertFalse(error_data["retryable"])
        self.assertNotIn("analysis_task_id", error_data)


class TestSourceAnalysisOrchestration(TestCase):
    databases = {"default", "monitor_api"}

    @staticmethod
    def create_execution(**kwargs) -> IssueSourceAnalysisExecution:
        defaults = {
            "bk_biz_id": 2,
            "issue_id": "issue-1",
            "status": SourceAnalysisStatus.PENDING,
            "stage": SourceAnalysisStage.WAITING,
            "alert_id": "alert-1",
            "rule_id": 10,
            "rule_priority": 100,
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "skill_ids": ["skill-a", "skill-b"],
            "knowledge_base_ids": ["knowledge-a"],
            "bkfara_provision_id": "provision-1",
            "create_user": "operator-a",
            "update_user": "operator-a",
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisExecution.objects.create(**defaults)

    @staticmethod
    def build_result(result_type=SourceAnalysisResultType.HIGH_CONFIDENCE) -> dict:
        responsibility = None
        if result_type == SourceAnalysisResultType.HIGH_CONFIDENCE:
            responsibility = {
                "commit_id": "a3fa531",
                "commit_message": "restore session guard",
                "author_name": "Edwin Wu",
                "bk_username": "edwinwu",
            }
        return {
            "schema_version": "1.0.0",
            "result_type": result_type,
            "result_card": {
                "description": "Session 空值检查缺失导致异常。",
                "responsibility": responsibility,
            },
            "content_type": "text/markdown",
            "content": "# 分析结论\n\nSession 空值检查缺失导致异常。",
        }

    @staticmethod
    def ready_scene_state() -> dict:
        return {
            "provision_id": "provision-1",
            "status": "ready",
            "terminal": True,
            "phase": None,
        }

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_ready_scene_triggers_and_persists_task(self, get_scene, trigger):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()
        trigger.return_value = {
            "analysis_task_id": "task-1",
            "status": "queued",
            "terminal": False,
            "phase": "bkflow_starting",
            "next_poll_after_seconds": 4,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 4)
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_task_id, "task-1")
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.SOURCE_PREPARING)
        trigger.assert_called_once_with(
            issue_id="issue-1",
            bk_biz_id=2,
            bk_tenant_id="system",
            devops_project_id="project-a",
            client_request_id=build_bkfara_client_request_id("trigger", execution.analysis_id),
            inputs={
                # 业务与租户标识和顶层重复：inputs 会被 BKFara 整体透传给蓝盾流水线。
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "repository_alias": "repo-a",
                "agent_id": "agent-a",
                "skill_ids": ["skill-a", "skill-b"],
                "knowledge_base_ids": ["knowledge-a"],
                "issue_context": {"alert_ids": ["alert-1"]},
            },
        )

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_provisioning_scene_uses_server_poll_interval(self, get_scene, trigger):
        execution = self.create_execution()
        get_scene.return_value = {
            "provision_id": "provision-1",
            "status": "provisioning",
            "terminal": False,
            "phase": "copying_flow",
            "next_poll_after_seconds": 2,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 2)
        trigger.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene")
    def test_missing_provision_id_is_initialized_and_persisted(self, ensure_scene, trigger):
        execution = self.create_execution(bkfara_provision_id=None)
        ensure_scene.return_value = {
            "provision_id": "provision-2",
            "status": "provisioning",
            "terminal": False,
            "next_poll_after_seconds": 3,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 3)
        trigger.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_provision_id, "provision-2")
        ensure_scene.assert_called_once_with(**SourceAnalysisExecutionBaseResource.build_ensure_scene_params(execution))

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_terminal_scene_failure_maps_failure_metadata(self, get_scene):
        execution = self.create_execution()
        get_scene.return_value = {
            "provision_id": "provision-1",
            "status": "failed",
            "terminal": True,
            "error": {
                "code": "SCENE_BINDING_DRIFTED",
                "message": "scene binding drifted",
                # 场景终态尚无重建协议，即使上游标记可重试也不能开放分析任务重试。
                "retryable": True,
            },
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "SCENE_BINDING_DRIFTED")
        self.assertFalse(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_existing_task_queries_only_and_keeps_start_unknown_active(self, get_task, trigger):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "analysis_task_id": "task-1",
            "status": "running",
            "terminal": False,
            "phase": "start_unknown",
            "next_poll_after_seconds": 7,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 7)
        get_task.assert_called_once_with(analysis_task_id="task-1", bk_tenant_id="system")
        trigger.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.stage, SourceAnalysisStage.SOURCE_PREPARING)

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_trigger_timeout_keeps_pending_for_same_idempotent_request(self, get_scene, trigger):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()
        trigger.side_effect = TimeoutError("timeout")

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 10)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)
        self.assertIsNone(execution.bkfara_task_id)
        first_request_id = trigger.call_args.kwargs["client_request_id"]
        self.assertEqual(
            first_request_id,
            SourceAnalysisExecutionBaseResource.build_trigger_params(execution)["client_request_id"],
        )

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_non_retryable_trigger_error_marks_failure(self, get_scene, trigger):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()
        trigger.side_effect = NonRetryableBKFaraError()

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.TASK_CREATE)
        self.assertEqual(execution.failure_code, "INVALID_ARGUMENT")
        self.assertFalse(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis", return_value={})
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_invalid_trigger_response_is_terminal_protocol_error(self, get_scene, _trigger):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "BKFARA_INVALID_RESPONSE")
        self.assertEqual(execution.failure_message, SourceAnalysisFailureMessage.BKFARA_TRIGGER_MISSING_TASK_ID)

    @patch.object(SourceAnalysisExecutionBaseResource, "build_trigger_params", side_effect=AttributeError("bad code"))
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_local_trigger_parameter_error_is_not_treated_as_upstream_retry(self, get_scene, _build_params):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()

        with self.assertRaisesMessage(AttributeError, "bad code"):
            SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)
        self.assertIsNone(execution.bkfara_task_id)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_query_failure_never_retriggers_existing_task(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.side_effect = TimeoutError("timeout")

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(poll_interval, 10)
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_task_id, "task-1")
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_invalid_task_state_is_terminal_protocol_error(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "running"}

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "BKFARA_INVALID_RESPONSE")
        self.assertFalse(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_remote_failure_maps_error_and_details(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "failed",
            "terminal": True,
            "result": None,
            "error": {
                "code": "ANALYSIS_FAILED",
                "message": "analysis failed",
                "retryable": True,
                "details": {"stage": "ai_analysis"},
            },
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.AI_ANALYSIS)
        self.assertEqual(execution.failure_code, "ANALYSIS_FAILED")
        self.assertTrue(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_remote_success_persists_inline_result(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        result = self.build_result()
        get_task.return_value = {
            "status": "succeeded",
            "terminal": True,
            "result": result,
            "error": None,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertIsNone(execution.stage)
        self.assertEqual(execution.result_schema_version, "1.0.0")
        self.assertEqual(execution.result_type, SourceAnalysisResultType.HIGH_CONFIDENCE)
        self.assertEqual(execution.result_payload, result)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_insufficient_evidence_is_persisted_as_success(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "succeeded",
            "terminal": True,
            "result": self.build_result(SourceAnalysisResultType.INSUFFICIENT_EVIDENCE),
            "error": None,
        }

        SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertEqual(execution.result_type, SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_invalid_inline_result_marks_retryable_validation_failure(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "succeeded",
            "terminal": True,
            "result": {"schema_version": "1.0.0"},
            "error": None,
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.RESULT_VALIDATE)
        self.assertEqual(execution.failure_code, "RESULT_SCHEMA_INVALID")
        self.assertTrue(execution.failure_retryable)
        self.assertEqual(execution.failure_message, SourceAnalysisFailureMessage.RESULT_SCHEMA_INVALID)

    @patch.object(IssueSourceAnalysisExecution, "mark_success", side_effect=DatabaseError("database unavailable"))
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_result_persist_error_propagates(self, get_task, _mark_success):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "succeeded",
            "terminal": True,
            "result": self.build_result(),
            "error": None,
        }

        with self.assertRaisesMessage(DatabaseError, "database unavailable"):
            SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.VALIDATING)
        self.assertIsNone(execution.result_payload)

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_stale_worker_stops_before_upstream_call(self, get_scene, trigger):
        execution = self.create_execution()
        IssueSourceAnalysisExecution.objects.filter(pk=execution.pk).update(
            update_time=execution.update_time + timedelta(seconds=1)
        )
        real_filter = IssueSourceAnalysisExecution.objects.filter

        def return_stale_execution(*args, **kwargs):
            if kwargs == {"analysis_id": execution.analysis_id}:
                result = MagicMock()
                result.first.return_value = execution
                return result
            return real_filter(*args, **kwargs)

        with patch.object(IssueSourceAnalysisExecution.objects, "filter", side_effect=return_stale_execution):
            poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        get_scene.assert_not_called()
        trigger.assert_not_called()

    @patch.object(run_source_analysis_execution, "apply_async", side_effect=RuntimeError("broker unavailable"))
    def test_dispatch_error_is_left_for_periodic_recovery(self, apply_async):
        execution = self.create_execution()

        SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        apply_async.assert_called_once_with(args=(execution.analysis_id,))

    def test_recovery_only_returns_stale_active_records(self):
        stale = self.create_execution(issue_id="issue-stale")
        fresh = self.create_execution(issue_id="issue-fresh")
        terminal = self.create_execution(issue_id="issue-terminal", status=SourceAnalysisStatus.FAILED)
        stale_time = timezone.now() - timedelta(seconds=SourceAnalysisExecutionBaseResource.RECOVERY_STALE_SECONDS + 1)
        IssueSourceAnalysisExecution.objects.filter(pk__in=[stale.pk, terminal.pk]).update(update_time=stale_time)

        analysis_ids = SourceAnalysisExecutionBaseResource.get_recoverable_analysis_ids()

        self.assertEqual(analysis_ids, [stale.analysis_id])
        self.assertNotIn(fresh.analysis_id, analysis_ids)


class TestSourceAnalysisCeleryTasks(TestCase):
    @patch.object(run_source_analysis_execution, "apply_async")
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task", return_value=3)
    def test_active_execution_schedules_server_interval(self, advance, apply_async):
        run_source_analysis_execution.run("analysis-1")

        advance.assert_called_once_with("analysis-1")
        apply_async.assert_called_once_with(args=("analysis-1",), countdown=3)

    @patch.object(run_source_analysis_execution, "apply_async")
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task", return_value=None)
    def test_terminal_execution_is_not_rescheduled(self, _advance, apply_async):
        run_source_analysis_execution.run("analysis-1")

        apply_async.assert_not_called()

    @patch.object(run_source_analysis_execution, "apply_async")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_recoverable_analysis_ids")
    def test_recovery_dispatches_each_stale_execution(self, get_ids, apply_async):
        get_ids.return_value = ["analysis-1", "analysis-2"]

        recover_source_analysis_executions.run()

        self.assertEqual(
            apply_async.call_args_list,
            [
                call(args=("analysis-1",)),
                call(args=("analysis-2",)),
            ],
        )
