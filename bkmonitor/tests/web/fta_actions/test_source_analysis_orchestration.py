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
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from bkoauth.client import oauth_client
from bkoauth.exceptions import TokenException, TokenNotExist
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from requests import Request

from api.bk_incident.default import (
    BkFaraSourceAnalysisBaseResource,
    EnsureSourceAnalysisSceneResource,
    GetSourceAnalysisSceneStatusResource,
    GetSourceAnalysisTaskResource,
    TriggerSourceAnalysisResource,
)
from bkmonitor.models import IssueSourceAnalysisExecution
from constants.issue import (
    SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER,
    SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER,
    SourceAnalysisFailureMessage,
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStage,
    SourceAnalysisStatus,
)
from fta_web.issue.resources import (
    SourceAnalysisExecutionBaseResource,
    build_bkfara_client_request_id,
)
from fta_web.tasks import recover_source_analysis_executions, run_source_analysis_execution


class NonRetryableBKFaraError(Exception):
    data = {
        "code": "INVALID_ARGUMENT",
        "message": "invalid source analysis input",
        "retryable": False,
        "request_id": "request-1",
    }


class TestSourceAnalysisContract(SimpleTestCase):
    CLIENT_REQUEST_ID = "43c3ca39-d60f-4482-854d-00f771e149fb"

    def test_bkfara_runtime_placeholders_match_protocol(self):
        self.assertEqual(SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER, "__BKFARA_TASK_ID__")
        self.assertEqual(SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER, "__BKAICLI_ACCESS_TOKEN__")

    def test_failed_task_trace_is_normalized_before_persistence(self):
        execution = SimpleNamespace(analysis_id="analysis-1", mark_failed=MagicMock())
        task_state = {
            "status": "failed",
            "terminal": True,
            "error": {
                "code": "DEVOPS_BUILD_FAILED",
                "message": "pipeline failed",
                "retryable": False,
                "details": {},
            },
            "trace": {
                "incident_task_id": 142,
                "flow_task_id": "250",
                "devops_project_id": "project-a",
                "pipeline_id": "pipeline-a",
                "build_id": "build-a",
                "console_url": None,
            },
        }

        SourceAnalysisExecutionBaseResource._apply_bkfara_task_state(execution, task_state)

        execution.mark_failed.assert_called_once_with(
            failure_stage=SourceAnalysisFailureStage.TASK_EXECUTE,
            failure_code="DEVOPS_BUILD_FAILED",
            failure_message="pipeline failed",
            failure_retryable=False,
            failure_request_id=None,
            execution_reference={
                "provider": "bkci",
                "identifiers": {
                    "project_id": "project-a",
                    "pipeline_id": "pipeline-a",
                    "build_id": "build-a",
                },
            },
        )

    def test_incomplete_task_trace_does_not_create_execution_reference(self):
        task_state = {
            "trace": {
                "devops_project_id": "project-a",
                "pipeline_id": "pipeline-a",
                "build_id": None,
            }
        }

        self.assertIsNone(SourceAnalysisExecutionBaseResource.normalize_execution_reference(task_state))

    @override_settings(BK_CI_URL="https://devops.example.com/")
    def test_bkci_execution_reference_uses_canonical_detail_url(self):
        result = SourceAnalysisExecutionBaseResource.serialize_execution_reference(
            {
                "provider": "bkci",
                "identifiers": {
                    "project_id": "project with space",
                    "pipeline_id": "pipeline-a",
                    "build_id": "build-a",
                },
            }
        )

        self.assertEqual(
            result["url"],
            (
                "https://devops.example.com/console/pipeline/project%20with%20space/"
                "pipeline-a/detail/build-a/executeDetail"
            ),
        )

    def test_request_serializers_define_four_interface_contract(self):
        ensure_request = EnsureSourceAnalysisSceneResource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "devops_project_id": "project-a",
                "client_request_id": self.CLIENT_REQUEST_ID,
                "bk_username": "operator-a",
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
                "bk_username": "operator-a",
                "inputs": {
                    "bk_biz_id": 2,
                    "bk_tenant_id": "system",
                    "repository_alias": "repo-a",
                    "agent_id": "agent-a",
                    "skill_ids": "skill-a",
                    "knowledge_base_ids": "",
                    "alert_id": "alert-1",
                    "BKFARA_TASK_ID": SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER,
                    "BKAI_AIDEV_API_KEY": SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER,
                },
            }
        )
        self.assertTrue(trigger_request.is_valid(), trigger_request.errors)
        self.assertNotIn("access_token", ensure_request.fields)
        self.assertNotIn("access_token", trigger_request.fields)

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

    def test_trigger_inputs_reject_runtime_values_instead_of_placeholders(self):
        valid_inputs = {
            "bk_biz_id": 2,
            "bk_tenant_id": "system",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "alert_id": "alert-1",
            "BKFARA_TASK_ID": SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER,
            "BKAI_AIDEV_API_KEY": SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER,
        }
        invalid_values = {
            "BKFARA_TASK_ID": "task-1",
            "BKAI_AIDEV_API_KEY": "real-access-token",
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                inputs = {**valid_inputs, field: value}
                request = TriggerSourceAnalysisResource.RequestSerializer(
                    data={
                        "issue_id": "issue-1",
                        "bk_biz_id": 2,
                        "bk_tenant_id": "system",
                        "devops_project_id": "project-a",
                        "client_request_id": self.CLIENT_REQUEST_ID,
                        "inputs": inputs,
                    }
                )

                self.assertFalse(request.is_valid())
                self.assertIn(field, request.errors["inputs"])

    def test_resources_bind_formal_endpoints(self):
        self.assertEqual(EnsureSourceAnalysisSceneResource.action, "/incident/issue_analysis/ensure_scene/")
        self.assertEqual(
            GetSourceAnalysisSceneStatusResource.action,
            "/incident/issue_analysis/get_scene_status/",
        )
        self.assertEqual(TriggerSourceAnalysisResource.action, "/incident/issue_analysis/trigger/")
        self.assertEqual(GetSourceAnalysisTaskResource.action, "/incident/issue_analysis/get_task/")

    @patch("api.bk_incident.default.settings.SECRET_KEY", "app-secret")
    @patch("api.bk_incident.default.settings.APP_CODE", "bkmonitorv3")
    def test_bkfara_user_access_token_is_sent_only_in_gateway_authorization_header(self):
        resource = TriggerSourceAnalysisResource()
        with patch.object(resource, "_get_user_access_token", return_value="user-access-token") as get_token:
            client = resource._build_client("system", "operator-a")

        request = client.session.prepare_request(Request("POST", "https://bkfara.example.com/trigger/"))

        get_token.assert_called_once_with("operator-a")
        self.assertEqual(client.session.headers["X-Bk-Tenant-Id"], "system")
        self.assertEqual(json.loads(request.headers["X-Bkapi-Authorization"]), {"access_token": "user-access-token"})

    @patch("api.bk_incident.default.settings.SECRET_KEY", "app-secret")
    @patch("api.bk_incident.default.settings.APP_CODE", "bkmonitorv3")
    def test_status_query_keeps_application_authorization(self):
        resource = GetSourceAnalysisTaskResource()
        with patch.object(resource, "_get_user_access_token") as get_token:
            client = resource._build_client("system")

        request = client.session.prepare_request(Request("GET", "https://bkfara.example.com/get_task/"))

        get_token.assert_not_called()
        self.assertEqual(
            json.loads(request.headers["X-Bkapi-Authorization"]),
            {"bk_app_code": "bkmonitorv3", "bk_app_secret": "app-secret"},
        )

    @patch("api.bk_incident.default.oauth_client.get_access_token")
    @patch("api.bk_incident.default.get_request")
    def test_web_request_uses_bkoauth_current_login(self, get_request, get_access_token):
        get_access_token.return_value = SimpleNamespace(access_token="web-access-token")

        access_token = TriggerSourceAnalysisResource._get_user_access_token()

        get_request.assert_called_once_with(peaceful=True)
        get_access_token.assert_called_once_with(get_request.return_value)
        self.assertEqual(access_token, "web-access-token")

    @patch("api.bk_incident.default.oauth_client.get_access_token_by_user")
    @patch("api.bk_incident.default.get_request")
    def test_celery_uses_bkoauth_token_by_execution_user(self, get_request, get_access_token_by_user):
        get_access_token_by_user.return_value = SimpleNamespace(access_token="worker-access-token")

        access_token = TriggerSourceAnalysisResource._get_user_access_token("operator-a")

        get_request.assert_not_called()
        get_access_token_by_user.assert_called_once_with("operator-a")
        self.assertEqual(access_token, "worker-access-token")

    @patch(
        "api.bk_incident.default.oauth_client.get_access_token_by_user",
        side_effect=TokenNotExist("token unavailable"),
    )
    def test_missing_persisted_token_is_reported_as_missing_user_token(self, _get_access_token_by_user):
        with self.assertRaises(TokenNotExist):
            TriggerSourceAnalysisResource._get_user_access_token("operator-a")

    @patch(
        "api.bk_incident.default.oauth_client.get_access_token_by_user",
        side_effect=DatabaseError("database unavailable"),
    )
    def test_token_storage_error_is_not_hidden_as_missing_user_token(self, _get_access_token_by_user):
        with self.assertRaisesMessage(DatabaseError, "database unavailable"):
            TriggerSourceAnalysisResource._get_user_access_token("operator-a")

    def test_bk_username_and_access_token_do_not_enter_bkfara_request_body(self):
        resource = TriggerSourceAnalysisResource()
        operation = MagicMock(return_value={"result": True, "code": "OK", "data": {"status": "running"}})
        client = MagicMock()
        client.source_analysis.trigger = operation
        request_data = {
            "bk_biz_id": 2,
            "bk_tenant_id": "system",
            "bk_username": "operator-a",
        }

        with patch.object(resource, "_build_client", return_value=client) as build_client:
            result = resource.perform_request(request_data)

        self.assertEqual(result, {"status": "running"})
        build_client.assert_called_once_with("system", "operator-a")
        operation.assert_called_once_with(
            data={"bk_biz_id": 2, "bk_tenant_id": "system"},
            timeout=resource.TIMEOUT,
        )
        self.assertNotIn("access_token", request_data)

    def test_web_request_uses_access_token_client_without_exposing_credentials(self):
        resource = TriggerSourceAnalysisResource()
        operation = MagicMock(return_value={"result": True, "code": "OK", "data": {"status": "running"}})
        client = MagicMock()
        client.source_analysis.trigger = operation
        request_data = {"bk_biz_id": 2, "bk_tenant_id": "system"}

        with patch.object(resource, "_build_client", return_value=client) as build_client:
            result = resource.perform_request(request_data)

        self.assertEqual(result, {"status": "running"})
        build_client.assert_called_once_with("system", "")
        operation.assert_called_once_with(data=request_data, timeout=resource.TIMEOUT)
        self.assertNotIn("access_token", request_data)

    @patch("fta_web.issue.resources.bk_biz_id_to_bk_tenant_id", return_value="system")
    def test_execution_params_use_rule_configurer_and_runtime_placeholders(self, _get_tenant_id):
        execution = SimpleNamespace(
            analysis_id="analysis-1",
            issue_id="issue-1",
            bk_biz_id=2,
            bkci_project_id="project-a",
            repository_alias="repo-a",
            agent_id="agent-a",
            skill_ids=["skill-a", "skill-b"],
            knowledge_base_ids=["knowledge-a"],
            alert_id="alert-1",
            create_user="operator-a",
            run_as_user="configurator-a",
        )

        ensure_params = SourceAnalysisExecutionBaseResource.build_ensure_scene_params(execution)
        trigger_params = SourceAnalysisExecutionBaseResource.build_trigger_params(execution)

        self.assertEqual(ensure_params["bk_username"], "configurator-a")
        self.assertEqual(trigger_params["bk_username"], "configurator-a")
        self.assertEqual(
            ensure_params["client_request_id"],
            build_bkfara_client_request_id("ensure-scene", "system", 2, "project-a", "analysis-1"),
        )
        self.assertEqual(
            trigger_params["inputs"]["BKFARA_TASK_ID"],
            SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER,
        )
        self.assertEqual(
            trigger_params["inputs"]["BKAI_AIDEV_API_KEY"],
            SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER,
        )

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
            "run_as_user": "configurator-a",
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
            bk_username=execution.run_as_user,
            client_request_id=build_bkfara_client_request_id("trigger", execution.analysis_id),
            inputs={
                # 业务与租户标识和顶层重复：inputs 除运行时占位符外会被 BKFara
                # 透传给蓝盾流水线。
                "bk_biz_id": 2,
                "bk_tenant_id": "system",
                "repository_alias": "repo-a",
                "agent_id": "agent-a",
                "skill_ids": "skill-a,skill-b",
                "knowledge_base_ids": "knowledge-a",
                "alert_id": "alert-1",
                "BKFARA_TASK_ID": SOURCE_ANALYSIS_BKFARA_TASK_ID_PLACEHOLDER,
                "BKAI_AIDEV_API_KEY": SOURCE_ANALYSIS_BKAI_AIDEV_API_KEY_PLACEHOLDER,
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
        ensure_scene.assert_called_once_with(
            **SourceAnalysisExecutionBaseResource.build_ensure_scene_params(execution),
        )

    @patch("fta_web.issue.resources.api.bk_incident.trigger_source_analysis")
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    @patch("fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene")
    def test_scene_is_ensured_once_before_trigger(self, ensure_scene, get_scene, trigger):
        execution = self.create_execution(bkfara_provision_id=None)
        ensure_scene.return_value = {
            "provision_id": "provision-2",
            "status": "provisioning",
            "terminal": False,
            "next_poll_after_seconds": 2,
        }
        get_scene.return_value = {
            "provision_id": "provision-2",
            "status": "ready",
            "terminal": True,
        }
        trigger.return_value = {
            "analysis_task_id": "task-2",
            "status": "running",
            "terminal": False,
            "phase": "devops_running",
            "next_poll_after_seconds": 4,
        }

        first_poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)
        second_poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertEqual(first_poll_interval, 2)
        self.assertEqual(second_poll_interval, 4)
        ensure_scene.assert_called_once()
        get_scene.assert_called_once_with(provision_id="provision-2", bk_tenant_id="system")
        trigger.assert_called_once()
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_provision_id, "provision-2")
        self.assertEqual(execution.bkfara_task_id, "task-2")

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
                # 场景终态尚无重建协议，即使上游标记可重试也不由系统自动重试。
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
            "trace": {
                "incident_task_id": 142,
                "flow_task_id": "250",
                "devops_project_id": "project-a",
                "pipeline_id": "pipeline-a",
                "build_id": "build-a",
                "console_url": None,
            },
        }

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.AI_ANALYSIS)
        self.assertEqual(execution.failure_code, "ANALYSIS_FAILED")
        self.assertTrue(execution.failure_retryable)
        self.assertEqual(
            execution.execution_reference,
            {
                "provider": "bkci",
                "identifiers": {
                    "project_id": "project-a",
                    "pipeline_id": "pipeline-a",
                    "build_id": "build-a",
                },
            },
        )

    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task")
    def test_remote_failure_does_not_persist_incomplete_execution_reference(self, get_task):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        get_task.return_value = {
            "status": "failed",
            "terminal": True,
            "result": None,
            "error": {
                "code": "ANALYSIS_FAILED",
                "message": "analysis failed",
                "retryable": False,
                "details": {},
            },
            "trace": {
                "devops_project_id": "project-a",
                "pipeline_id": "pipeline-a",
                "build_id": None,
            },
        }

        SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertIsNone(execution.execution_reference)

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

    @patch("fta_web.issue.resources.oauth_client.get_access_token_by_user")
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task", return_value=3)
    @patch.object(run_source_analysis_execution, "apply_async", side_effect=RuntimeError("broker unavailable"))
    def test_dispatch_uses_rule_configurer_token_before_advancing(
        self,
        apply_async,
        advance,
        get_access_token_by_user,
    ):
        execution = self.create_execution()
        get_access_token_by_user.return_value = SimpleNamespace(access_token="persisted-access-token")

        SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        get_access_token_by_user.assert_called_once_with(execution.run_as_user)
        advance.assert_called_once_with(execution.analysis_id)
        apply_async.assert_called_once_with(args=(execution.analysis_id,), countdown=3)

    def test_persisted_rule_configurer_token_is_recovered_by_celery_trigger(self):
        execution = self.create_execution(bkfara_provision_id=None)
        persisted_tokens = {
            execution.run_as_user: SimpleNamespace(access_token="persisted-access-token"),
        }

        def recover_token(username):
            try:
                return persisted_tokens[username]
            except KeyError as error:
                raise TokenNotExist("persisted token unavailable") from error

        provisioning_scene = {
            "provision_id": "provision-new",
            "status": "provisioning",
            "terminal": False,
            "phase": "copying_flow",
            "next_poll_after_seconds": 2,
        }

        with (
            patch.object(oauth_client, "get_access_token_by_user", side_effect=recover_token) as get_token_by_user,
            patch(
                "fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene",
                return_value=provisioning_scene,
            ),
            patch.object(run_source_analysis_execution, "apply_async") as apply_async,
        ):
            SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        get_token_by_user.assert_called_once_with(execution.run_as_user)
        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_provision_id, "provision-new")
        apply_async.assert_called_once_with(args=(execution.analysis_id,), countdown=2)

        def trigger_with_celery_token(**params):
            self.assertEqual(
                TriggerSourceAnalysisResource._get_user_access_token(params["bk_username"]),
                persisted_tokens[execution.run_as_user].access_token,
            )
            return {
                "analysis_task_id": "task-from-celery",
                "status": "running",
                "terminal": False,
                "phase": "devops_running",
                "next_poll_after_seconds": 4,
            }

        with (
            patch(
                "fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status",
                return_value={
                    "provision_id": "provision-new",
                    "status": "ready",
                    "terminal": True,
                },
            ),
            patch(
                "fta_web.issue.resources.api.bk_incident.trigger_source_analysis",
                side_effect=trigger_with_celery_token,
            ),
            patch.object(oauth_client, "get_access_token_by_user", side_effect=recover_token) as celery_get_token,
            patch.object(run_source_analysis_execution, "apply_async") as celery_apply_async,
        ):
            run_source_analysis_execution.run(execution.analysis_id)

        execution.refresh_from_db()
        self.assertEqual(execution.bkfara_task_id, "task-from-celery")
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.ANALYZING)
        celery_get_token.assert_called_once_with(execution.run_as_user)
        celery_apply_async.assert_called_once_with(args=(execution.analysis_id,), countdown=4)

    @patch(
        "fta_web.issue.resources.oauth_client.get_access_token_by_user",
        side_effect=TokenException("token unavailable"),
    )
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task")
    @patch.object(run_source_analysis_execution, "apply_async")
    def test_dispatch_token_failure_is_retryable(self, apply_async, advance, _get_access_token_by_user):
        execution = self.create_execution()

        SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        advance.assert_not_called()
        apply_async.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "USER_ACCESS_TOKEN_UNAVAILABLE")
        self.assertEqual(execution.failure_message, SourceAnalysisFailureMessage.USER_ACCESS_TOKEN_UNAVAILABLE)
        self.assertTrue(execution.failure_retryable)

    @patch(
        "fta_web.issue.resources.oauth_client.get_access_token_by_user",
        side_effect=TokenNotExist("persisted token unavailable"),
    )
    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task")
    @patch.object(run_source_analysis_execution, "apply_async")
    def test_dispatch_stops_when_celery_cannot_read_persisted_token(
        self,
        apply_async,
        advance,
        _get_access_token_by_user,
    ):
        execution = self.create_execution()

        SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        advance.assert_not_called()
        apply_async.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "USER_ACCESS_TOKEN_UNAVAILABLE")
        self.assertTrue(execution.failure_retryable)

    @patch(
        "fta_web.issue.resources.oauth_client.get_access_token_by_user",
        side_effect=DatabaseError("database unavailable"),
    )
    def test_dispatch_does_not_hide_token_storage_error(self, _get_access_token_by_user):
        execution = self.create_execution()

        with self.assertRaisesMessage(DatabaseError, "database unavailable"):
            SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

    @patch.object(SourceAnalysisExecutionBaseResource, "advance_bkfara_task", return_value=None)
    @patch("fta_web.issue.resources.oauth_client.get_access_token_by_user")
    @patch.object(run_source_analysis_execution, "apply_async")
    def test_dispatch_terminal_execution_is_not_scheduled(
        self,
        apply_async,
        get_access_token_by_user,
        advance,
    ):
        execution = self.create_execution()
        get_access_token_by_user.return_value = SimpleNamespace(access_token="persisted-access-token")

        SourceAnalysisExecutionBaseResource.dispatch_execution(execution)

        advance.assert_called_once_with(execution.analysis_id)
        apply_async.assert_not_called()

    @patch(
        "fta_web.issue.resources.api.bk_incident.trigger_source_analysis",
        side_effect=TokenException("token unavailable"),
    )
    @patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_scene_status")
    def test_celery_token_failure_is_retryable(self, get_scene, _trigger):
        execution = self.create_execution()
        get_scene.return_value = self.ready_scene_state()

        poll_interval = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)

        self.assertIsNone(poll_interval)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_code, "USER_ACCESS_TOKEN_UNAVAILABLE")
        self.assertTrue(execution.failure_retryable)

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
