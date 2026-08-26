"""源码分析临时上游 Mock 的联调契约测试。"""

from unittest.mock import patch

from django.core.cache import caches
from django.test import SimpleTestCase, TestCase

from api.source_analysis_mock import SourceAnalysisUpstreamMock
from bkmonitor.models import IssueSourceAnalysisExecution, IssueSourceAnalysisRule
from constants.issue import (
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStage,
    SourceAnalysisStatus,
)
from core.drf_resource import api
from core.errors.issue import SourceAnalysisRepositoryInvalidError, SourceAnalysisResourceNotFoundError
from fta_web.issue.resources import (
    ListSourceAnalysisBkciProjectsResource,
    ListSourceAnalysisBkciRepositoriesResource,
    ListSourceAnalysisAgentsResource,
    ListSourceAnalysisKnowledgeBasesResource,
    ListSourceAnalysisSkillsResource,
    SaveSourceAnalysisConfigResource,
    SourceAnalysisBaseResource,
    SourceAnalysisExecutionBaseResource,
)


class SourceAnalysisMockTestMixin:
    def setUp(self):
        super().setUp()
        self.mock_enabled = patch.object(SourceAnalysisUpstreamMock, "is_enabled", return_value=True)
        self.mock_cache = patch("api.source_analysis_mock.cache", caches["locmem"])
        self.mock_enabled.start()
        self.mock_cache.start()
        self.addCleanup(self.mock_cache.stop)
        self.addCleanup(self.mock_enabled.stop)


class TestSourceAnalysisMockOptions(SourceAnalysisMockTestMixin, SimpleTestCase):
    def test_mock_resources_use_final_option_contract(self):
        projects = ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})
        repositories = ListSourceAnalysisBkciRepositoriesResource().perform_request(
            {"bk_biz_id": 2, "project_id": SourceAnalysisUpstreamMock.BKCI_PROJECT_ID}
        )
        agents = ListSourceAnalysisAgentsResource().perform_request(
            {"bk_biz_id": 2, "keyword": "", "page": 1, "page_size": 20}
        )
        skills = ListSourceAnalysisSkillsResource().perform_request(
            {"bk_biz_id": 2, "keyword": "", "page": 1, "page_size": 20}
        )
        knowledge_bases = ListSourceAnalysisKnowledgeBasesResource().perform_request(
            {"bk_biz_id": 2, "keyword": "", "page": 1, "page_size": 20}
        )

        self.assertEqual(
            projects,
            [{"id": "mock-source-analysis-project", "name": "[Mock] 源码分析联调项目"}],
        )
        self.assertEqual(
            repositories,
            [
                {
                    "id": "mock-source-analysis-repository",
                    "name": "mock-source-analysis-repository",
                    "scm_type": "GIT",
                }
            ],
        )
        self.assertEqual(agents["total"], 4)
        self.assertEqual(
            {item["id"] for item in agents["list"]},
            {
                "mock-agent-high-confidence",
                "mock-agent-insufficient-evidence",
                "mock-agent-retryable-failure",
                "mock-agent-terminal-failure",
            },
        )
        self.assertEqual(skills["total"], 2)
        self.assertEqual(knowledge_bases["total"], 2)
        option_fields = {"id", "name", "space_id", "space_name"}
        self.assertEqual(set(agents["list"][0]), option_fields)
        self.assertEqual(set(skills["list"][0]), option_fields)
        self.assertEqual(set(knowledge_bases["list"][0]), option_fields)

    def test_mock_bkci_options_do_not_call_devops_api(self):
        with (
            patch.object(api.devops, "list_user_project", side_effect=AssertionError("unexpected DevOps request")),
            patch.object(api.devops, "list_user_repository", side_effect=AssertionError("unexpected DevOps request")),
        ):
            ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})
            ListSourceAnalysisBkciRepositoriesResource().perform_request(
                {"bk_biz_id": 2, "project_id": SourceAnalysisUpstreamMock.BKCI_PROJECT_ID}
            )

    def test_mock_repository_uses_the_same_config_validation(self):
        SaveSourceAnalysisConfigResource.validate_repository(
            2,
            SourceAnalysisUpstreamMock.BKCI_PROJECT_ID,
            SourceAnalysisUpstreamMock.BKCI_REPOSITORY_ALIAS,
        )

        with self.assertRaises(SourceAnalysisRepositoryInvalidError):
            SaveSourceAnalysisConfigResource.validate_repository(
                2,
                SourceAnalysisUpstreamMock.BKCI_PROJECT_ID,
                "unknown-repository",
            )

    def test_mock_options_support_keyword_and_pagination(self):
        result = ListSourceAnalysisAgentsResource().perform_request(
            {"bk_biz_id": 2, "keyword": "失败", "page": 2, "page_size": 1}
        )

        self.assertEqual(result["total"], 2)
        self.assertEqual(
            result["list"],
            [
                {
                    "id": "mock-agent-terminal-failure",
                    "name": "[Mock] 不可重试分析失败",
                    "space_id": "mock-space-b",
                    "space_name": "[Mock] Source Analysis",
                }
            ],
        )

    def test_mock_resources_pass_the_same_enable_validation(self):
        rule = IssueSourceAnalysisRule(
            bk_biz_id=2,
            priority=1,
            agent_id="mock-agent-high-confidence",
            skill_ids=["mock-skill-code-search"],
            knowledge_base_ids=["mock-kb-service"],
        )

        SourceAnalysisBaseResource.validate_resources(rule)

    def test_unknown_mock_knowledge_base_is_rejected(self):
        rule = IssueSourceAnalysisRule(
            bk_biz_id=2,
            priority=1,
            agent_id="mock-agent-high-confidence",
            knowledge_base_ids=["unknown-kb"],
        )

        with self.assertRaises(SourceAnalysisResourceNotFoundError):
            SourceAnalysisBaseResource.validate_resources(rule)


