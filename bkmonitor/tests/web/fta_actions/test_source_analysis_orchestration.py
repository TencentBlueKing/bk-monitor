"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from api.bk_incident.default import (
    CreateSourceAnalysisTaskResource,
    ExecuteSourceAnalysisTaskResource,
    GetSourceAnalysisResultResource,
    GetSourceAnalysisTaskResource,
)
from bkmonitor.models import IssueSourceAnalysisExecution
from constants.issue import (
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStage,
    SourceAnalysisStatus,
)
from fta_web.issue.resources import SourceAnalysisExecutionBaseResource
from fta_web.tasks import recover_source_analysis_executions, run_source_analysis_execution


class NonRetryableBKFaraError(Exception):
    data = {
        "code": "INVALID_ARGUMENT",
        "message": "invalid source analysis input",
        "retryable": False,
        "request_id": "request-1",
    }


class TestSourceAnalysisMockContract(TestCase):
    def test_request_serializers_define_temporary_boundary(self):
        create_request = CreateSourceAnalysisTaskResource.RequestSerializer(
            data={"bk_biz_id": 2, "analysis_id": "analysis-1"}
        )
        self.assertTrue(create_request.is_valid(), create_request.errors)

        execute_request = ExecuteSourceAnalysisTaskResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "task_id": "task-1",
                "analysis_id": "analysis-1",
                "issue_id": "issue-1",
                "alert_id": "alert-1",
                "bkci_project_id": "project-a",
                "repository_alias": "repo-a",
                "agent_id": "agent-a",
                "skill_ids": ["skill-a"],
                "knowledge_base_ids": [],
                "trigger_user": "operator-a",
            }
        )
        self.assertTrue(execute_request.is_valid(), execute_request.errors)
        result_request = GetSourceAnalysisResultResource.RequestSerializer(data={"bk_biz_id": 2, "task_id": "task-1"})
        self.assertTrue(result_request.is_valid(), result_request.errors)
        self.assertIsNone(CreateSourceAnalysisTaskResource.ResponseSerializer)
        self.assertIsNone(ExecuteSourceAnalysisTaskResource.ResponseSerializer)
        self.assertIsNone(GetSourceAnalysisTaskResource.ResponseSerializer)
        self.assertIsNone(GetSourceAnalysisResultResource.ResponseSerializer)

    def test_resources_keep_endpoint_unbound_until_bkfara_publishes_contract(self):
        self.assertEqual(CreateSourceAnalysisTaskResource.action, "")
        self.assertEqual(ExecuteSourceAnalysisTaskResource.action, "")
        self.assertEqual(GetSourceAnalysisTaskResource.action, "")
        self.assertEqual(GetSourceAnalysisResultResource.action, "")

    @patch("api.bk_incident.default.APIResource.perform_request", return_value={"task_id": "task-1"})
    def test_source_analysis_base_preserves_bk_biz_id(self, perform_request):
        request_data = {"bk_biz_id": 2, "analysis_id": "analysis-1"}
        resource = CreateSourceAnalysisTaskResource()

        result = resource.perform_request(request_data)

        self.assertEqual(result, {"task_id": "task-1"})
        perform_request.assert_called_once_with(resource, request_data)


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

    @patch("fta_web.issue.resources.api.bk_incident.execute_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_task_id_is_persisted_before_execute(self, create_task, execute_task):
        execution = self.create_execution()
        create_task.return_value = {"task_id": "task-1"}

        def execute(**params):
            persisted = IssueSourceAnalysisExecution.objects.get(pk=execution.pk)
            self.assertEqual(persisted.bkfara_task_id, "task-1")
            self.assertEqual(params["task_id"], "task-1")
            return {
                "status": "running",
                "stage": "analyzing",
            }

        execute_task.side_effect = execute

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execution.refresh_from_db()
        create_task.assert_called_once_with(bk_biz_id=2, analysis_id=execution.analysis_id)
        execute_task.assert_called_once_with(
            bk_biz_id=2,
            task_id="task-1",
            analysis_id=execution.analysis_id,
            issue_id="issue-1",
            alert_id="alert-1",
            bkci_project_id="project-a",
            repository_alias="repo-a",
            agent_id="agent-a",
            skill_ids=["skill-a", "skill-b"],
            knowledge_base_ids=["knowledge-a"],
            trigger_user=execution.create_user,
        )
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.ANALYZING)

    @patch("fta_web.issue.resources.api.bk_incident.execute_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_existing_task_queries_before_deciding_to_execute(self, get_task, create_task, execute_task):
        execution = self.create_execution(bkfara_task_id="task-1")
        get_task.return_value = {"status": "running", "stage": "source_preparing"}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        get_task.assert_called_once_with(bk_biz_id=2, task_id="task-1")
        create_task.assert_not_called()
        execute_task.assert_not_called()

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_stale_worker_stops_when_execution_version_has_advanced(self, create_task, get_task):
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

        with patch.object(
            IssueSourceAnalysisExecution.objects,
            "filter",
            side_effect=return_stale_execution,
        ):
            should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        create_task.assert_not_called()
        get_task.assert_not_called()

    @patch("fta_web.issue.resources.api.bk_incident.execute_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_created_task_is_resumed_without_recreating(self, get_task, execute_task):
        execution = self.create_execution(bkfara_task_id="task-1")
        get_task.return_value = {"status": "created"}
        execute_task.return_value = {"status": "running", "stage": "analyzing"}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execute_task.assert_called_once()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.execute_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_execute_timeout_queries_state_before_retry(self, create_task, execute_task, get_task):
        execution = self.create_execution()
        create_task.return_value = {"task_id": "task-1"}
        execute_task.side_effect = TimeoutError("timeout")
        get_task.return_value = {"status": "running", "stage": "analyzing"}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execute_task.assert_called_once()
        get_task.assert_called_once_with(bk_biz_id=2, task_id="task-1")
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_task_id, "task-1")
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    @patch("fta_web.issue.resources.api.bk_incident.execute_source_analysis_task")
    def test_non_retryable_execute_error_marks_failure_without_recovery_query(self, execute_task, get_task):
        execution = self.create_execution(bkfara_task_id="task-1")
        get_task.return_value = {"status": "created"}
        execute_task.side_effect = NonRetryableBKFaraError()

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        get_task.assert_called_once_with(bk_biz_id=2, task_id="task-1")
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.TASK_EXECUTE)
        self.assertEqual(execution.failure_code, "INVALID_ARGUMENT")
        self.assertFalse(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_retryable_create_error_keeps_pending_record(self, create_task):
        execution = self.create_execution()
        create_task.side_effect = TimeoutError("timeout")

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)
        self.assertIsNone(execution.bkfara_task_id)

    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_non_retryable_create_error_marks_failure(self, create_task):
        execution = self.create_execution()
        create_task.side_effect = NonRetryableBKFaraError()

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.TASK_CREATE)
        self.assertEqual(execution.failure_code, "INVALID_ARGUMENT")
        self.assertFalse(execution.failure_retryable)
        self.assertEqual(execution.failure_request_id, "request-1")

    @patch("fta_web.issue.resources.api.bk_incident.create_source_analysis_task")
    def test_invalid_create_response_is_terminal_protocol_error(self, create_task):
        execution = self.create_execution()
        create_task.return_value = {}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "BKFARA_INVALID_RESPONSE")

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_invalid_task_state_is_terminal_protocol_error(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "unknown"}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.TASK_EXECUTE)
        self.assertEqual(execution.failure_code, "BKFARA_INVALID_RESPONSE")
        self.assertFalse(execution.failure_retryable)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_remote_failure_maps_failure_metadata(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "failed",
            "failure": {
                "stage": "ai_analysis",
                "code": "ANALYSIS_FAILED",
                "message": "analysis failed",
                "retryable": True,
                "request_id": "request-2",
            },
        }

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.AI_ANALYSIS)
        self.assertEqual(execution.failure_code, "ANALYSIS_FAILED")
        self.assertTrue(execution.failure_retryable)
        self.assertEqual(execution.failure_request_id, "request-2")

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_result")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_remote_success_persists_valid_result(self, get_task, get_result):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "success"}
        get_result.return_value = self.build_result()

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        get_result.assert_called_once_with(bk_biz_id=2, task_id="task-1")
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertIsNone(execution.stage)
        self.assertEqual(execution.result_schema_version, "1.0.0")
        self.assertEqual(execution.result_type, SourceAnalysisResultType.HIGH_CONFIDENCE)
        self.assertEqual(execution.result_payload, get_result.return_value)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_result")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_insufficient_evidence_is_persisted_as_success(self, get_task, get_result):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "success"}
        get_result.return_value = self.build_result(SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertEqual(execution.result_type, SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_result")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_result_fetch_timeout_keeps_validating_for_retry(self, get_task, get_result):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "success"}
        get_result.side_effect = TimeoutError("timeout")

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.VALIDATING)

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_result")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_invalid_result_marks_retryable_validation_failure(self, get_task, get_result):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "success"}
        get_result.return_value = {"schema_version": "1.0.0"}

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertFalse(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.RESULT_VALIDATE)
        self.assertEqual(execution.failure_code, "RESULT_SCHEMA_INVALID")
        self.assertTrue(execution.failure_retryable)
        self.assertIsNone(execution.result_payload)

    @patch.object(IssueSourceAnalysisExecution, "mark_success", side_effect=DatabaseError("database unavailable"))
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_result")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_result_persist_error_keeps_validating_for_retry(self, get_task, get_result, _mark_success):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {"status": "success"}
        get_result.return_value = self.build_result()

        should_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertTrue(should_poll)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.VALIDATING)
        self.assertIsNone(execution.result_payload)

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
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task", return_value=True)
    def test_active_execution_schedules_next_poll(self, advance, apply_async):
        run_source_analysis_execution.run("analysis-1")

        advance.assert_called_once_with("analysis-1")
        apply_async.assert_called_once_with(args=("analysis-1",), countdown=10)

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
