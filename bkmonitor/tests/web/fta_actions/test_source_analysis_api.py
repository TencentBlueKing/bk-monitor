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
                "is_repository_configured": False,
                "is_configured": False,
                "unavailable_reason": "no_matched_rule",
                "unavailable_reason_display": "当前 Issue 未匹配到可用的源码分析规则。",
                "next_execution_context": None,
                "latest": None,
            },
        )

    def test_query_without_execution_returns_initial_context(self):
        rule = self.create_rule()
        expected_context = {
            "trigger_type": SourceAnalysisTriggerType.INITIAL,
            "source": "matched_rule_preview",
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "knowledge_base_ids": [],
            "skill_ids": [],
        }

        with (
            patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=SimpleNamespace()),
            patch.object(SourceAnalysisExecutionBaseResource, "get_rule_availability", return_value=(rule, None)),
            patch.object(
                SourceAnalysisExecutionBaseResource,
                "build_next_execution_context",
                return_value=expected_context,
            ) as build_context,
        ):
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertEqual(result["next_execution_context"], expected_context)
        build_context.assert_called_once_with(
            rule,
            trigger_type=SourceAnalysisTriggerType.INITIAL,
            source="matched_rule_preview",
        )

    def test_build_next_execution_context_only_returns_parameter_ids(self):
        rule = SimpleNamespace(
            bkci_project_id="project-a",
            repository_alias="repo-a",
            agent_id="agent-a",
            skill_ids=["skill-a"],
            knowledge_base_ids=["knowledge-a"],
        )

        result = SourceAnalysisExecutionBaseResource.build_next_execution_context(
            rule,
            trigger_type=SourceAnalysisTriggerType.REANALYZE,
            source="matched_rule_preview",
        )

        self.assertEqual(
            result,
            {
                "trigger_type": SourceAnalysisTriggerType.REANALYZE,
                "source": "matched_rule_preview",
                "bkci_project_id": "project-a",
                "repository_alias": "repo-a",
                "agent_id": "agent-a",
                "knowledge_base_ids": ["knowledge-a"],
                "skill_ids": ["skill-a"],
            },
        )

    def test_retryable_failure_returns_failed_execution_snapshot(self):
        execution = self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            stage=None,
            failure_retryable=True,
            bkci_project_id="snapshot-project",
            repository_alias="snapshot-repo",
            agent_id="snapshot-agent",
            knowledge_base_ids=["snapshot-knowledge"],
            skill_ids=["snapshot-skill"],
        )

        with patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert") as get_latest_alert:
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertEqual(
            result["next_execution_context"],
            {
                "trigger_type": SourceAnalysisTriggerType.RETRY,
                "source": "execution_snapshot",
                "bkci_project_id": execution.bkci_project_id,
                "repository_alias": execution.repository_alias,
                "agent_id": execution.agent_id,
                "knowledge_base_ids": execution.knowledge_base_ids,
                "skill_ids": execution.skill_ids,
            },
        )
        get_latest_alert.assert_not_called()

    def test_success_returns_current_matched_rule_for_reanalysis(self):
        self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            bkci_project_id="old-project",
            repository_alias="old-repo",
            agent_id="old-agent",
            knowledge_base_ids=["old-knowledge"],
            skill_ids=["old-skill"],
        )
        rule = self.create_rule(
            bkci_project_id="current-project",
            repository_alias="current-repo",
            agent_id="current-agent",
            knowledge_base_ids=["current-knowledge"],
            skill_ids=["current-skill"],
        )
        alert = SimpleNamespace()

        with (
            patch.object(
                SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=alert
            ) as get_latest_alert,
            patch.object(
                SourceAnalysisExecutionBaseResource, "get_matched_rule", return_value=rule
            ) as get_matched_rule,
        ):
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertEqual(
            result["next_execution_context"],
            {
                "trigger_type": SourceAnalysisTriggerType.REANALYZE,
                "source": "matched_rule_preview",
                "bkci_project_id": "current-project",
                "repository_alias": "current-repo",
                "agent_id": "current-agent",
                "knowledge_base_ids": ["current-knowledge"],
                "skill_ids": ["current-skill"],
            },
        )
        get_latest_alert.assert_called_once()
        get_matched_rule.assert_called_once_with(self.BK_BIZ_ID, alert)

    def test_active_execution_does_not_return_next_execution_context(self):
        self.create_execution(status=SourceAnalysisStatus.RUNNING)

        with patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert") as get_latest_alert:
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertIsNone(result["next_execution_context"])
        get_latest_alert.assert_not_called()

    def test_non_retryable_failure_does_not_return_next_execution_context(self):
        self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            stage=None,
            failure_retryable=False,
        )

        with patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert") as get_latest_alert:
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertIsNone(result["next_execution_context"])
        get_latest_alert.assert_not_called()

    @patch.object(SourceAnalysisExecutionBaseResource, "get_rule_availability", return_value=(None, "no_matched_rule"))
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=None)
    def test_query_returns_repository_configuration_independently_from_rule(self, _get_alert, _get_availability):
        IssueSourceAnalysisConfig.objects.create(
            bk_biz_id=self.BK_BIZ_ID,
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertTrue(result["is_repository_configured"])
        self.assertFalse(result["is_configured"])

    def test_success_view_returns_result_card_and_markdown_content(self):
        payload = {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            "result_card": {
                "description": "现有证据无法确认唯一责任提交。",
                "responsibility": None,
            },
            "content_type": "text/markdown",
            "content": "# 分析报告\n\n缺少告警时刻的运行 Commit 映射。",
            "internal_debug": {"analysis_id": "internal"},
        }
        execution = self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            result_schema_version="1.0.0",
            result_payload=payload,
        )

        with (
            patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=None),
            patch.object(SourceAnalysisExecutionBaseResource, "build_next_execution_context") as build_context,
        ):
            result = SourceAnalysisResource().perform_request({"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID})

        self.assertTrue(result["is_configured"])
        self.assertFalse(result["is_repository_configured"])
        self.assertIsNone(result["next_execution_context"])
        build_context.assert_not_called()
        self.assertEqual(result["latest"]["analysis_id"], execution.analysis_id)
        self.assertEqual(result["latest"]["status_display"], "分析完成（证据不足）")
        self.assertEqual(
            result["latest"]["result"],
            {
                "schema_version": "1.0.0",
                "result_type": SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
                "result_card": {
                    "description": "现有证据无法确认唯一责任提交。",
                    "responsibility": None,
                },
                "content_type": "text/markdown",
                "content": "# 分析报告\n\n缺少告警时刻的运行 Commit 映射。",
            },
        )

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
        self.assertNotIn("next_execution_context", result["source_analysis"])

    def test_overview_does_not_build_next_execution_context_for_matched_rule(self):
        rule = self.create_rule()
        with (
            patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=SimpleNamespace()),
            patch.object(SourceAnalysisExecutionBaseResource, "get_rule_availability", return_value=(rule, None)),
            patch.object(SourceAnalysisExecutionBaseResource, "build_next_execution_context") as build_context,
        ):
            result = AIAnalysisOverviewResource().perform_request(
                {"bk_biz_id": self.BK_BIZ_ID, "issue_id": self.ISSUE_ID}
            )

        self.assertTrue(result["source_analysis"]["is_configured"])
        self.assertNotIn("next_execution_context", result["source_analysis"])
        build_context.assert_not_called()

    def test_overview_crops_full_source_analysis_result(self):
        payload = {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE,
            "result_card": {
                "description": "空值校验被删除导致登录接口出现空指针。",
                "responsibility": {
                    "commit_id": "a3fa531",
                    "commit_message": "remove null check",
                    "author_name": "Edwin Wu",
                    "bk_username": "edwinwu",
                    "internal_score": 0.98,
                },
                "internal_trace": "not-for-frontend",
            },
            "content_type": "text/markdown",
            "content": "# 分析报告\n\n```diff\n- value.getName()\n+ value == null ? null : value.getName()\n```",
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
            latest["result"],
            {
                "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE,
                "result_card": {
                    "description": "空值校验被删除导致登录接口出现空指针。",
                    "responsibility": {
                        "commit_id": "a3fa531",
                        "commit_message": "remove null check",
                        "author_name": "Edwin Wu",
                        "bk_username": "edwinwu",
                    },
                },
            },
        )

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
        )
        for method in expected_methods:
            with self.subTest(method=method):
                self.assertIn(f"export const {method} = request(", source)
                self.assertIn(f"  {method},", source)
        self.assertNotIn("sourceAnalysisRaw", source)

    def test_urls_expose_finalized_methods(self):
        expected = {
            "/fta/issue/issue/ai_analysis_overview/": {"get": "issue/ai_analysis_overview"},
            "/fta/issue/issue/source_analysis/": {"get": "issue/source_analysis"},
            "/fta/issue/issue/start_source_analysis/": {"post": "issue/start_source_analysis"},
            "/fta/issue/issue/retry_source_analysis/": {"post": "issue/retry_source_analysis"},
            "/fta/issue/issue/reanalyze_source_analysis/": {"post": "issue/reanalyze_source_analysis"},
        }

        for path, actions in expected.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).func.actions, actions)

    def test_viewset_uses_issue_read_and_write_permissions(self):
        for action in ("issue/ai_analysis_overview", "issue/source_analysis"):
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