class TestSourceAnalysisMockTiming(SourceAnalysisMockTestMixin, SimpleTestCase):
    CLIENT_REQUEST_ID = "43c3ca39-d60f-4482-854d-00f771e149fb"

    def tearDown(self):
        task_id = f"mock:high_confidence:{self.CLIENT_REQUEST_ID}"
        caches["locmem"].delete(SourceAnalysisUpstreamMock._task_cache_key(task_id))

    def test_task_stays_running_until_configured_duration(self):
        trigger_params = {
            "issue_id": "issue-1",
            "bk_biz_id": 2,
            "bk_tenant_id": "system",
            "devops_project_id": "project-a",
            "client_request_id": self.CLIENT_REQUEST_ID,
            "inputs": {
                "repository_alias": "repo-a",
                "agent_id": "mock-agent-high-confidence",
                "skill_ids": [],
                "knowledge_base_ids": [],
                "issue_context": {"alert_ids": ["alert-1"]},
            },
        }

        triggered = SourceAnalysisUpstreamMock.perform_bkfara_request(
            SourceAnalysisUpstreamMock.BKFARA_TRIGGER_ACTION,
            trigger_params,
        )
        with (
            patch.object(SourceAnalysisUpstreamMock, "duration_seconds", return_value=10),
            patch.object(caches["locmem"], "get", return_value=100.0),
            patch("api.source_analysis_mock.time.time", side_effect=[105.0, 111.0]),
        ):
            running = SourceAnalysisUpstreamMock.perform_bkfara_request(
                SourceAnalysisUpstreamMock.BKFARA_GET_TASK_ACTION,
                {"analysis_task_id": triggered["analysis_task_id"]},
            )
            succeeded = SourceAnalysisUpstreamMock.perform_bkfara_request(
                SourceAnalysisUpstreamMock.BKFARA_GET_TASK_ACTION,
                {"analysis_task_id": triggered["analysis_task_id"]},
            )

        self.assertEqual(triggered["status"], "queued")
        self.assertEqual(running["status"], "running")
        self.assertEqual(succeeded["status"], "succeeded")


class TestSourceAnalysisMockOrchestration(SourceAnalysisMockTestMixin, TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        super().setUp()
        self.mock_duration = patch.object(SourceAnalysisUpstreamMock, "duration_seconds", return_value=0)
        self.mock_duration.start()
        self.addCleanup(self.mock_duration.stop)

    @staticmethod
    def create_execution(agent_id: str, issue_id: str) -> IssueSourceAnalysisExecution:
        return IssueSourceAnalysisExecution.objects.create(
            bk_biz_id=2,
            issue_id=issue_id,
            status=SourceAnalysisStatus.PENDING,
            stage=SourceAnalysisStage.WAITING,
            alert_id=f"alert-{issue_id}",
            rule_id=10,
            rule_priority=100,
            bkci_project_id="project-a",
            repository_alias="repo-a",
            agent_id=agent_id,
            skill_ids=["mock-skill-code-search"],
            knowledge_base_ids=["mock-kb-service"],
            bkfara_provision_id=None,
            create_user="operator-a",
            update_user="operator-a",
        )

    def advance_to_terminal(self, execution: IssueSourceAnalysisExecution) -> IssueSourceAnalysisExecution:
        first_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)
        execution.refresh_from_db()
        self.assertEqual(first_poll, 2)
        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.SOURCE_PREPARING)

        second_poll = SourceAnalysisExecutionBaseResource.advance_bkfara_task(execution.analysis_id)
        self.assertIsNone(second_poll)
        execution.refresh_from_db()
        caches["locmem"].delete(SourceAnalysisUpstreamMock._task_cache_key(execution.bkfara_task_id))
        return execution

    def test_real_state_machine_persists_mock_high_confidence_success(self):
        execution = self.advance_to_terminal(
            self.create_execution("mock-agent-high-confidence", "issue-high-confidence")
        )

        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertEqual(execution.result_type, SourceAnalysisResultType.HIGH_CONFIDENCE)
        self.assertEqual(execution.result_schema_version, "1.0.0")
        self.assertIn("```diff", execution.result_payload["content"])

    def test_real_state_machine_persists_mock_insufficient_evidence_success(self):
        execution = self.advance_to_terminal(
            self.create_execution("mock-agent-insufficient-evidence", "issue-insufficient-evidence")
        )

        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertEqual(execution.result_type, SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(execution.result_payload["result_card"]["responsibility"])

    def test_real_state_machine_persists_mock_retryable_failure(self):
        execution = self.advance_to_terminal(
            self.create_execution("mock-agent-retryable-failure", "issue-retryable-failure")
        )

        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.AI_ANALYSIS)
        self.assertEqual(execution.failure_code, "MOCK_ANALYSIS_FAILED")
        self.assertTrue(execution.failure_retryable)

    def test_real_state_machine_persists_mock_terminal_failure(self):
        execution = self.advance_to_terminal(
            self.create_execution("mock-agent-terminal-failure", "issue-terminal-failure")
        )

        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertFalse(execution.failure_retryable)
