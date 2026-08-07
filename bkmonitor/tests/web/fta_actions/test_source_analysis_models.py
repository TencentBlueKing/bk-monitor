"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from bkmonitor.models import (
    IssueSourceAnalysisConfig,
    IssueSourceAnalysisExecution,
    IssueSourceAnalysisRule,
    generate_analysis_id,
)
from constants.issue import (
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStage,
    SourceAnalysisStatus,
    SourceAnalysisTriggerType,
)
from core.errors.issue import SourceAnalysisInvalidStatusTransitionError


class TestIssueSourceAnalysisConfig(TestCase):
    databases = {"default", "monitor_api"}

    def test_business_has_only_one_config(self):
        IssueSourceAnalysisConfig.objects.create(
            bk_biz_id=2,
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            IssueSourceAnalysisConfig.objects.create(
                bk_biz_id=2,
                bkci_project_id="project-b",
                repository_alias="repo-b",
            )

    def test_different_businesses_can_reuse_repository_alias(self):
        for bk_biz_id in (2, 3):
            IssueSourceAnalysisConfig.objects.create(
                bk_biz_id=bk_biz_id,
                bkci_project_id="shared-project",
                repository_alias="shared-repo",
            )

        self.assertEqual(IssueSourceAnalysisConfig.objects.count(), 2)

    def test_repository_snapshot_field_lengths_match_bkci(self):
        self.assertEqual(IssueSourceAnalysisConfig._meta.get_field("bkci_project_id").max_length, 128)
        self.assertEqual(IssueSourceAnalysisRule._meta.get_field("bkci_project_id").max_length, 128)
        self.assertEqual(IssueSourceAnalysisConfig._meta.get_field("repository_alias").max_length, 255)
        self.assertEqual(IssueSourceAnalysisRule._meta.get_field("repository_alias").max_length, 255)


class TestIssueSourceAnalysisRule(TestCase):
    databases = {"default", "monitor_api"}

    @staticmethod
    def create_rule(**kwargs):
        defaults = {
            "bk_biz_id": 2,
            "name": "custom rule",
            "priority": 0,
            "is_enabled": False,
            "is_default": False,
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisRule.objects.create(**defaults)

    def test_priority_is_unique_within_business(self):
        self.create_rule(priority=10)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(name="duplicate priority", priority=10)

    def test_different_businesses_can_reuse_priority(self):
        self.create_rule(bk_biz_id=2, priority=10)
        self.create_rule(bk_biz_id=3, priority=10)

        self.assertEqual(IssueSourceAnalysisRule.objects.count(), 2)

    def test_default_rule_requires_priority_minus_one(self):
        rule = self.create_rule(name="default rule", priority=-1, is_default=True)

        self.assertTrue(rule.is_default)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(name="invalid default rule", priority=0, is_default=True)

    def test_custom_rule_priority_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(priority=-1, is_default=False)

    def test_disabled_rule_allows_incomplete_configuration(self):
        rule = self.create_rule()

        self.assertFalse(rule.is_enabled)
        self.assertEqual(rule.conditions, [])
        self.assertIsNone(rule.bkci_project_id)
        self.assertIsNone(rule.repository_alias)
        self.assertEqual(rule.agent_ids, [])
        self.assertEqual(rule.skill_ids, [])
        self.assertEqual(rule.knowledge_base_ids, [])

    def test_json_field_defaults_are_not_shared(self):
        first = IssueSourceAnalysisRule(bk_biz_id=2, name="first", priority=1)
        second = IssueSourceAnalysisRule(bk_biz_id=2, name="second", priority=2)

        first.agent_ids.append("agent-a")

        self.assertEqual(second.agent_ids, [])

    def test_default_ordering_is_priority_descending(self):
        self.create_rule(name="default", priority=-1, is_default=True)
        self.create_rule(name="low", priority=0)
        self.create_rule(name="high", priority=100)

        priorities = list(IssueSourceAnalysisRule.objects.values_list("priority", flat=True))

        self.assertEqual(priorities, [100, 0, -1])


class TestIssueSourceAnalysisExecution(TestCase):
    databases = {"default", "monitor_api"}

    ISSUE_ID = "1785376798a3f4b1c2"

    @classmethod
    def create_execution(cls, **kwargs):
        defaults = {
            "bk_biz_id": 2,
            "issue_id": cls.ISSUE_ID,
            "active_key": cls.ISSUE_ID,
            "alert_id": "alert-1748392000001",
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisExecution.objects.create(**defaults)

    def test_analysis_id_reuses_issue_document_format(self):
        analysis_id = generate_analysis_id()

        self.assertEqual(len(analysis_id), 18)
        # 前 10 位是秒级时间戳，可直接还原发起时间
        self.assertGreater(int(analysis_id[:10]), 0)
        self.assertNotEqual(analysis_id, generate_analysis_id())

    def test_analysis_id_is_generated_by_default(self):
        execution = self.create_execution()

        self.assertTrue(execution.analysis_id)
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)
        self.assertEqual(execution.trigger_type, SourceAnalysisTriggerType.INITIAL)
        self.assertEqual(execution.attempt, 1)
        self.assertIsNone(execution.retry_of_analysis_id)

    def test_issue_allows_only_one_active_execution(self):
        self.create_execution()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_execution()

    def test_terminal_execution_releases_active_slot(self):
        first = self.create_execution()
        first.mark_running(SourceAnalysisStage.ANALYZING)
        first.mark_failed(
            failure_stage=SourceAnalysisFailureStage.RESULT_VALIDATE,
            failure_code="RESULT_SCHEMA_INVALID",
            failure_message="分析结果格式校验失败",
            failure_retryable=True,
        )

        second = self.create_execution(trigger_type=SourceAnalysisTriggerType.RETRY, attempt=2)

        self.assertIsNone(first.active_key)
        self.assertEqual(second.active_key, self.ISSUE_ID)

    def test_different_issues_can_run_concurrently(self):
        self.create_execution()
        self.create_execution(issue_id="1785376900ffffffff", active_key="1785376900ffffffff")

        self.assertEqual(IssueSourceAnalysisExecution.objects.count(), 2)

    def test_mark_running_records_started_at_once(self):
        execution = self.create_execution()

        execution.mark_running(SourceAnalysisStage.SOURCE_PREPARING)
        started_at = execution.started_at

        # running -> running 只推进阶段，不覆盖首次开始时间
        execution.mark_running(SourceAnalysisStage.ANALYZING)

        self.assertEqual(execution.status, SourceAnalysisStatus.RUNNING)
        self.assertEqual(execution.stage, SourceAnalysisStage.ANALYZING)
        self.assertEqual(execution.started_at, started_at)

    def test_mark_success_clears_stage_and_active_key(self):
        execution = self.create_execution()
        execution.mark_running(SourceAnalysisStage.VALIDATING)

        execution.mark_success(
            result_type=SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            result_payload={"schema_version": "1.0.0"},
            result_schema_version="1.0.0",
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertIsNone(execution.stage)
        self.assertIsNone(execution.active_key)
        self.assertIsNotNone(execution.finished_at)
        self.assertEqual(execution.result_payload, {"schema_version": "1.0.0"})

    def test_mark_failed_records_failure_detail(self):
        execution = self.create_execution()

        execution.mark_failed(
            failure_stage=SourceAnalysisFailureStage.TASK_CREATE,
            failure_code="RESULT_NOT_JSON",
            failure_message="分析结果不是合法 JSON",
            failure_retryable=False,
            failure_request_id="req-source-analysis-20260730-041",
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        self.assertEqual(execution.failure_stage, SourceAnalysisFailureStage.TASK_CREATE)
        self.assertFalse(execution.failure_retryable)
        self.assertIsNone(execution.active_key)

    def test_terminal_execution_rejects_further_transition(self):
        execution = self.create_execution()
        execution.mark_running(SourceAnalysisStage.ANALYZING)
        execution.mark_success(
            result_type=SourceAnalysisResultType.HIGH_CONFIDENCE,
            result_payload={},
            result_schema_version="1.0.0",
        )

        with self.assertRaises(SourceAnalysisInvalidStatusTransitionError):
            execution.mark_running(SourceAnalysisStage.ANALYZING)

    def test_concurrent_transition_loses_race(self):
        execution = self.create_execution()
        stale = IssueSourceAnalysisExecution.objects.get(pk=execution.pk)

        execution.mark_failed(
            failure_stage=SourceAnalysisFailureStage.TASK_EXECUTE,
            failure_code="CODE_CHECKOUT_FAILED",
            failure_message="代码检出失败",
            failure_retryable=True,
        )

        # 另一个持有旧状态的调用方不能再改写已进入终态的记录
        with self.assertRaises(SourceAnalysisInvalidStatusTransitionError):
            stale.mark_running(SourceAnalysisStage.ANALYZING)

    def test_latest_execution_comes_first(self):
        first = self.create_execution()
        first.mark_failed(
            failure_stage=SourceAnalysisFailureStage.AI_ANALYSIS,
            failure_code="RESULT_SCHEMA_INVALID",
            failure_message="分析结果格式校验失败",
            failure_retryable=True,
        )
        second = self.create_execution(
            trigger_type=SourceAnalysisTriggerType.RETRY,
            attempt=2,
            retry_of_analysis_id=first.analysis_id,
        )

        latest = IssueSourceAnalysisExecution.objects.filter(bk_biz_id=2, issue_id=self.ISSUE_ID).first()

        self.assertEqual(latest.pk, second.pk)
        self.assertEqual(latest.retry_of_analysis_id, first.analysis_id)

    def test_json_snapshot_defaults_are_not_shared(self):
        first = IssueSourceAnalysisExecution(bk_biz_id=2, issue_id=self.ISSUE_ID)
        second = IssueSourceAnalysisExecution(bk_biz_id=2, issue_id=self.ISSUE_ID)

        first.agent_ids.append("agent-a")

        self.assertEqual(second.agent_ids, [])
