"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import resolve

from bkmonitor.iam import ActionEnum
from bkmonitor.models import IssueSourceAnalysisConfig, IssueSourceAnalysisExecution, IssueSourceAnalysisRule
from bkmonitor.utils.user import set_local_username
from constants.issue import (
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStatus,
    SourceAnalysisTriggerType,
)
from core.errors.issue import SourceAnalysisOperationConflictError
from fta_web.issue.resources import (
    AIAnalysisOverviewResource,
    ReanalyzeSourceAnalysisResource,
    RetrySourceAnalysisResource,
    SourceAnalysisExecutionBaseResource,
    SourceAnalysisRawResource,
    SourceAnalysisResource,
    StartSourceAnalysisResource,
)
from fta_web.issue.views import IssueViewSet


class TestSourceAnalysisFrontendResources(TestCase):
    databases = {"default", "monitor_api"}

    BK_BIZ_ID = 2
    ISSUE_ID = "1785376798a3f4b1c2"
    ALERT_ID = "1785376810000001"

    def setUp(self):
        set_local_username("alice")

    def tearDown(self):
        set_local_username(None)

    @classmethod
    def create_execution(cls, **kwargs) -> IssueSourceAnalysisExecution:
        defaults = {
            "bk_biz_id": cls.BK_BIZ_ID,
            "issue_id": cls.ISSUE_ID,
            "alert_id": cls.ALERT_ID,
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "skill_ids": ["skill-a"],
            "knowledge_base_ids": [],
            "create_user": "alice",
            "update_user": "alice",
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisExecution.objects.create(**defaults)

    @classmethod
    def create_rule(cls, **kwargs) -> IssueSourceAnalysisRule:
        defaults = {
            "bk_biz_id": cls.BK_BIZ_ID,
            "priority": 1,
            "is_enabled": True,
            "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisRule.objects.create(**defaults)

    @patch.object(SourceAnalysisExecutionBaseResource, "get_rule_availability", return_value=(None, "no_matched_rule"))
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=None)
    def test_query_without_execution_returns_unavailable_shape(self, _get_alert, _get_availability):
        result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertEqual(
            result,
            {
                "is_configured": False,
                "unavailable_reason": "no_matched_rule",
                "unavailable_reason_display": "当前 Issue 未匹配到可用的源码分析规则。",
                "latest": None,
            },
        )

    def test_success_view_projects_page_fields_and_hides_execution_context(self):
        payload = {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            "analysis_summary": {"conclusion": "证据不足"},
            "responsibility": None,
            "repair_suggestion": None,
            "evidence_chain": [],
            "next_actions": [{"title": "补充证据", "description": "查询运行 Commit"}],
            "source_build": {"project_id": "project-a"},
            "code_association": {"repository_alias": "repo-a"},
            "execution_context": {"analysis_id": "internal"},
        }
        execution = self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            result_schema_version="1.0.0",
            result_payload=payload,
        )

        result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertTrue(result["is_configured"])
        self.assertEqual(result["latest"]["analysis_id"], execution.analysis_id)
        self.assertEqual(result["latest"]["status_display"], "分析完成（证据不足）")
        self.assertNotIn("execution_context", result["latest"]["result"])
        self.assertEqual(result["latest"]["result"]["result_type"], SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)

    @patch.object(SourceAnalysisExecutionBaseResource, "get_rule_availability", return_value=(None, "no_matched_rule"))
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=None)
    def test_overview_only_exposes_source_analysis_module(self, _get_alert, _get_availability):
        IssueSourceAnalysisConfig.objects.create(
            bk_biz_id=self.BK_BIZ_ID,
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        result = AIAnalysisOverviewResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertEqual(set(result), {"source_analysis"})
        self.assertTrue(result["source_analysis"]["is_repository_configured"])

    def test_overview_crops_full_source_analysis_result(self):
        payload = {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE,
            "analysis_summary": {
                "conclusion": "定位到责任提交",
                "root_cause": "空值校验被删除",
                "impact_scope": "登录接口",
                "insufficient_evidence_reason": None,
            },
            "responsibility": {
                "commit_id": "a3fa531",
                "commit_message": "remove null check",
                "author_name": "Edwin Wu",
                "bk_username": "edwinwu",
                "committed_at": "2026-07-28T09:32:15+08:00",
                "reason": "异常行与 Git blame 一致",
            },
            "repair_suggestion": {
                "problem_description": "缺少空值校验",
                "fix_strategy": "恢复空值校验",
                "changes": [{"suggested_code": "if value is None: return"}],
                "validation_suggestions": ["补充单测"],
            },
            "evidence_chain": [
                {
                    "title": "异常命中空值解引用",
                    "summary": "堆栈定位到 LoginHandler.java:126",
                    "excerpt": "NullPointerException",
                },
                {"title": "第二条证据", "summary": "快览不返回"},
            ],
            "next_actions": [{"title": "第一步", "description": "快览只保留第一条"}],
            "source_build": {"project_id": "project-a", "pipeline_id": "pipeline-a"},
            "code_association": {"repository_alias": "repo-a"},
            "execution_context": {"analysis_id": "internal"},
        }
        self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_schema_version="1.0.0",
            result_payload=payload,
        )

        result = AIAnalysisOverviewResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        latest = result["source_analysis"]["latest"]
        self.assertEqual(
            set(latest),
            {
                "analysis_id",
                "status",
                "status_display",
                "stage",
                "stage_display",
                "updated_at",
                "failure",
                "result",
            },
        )
        self.assertEqual(
            latest["result"]["analysis_summary"], {"conclusion": "定位到责任提交", "insufficient_evidence_reason": None}
        )
        self.assertEqual(latest["result"]["repair_suggestion"], {"fix_strategy": "恢复空值校验"})
        self.assertEqual(
            latest["result"]["evidence_chain"],
            [{"title": "异常命中空值解引用", "summary": "堆栈定位到 LoginHandler.java:126"}],
        )
        self.assertNotIn("source_build", latest["result"])
        self.assertNotIn("code_association", latest["result"])

    def test_raw_result_returns_validated_payload(self):
        payload = {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE,
            "execution_context": {"analysis_id": "internal"},
        }
        execution = self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_schema_version="1.0.0",
            result_payload=payload,
        )

        result = SourceAnalysisRawResource().perform_request(
            {
                "bk_biz_id": self.BK_BIZ_ID,
                "issue_id": self.ISSUE_ID,
                "analysis_id": execution.analysis_id,
            }
        )

        self.assertEqual(result, payload)

    def test_raw_result_rejects_non_success_execution(self):
        execution = self.create_execution()

        with self.assertRaises(SourceAnalysisOperationConflictError) as context:
            SourceAnalysisRawResource().perform_request(
                {
                    "bk_biz_id": self.BK_BIZ_ID,
                    "issue_id": self.ISSUE_ID,
                    "analysis_id": execution.analysis_id,
                }
            )

        self.assertEqual(context.exception.data, {"reason": "source_analysis_result_not_ready"})

    @patch.object(SourceAnalysisExecutionBaseResource, "dispatch_execution")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions", return_value={})
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_start_creates_and_dispatches_initial_execution(self, get_latest_alert, _get_dimensions, dispatch):
        self.create_rule(priority=-1, is_default=True, conditions=[])
        get_latest_alert.return_value = SimpleNamespace(id=self.ALERT_ID, assignee=[])

        result = StartSourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        execution = IssueSourceAnalysisExecution.objects.get()
        self.assertEqual(execution.trigger_type, SourceAnalysisTriggerType.INITIAL)
        self.assertEqual(result["latest"]["analysis_id"], execution.analysis_id)
        dispatch.assert_called_once_with(execution)

    @patch.object(SourceAnalysisExecutionBaseResource, "dispatch_execution")
    def test_retry_copies_failed_snapshot_and_increments_attempt(self, dispatch):
        failed = self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            stage=None,
            trigger_type=SourceAnalysisTriggerType.INITIAL,
            attempt=1,
            failure_stage=SourceAnalysisFailureStage.AI_ANALYSIS,
            failure_code="AI_FAILED",
            failure_message="分析失败",
            failure_retryable=True,
        )

        result = RetrySourceAnalysisResource().perform_request(
            {
                "bk_biz_id": self.BK_BIZ_ID,
                "issue_id": self.ISSUE_ID,
                "analysis_id": failed.analysis_id,
            }
        )

        retry = IssueSourceAnalysisExecution.objects.order_by("-id").first()
        self.assertEqual(retry.trigger_type, SourceAnalysisTriggerType.RETRY)
        self.assertEqual(retry.retry_of_analysis_id, failed.analysis_id)
        self.assertEqual(retry.attempt, 2)
        self.assertEqual(retry.alert_id, failed.alert_id)
        self.assertEqual(result["latest"]["analysis_id"], retry.analysis_id)
        dispatch.assert_called_once_with(retry)

    def test_retry_rejects_non_retryable_failure(self):
        failed = self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            stage=None,
            failure_retryable=False,
        )

        with self.assertRaises(SourceAnalysisOperationConflictError) as context:
            RetrySourceAnalysisResource().perform_request(
                {
                    "bk_biz_id": self.BK_BIZ_ID,
                    "issue_id": self.ISSUE_ID,
                    "analysis_id": failed.analysis_id,
                }
            )

        self.assertEqual(context.exception.data, {"reason": "source_analysis_not_retryable"})

    def test_retry_rejects_old_target_after_later_execution(self):
        failed = self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            stage=None,
            failure_retryable=True,
        )
        self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            retry_of_analysis_id=failed.analysis_id,
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_schema_version="1.0.0",
            result_payload={"schema_version": "1.0.0", "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE},
        )
        self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_schema_version="1.0.0",
            result_payload={"schema_version": "1.0.0", "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE},
        )

        with self.assertRaises(SourceAnalysisOperationConflictError) as context:
            RetrySourceAnalysisResource().perform_request(
                {
                    "bk_biz_id": self.BK_BIZ_ID,
                    "issue_id": self.ISSUE_ID,
                    "analysis_id": failed.analysis_id,
                }
            )

        self.assertEqual(context.exception.data, {"reason": "source_analysis_target_not_failed"})

    @patch.object(SourceAnalysisExecutionBaseResource, "dispatch_execution")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_matched_rule")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_reanalyze_uses_current_alert_and_rule(self, get_latest_alert, get_matched_rule, dispatch):
        self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_schema_version="1.0.0",
            result_payload={"schema_version": "1.0.0", "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE},
        )
        rule = self.create_rule(priority=10)
        get_latest_alert.return_value = SimpleNamespace(id="latest-alert", assignee=[])
        get_matched_rule.return_value = rule

        result = ReanalyzeSourceAnalysisResource().perform_request(
            {"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID}
        )

        execution = IssueSourceAnalysisExecution.objects.order_by("-id").first()
        self.assertEqual(execution.trigger_type, SourceAnalysisTriggerType.REANALYZE)
        self.assertEqual(execution.alert_id, "latest-alert")
        self.assertEqual(execution.rule_id, rule.id)
        self.assertEqual(result["latest"]["analysis_id"], execution.analysis_id)
        dispatch.assert_called_once_with(execution)

    @patch("fta_web.issue.resources.AssignRuleMatch")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions", return_value={})
    def test_availability_distinguishes_disabled_matching_rule(self, _get_dimensions, rule_match):
        self.create_rule(is_enabled=False)
        rule_match.return_value.is_matched.return_value = True

        rule, reason = SourceAnalysisExecutionBaseResource.get_rule_availability(
            self.BK_BIZ_ID,
            SimpleNamespace(),
        )

        self.assertIsNone(rule)
        self.assertEqual(reason, "rule_disabled")


class TestSourceAnalysisFrontendRoutes(TestCase):
    def test_js_api_generation_is_registered_and_exports_source_analysis_methods(self):
        self.assertEqual(settings.ACTIVE_VIEWS["fta_web"]["issue"], "fta_web.issue.views")

        source = Path(settings.PROJECT_ROOT, "webpack/src/monitor-api/modules/issue.js").read_text(encoding="utf-8")
        expected_methods = (
            "aiAnalysisOverview",
            "sourceAnalysis",
            "startSourceAnalysis",
            "retrySourceAnalysis",
            "reanalyzeSourceAnalysis",
            "sourceAnalysisRaw",
        )
        for method in expected_methods:
            with self.subTest(method=method):
                self.assertIn(f"export const {method} = request(", source)
                self.assertIn(f"  {method},", source)

    def test_urls_expose_finalized_methods(self):
        expected = {
            "/fta/issue/issue/ai_analysis_overview/": {"get": "issue/ai_analysis_overview"},
            "/fta/issue/issue/source_analysis/": {"get": "issue/source_analysis"},
            "/fta/issue/issue/start_source_analysis/": {"post": "issue/start_source_analysis"},
            "/fta/issue/issue/retry_source_analysis/": {"post": "issue/retry_source_analysis"},
            "/fta/issue/issue/reanalyze_source_analysis/": {"post": "issue/reanalyze_source_analysis"},
            "/fta/issue/issue/source_analysis_raw/": {"get": "issue/source_analysis_raw"},
        }

        for path, actions in expected.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).func.actions, actions)

    def test_viewset_uses_issue_read_and_write_permissions(self):
        for action in ("issue/ai_analysis_overview", "issue/source_analysis", "issue/source_analysis_raw"):
            view = IssueViewSet()
            view.action = action
            self.assertEqual(view.get_permissions()[0].actions, [ActionEnum.VIEW_EVENT])

        for action in (
            "issue/start_source_analysis",
            "issue/retry_source_analysis",
            "issue/reanalyze_source_analysis",
        ):
            view = IssueViewSet()
            view.action = action
            self.assertEqual(view.get_permissions()[0].actions, [ActionEnum.MANAGE_EVENT])
