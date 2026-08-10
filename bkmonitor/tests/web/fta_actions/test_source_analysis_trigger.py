"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from django.db import IntegrityError
from django.test import TestCase

from bkmonitor.models import IssueSourceAnalysisExecution, IssueSourceAnalysisRule
from bkmonitor.models.issue import IssueMergeRelation
from constants.issue import SourceAnalysisStage, SourceAnalysisStatus, SourceAnalysisTriggerType
from core.errors.issue import SourceAnalysisUpstreamUnavailableError
from fta_web.issue.resources import SourceAnalysisExecutionBaseResource


class TestSourceAnalysisInitialTrigger(TestCase):
    databases = {"default", "monitor_api"}

    BK_BIZ_ID = 2
    ISSUE_ID = "1785376798a3f4b1c2"
    MEMBER_ISSUE_ID = "1785376800ffffffff"
    ALERT_ID = "1785376810000001"

    @classmethod
    def create_rule(cls, **kwargs) -> IssueSourceAnalysisRule:
        defaults = {
            "bk_biz_id": cls.BK_BIZ_ID,
            "name": "source analysis rule",
            "priority": 0,
            "is_enabled": True,
            "is_default": False,
            "conditions": [
                {
                    "field": "alert.strategy_id",
                    "value": ["100"],
                    "method": "eq",
                    "condition": "and",
                }
            ],
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "skill_ids": ["skill-b", "skill-a"],
            "knowledge_base_ids": [],
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisRule.objects.create(**defaults)

    @classmethod
    def create_execution(cls, **kwargs) -> IssueSourceAnalysisExecution:
        defaults = {
            "bk_biz_id": cls.BK_BIZ_ID,
            "issue_id": cls.ISSUE_ID,
            "alert_id": cls.ALERT_ID,
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisExecution.objects.create(**defaults)

    @staticmethod
    def alert() -> SimpleNamespace:
        return SimpleNamespace(id=TestSourceAnalysisInitialTrigger.ALERT_ID, assignee=[])

    @patch("fta_web.issue.resources.AlertQueryHandler")
    @patch("fta_web.issue.resources.IssueDocument.get_issue_or_raise")
    def test_latest_alert_query_uses_latest_ordering(self, get_issue_or_raise, handler_class):
        get_issue_or_raise.return_value = SimpleNamespace(first_alert_time=100, create_time=200)
        latest_alert = self.alert()
        handler_class.return_value.search_raw.return_value = ([latest_alert], None)

        result = SourceAnalysisExecutionBaseResource.get_latest_alert(self.BK_BIZ_ID, self.ISSUE_ID, [self.ISSUE_ID])

        self.assertIs(result, latest_alert)
        get_issue_or_raise.assert_called_once_with(self.ISSUE_ID, bk_biz_id=self.BK_BIZ_ID)
        handler_class.assert_called_once_with(
            bk_biz_ids=[self.BK_BIZ_ID],
            start_time=100,
            end_time=ANY,
            conditions=[{"key": "issue_id", "value": [self.ISSUE_ID], "method": "eq"}],
            ordering=["-create_time", "-seq_id"],
            page=1,
            page_size=1,
            allow_partial=False,
        )
        handler_class.return_value.search_raw.assert_called_once_with()
        handler_class.return_value._check_search_response_completeness.assert_called_once_with([latest_alert])

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_first_matching_rule_creates_execution_snapshot(self, get_latest_alert, get_alert_match_dimensions):
        self.create_rule(
            name="high priority mismatch",
            priority=100,
            conditions=[
                {
                    "field": "alert.strategy_id",
                    "value": ["999"],
                    "method": "eq",
                    "condition": "and",
                }
            ],
        )
        matched_rule = self.create_rule(name="matched rule", priority=10)
        self.create_rule(
            name="default rule",
            priority=-1,
            is_default=True,
            conditions=[],
        )
        get_latest_alert.return_value = self.alert()
        get_alert_match_dimensions.return_value = {"alert.strategy_id": "100"}

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertTrue(created)
        self.assertEqual(IssueSourceAnalysisExecution.objects.count(), 1)
        self.assertEqual(execution.issue_id, self.ISSUE_ID)
        self.assertEqual(execution.alert_id, self.ALERT_ID)
        self.assertEqual(execution.rule_id, matched_rule.id)
        self.assertEqual(execution.rule_name, "matched rule")
        self.assertEqual(execution.rule_priority, 10)
        self.assertEqual(execution.bkci_project_id, "project-a")
        self.assertEqual(execution.repository_alias, "repo-a")
        self.assertEqual(execution.agent_id, "agent-a")
        self.assertEqual(execution.skill_ids, ["skill-b", "skill-a"])
        self.assertEqual(execution.knowledge_base_ids, [])
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)
        self.assertEqual(execution.stage, SourceAnalysisStage.WAITING)
        self.assertEqual(execution.trigger_type, SourceAnalysisTriggerType.INITIAL)
        self.assertEqual(execution.attempt, 1)
        self.assertEqual(execution.create_user, "admin")
        self.assertEqual(execution.update_user, "admin")

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions")
    def test_rule_matching_uses_alarm_assign_previous_connector_semantics(self, get_alert_match_dimensions):
        expected_rule = self.create_rule(
            conditions=[
                {
                    "field": "alert.strategy_id",
                    "value": ["100"],
                    "method": "eq",
                    "condition": "and",
                },
                {
                    "field": "alert.name",
                    "value": ["not matched"],
                    "method": "eq",
                    "condition": "or",
                },
            ]
        )
        get_alert_match_dimensions.return_value = {
            "alert.strategy_id": "100",
            "alert.name": "cpu high load",
        }

        matched_rule = SourceAnalysisExecutionBaseResource.get_matched_rule(self.BK_BIZ_ID, self.alert())

        self.assertEqual(matched_rule.id, expected_rule.id)

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions")
    def test_rule_matching_preserves_alarm_assign_and_or_grouping(self, get_alert_match_dimensions):
        expected_rule = self.create_rule(
            conditions=[
                {"field": "alert.strategy_id", "value": ["100"], "method": "eq", "condition": "and"},
                {"field": "alert.name", "value": ["not matched"], "method": "eq", "condition": "or"},
                {"field": "alert.scenario", "value": ["not matched"], "method": "eq", "condition": "and"},
            ]
        )
        get_alert_match_dimensions.return_value = {
            "alert.strategy_id": "100",
            "alert.name": "cpu high load",
            "alert.scenario": "os",
        }

        matched_rule = SourceAnalysisExecutionBaseResource.get_matched_rule(self.BK_BIZ_ID, self.alert())

        # 告警分派语义为 A OR (B AND C)，而不是旧源码分析协议表达的 (A AND B) OR C。
        self.assertEqual(matched_rule.id, expected_rule.id)

    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert", return_value=None)
    def test_no_alert_does_not_create_execution(self, _get_latest_alert):
        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertIsNone(execution)
        self.assertFalse(created)
        self.assertFalse(IssueSourceAnalysisExecution.objects.exists())

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_no_enabled_rule_skips_runtime_dimension_build(self, get_latest_alert, get_alert_match_dimensions):
        get_latest_alert.return_value = self.alert()

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertIsNone(execution)
        self.assertFalse(created)
        get_alert_match_dimensions.assert_not_called()

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions")
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_no_matching_rule_does_not_create_execution(self, get_latest_alert, get_alert_match_dimensions):
        self.create_rule()
        get_latest_alert.return_value = self.alert()
        get_alert_match_dimensions.return_value = {"alert.strategy_id": "999"}

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertIsNone(execution)
        self.assertFalse(created)
        self.assertFalse(IssueSourceAnalysisExecution.objects.exists())

    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_existing_active_execution_is_reused_before_alert_query(self, get_latest_alert):
        active_execution = self.create_execution()

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertEqual(execution.id, active_execution.id)
        self.assertFalse(created)
        get_latest_alert.assert_not_called()

    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_member_active_before_merge_is_reused_by_main(self, get_latest_alert):
        active_execution = self.create_execution(issue_id=self.MEMBER_ISSUE_ID)
        IssueMergeRelation.objects.create(
            bk_biz_id=self.BK_BIZ_ID,
            main_issue_id=self.ISSUE_ID,
            member_issue_id=self.MEMBER_ISSUE_ID,
        )

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.ISSUE_ID, "admin"
        )

        self.assertEqual(execution.id, active_execution.id)
        self.assertFalse(created)
        self.assertEqual(IssueSourceAnalysisExecution.objects.count(), 1)
        get_latest_alert.assert_not_called()

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions", return_value={})
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_merged_member_uses_main_issue_active_slot(self, get_latest_alert, _get_alert_match_dimensions):
        IssueMergeRelation.objects.create(
            bk_biz_id=self.BK_BIZ_ID,
            main_issue_id=self.ISSUE_ID,
            member_issue_id=self.MEMBER_ISSUE_ID,
        )
        self.create_rule(priority=-1, is_default=True, conditions=[])
        get_latest_alert.return_value = self.alert()

        execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
            self.BK_BIZ_ID, self.MEMBER_ISSUE_ID, "admin"
        )

        self.assertTrue(created)
        self.assertEqual(execution.issue_id, self.ISSUE_ID)
        self.assertEqual(execution.active_key, self.ISSUE_ID)
        get_latest_alert.assert_called_once_with(
            self.BK_BIZ_ID,
            self.ISSUE_ID,
            [self.ISSUE_ID, self.MEMBER_ISSUE_ID],
        )

    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_merge_scope_degradation_stops_creation(self, get_latest_alert):
        merge_context = Mock(degraded=True)

        with (
            patch("fta_web.issue.resources.MergeResolverContext", return_value=merge_context),
            self.assertRaises(SourceAnalysisUpstreamUnavailableError),
        ):
            SourceAnalysisExecutionBaseResource.create_initial_execution(self.BK_BIZ_ID, self.ISSUE_ID, "admin")

        merge_context.load.assert_called_once_with()
        get_latest_alert.assert_not_called()
        self.assertFalse(IssueSourceAnalysisExecution.objects.exists())

    @patch.object(SourceAnalysisExecutionBaseResource, "get_alert_match_dimensions", return_value={})
    @patch.object(SourceAnalysisExecutionBaseResource, "get_latest_alert")
    def test_concurrent_create_returns_winning_execution(self, get_latest_alert, _get_alert_match_dimensions):
        winning_execution = self.create_execution()
        self.create_rule(priority=-1, is_default=True, conditions=[])
        get_latest_alert.return_value = self.alert()

        with (
            patch.object(
                SourceAnalysisExecutionBaseResource,
                "get_active_execution",
                side_effect=[None, winning_execution],
            ),
            patch.object(IssueSourceAnalysisExecution.objects, "create", side_effect=IntegrityError),
        ):
            execution, created = SourceAnalysisExecutionBaseResource.create_initial_execution(
                self.BK_BIZ_ID, self.ISSUE_ID, "admin"
            )

        self.assertEqual(execution.id, winning_execution.id)
        self.assertFalse(created)
