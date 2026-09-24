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
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve
from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import IssueSourceAnalysisConfig, IssueSourceAnalysisRule
from bkmonitor.utils.user import set_local_username
from core.drf_resource import api
from core.drf_resource.exceptions import custom_exception_handler
from core.errors.issue import (
    IssueAIAnalysisNotEnabledError,
    IssueError,
    SourceAnalysisConfigNotFoundError,
    SourceAnalysisDefaultRuleCannotDeleteError,
    SourceAnalysisDefaultRuleConditionsInvalidError,
    SourceAnalysisDefaultRulePriorityImmutableError,
    SourceAnalysisExecutionCredentialUnavailableError,
    SourceAnalysisRepositoryInvalidError,
    SourceAnalysisResourceNotFoundError,
    SourceAnalysisRuleIncompleteError,
    SourceAnalysisRulePriorityConflictError,
    SourceAnalysisUpstreamUnavailableError,
)
from fta_web.issue.resources import (
    AIAnalysisOverviewResource,
    CreateSourceAnalysisRuleResource,
    DeleteSourceAnalysisRuleResource,
    GetSourceAnalysisConfigResource,
    ListSourceAnalysisBkciRepositoriesResource,
    ListSourceAnalysisRulesResource,
    SaveSourceAnalysisConfigResource,
    SourceAnalysisBaseResource,
    SourceAnalysisRulePatchSerializer,
    SourceAnalysisRuleWriteSerializer,
    UpdateSourceAnalysisRuleResource,
)
from fta_web.issue.source_analysis import is_issue_ai_analysis_enabled_for_biz
from fta_web.issue.views import SourceAnalysisConfigViewSet, SourceAnalysisRulesViewSet


def validate(serializer_class, data):
    serializer = serializer_class(data=data)
    assert serializer.is_valid(), serializer.errors
    return dict(serializer.validated_data)


class TestSourceAnalysisRuleSerializers(SimpleTestCase):
    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=[])
    def test_issue_ai_analysis_empty_white_list_disables_all_biz(self):
        self.assertFalse(is_issue_ai_analysis_enabled_for_biz(2))

    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=[-1])
    def test_issue_ai_analysis_minus_one_enables_all_biz(self):
        self.assertTrue(is_issue_ai_analysis_enabled_for_biz(2))

    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=["2"])
    def test_issue_ai_analysis_normalizes_and_matches_biz_id(self):
        self.assertTrue(is_issue_ai_analysis_enabled_for_biz(2))
        self.assertFalse(is_issue_ai_analysis_enabled_for_biz(3))

    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=["invalid"])
    def test_issue_ai_analysis_invalid_white_list_fails_closed(self):
        self.assertFalse(is_issue_ai_analysis_enabled_for_biz(2))

    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=[])
    def test_source_analysis_resources_reject_biz_outside_white_list(self):
        resource_requests = (
            (ListSourceAnalysisRulesResource, {"bk_biz_id": 2}),
            (AIAnalysisOverviewResource, {"bk_biz_id": 2, "issue_id": "issue-1"}),
        )
        for resource_class, request_data in resource_requests:
            with self.subTest(resource_class=resource_class.__name__):
                with self.assertRaises(IssueAIAnalysisNotEnabledError):
                    resource_class().validate_request_data(request_data)

    @override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=[2])
    def test_source_analysis_resources_accept_biz_inside_white_list(self):
        validated_data = ListSourceAnalysisRulesResource().validate_request_data({"bk_biz_id": 2})

        self.assertEqual(validated_data["bk_biz_id"], 2)

    def test_rule_contract_does_not_expose_name(self):
        self.assertNotIn("name", SourceAnalysisRuleWriteSerializer().fields)
        self.assertNotIn("name", SourceAnalysisRulePatchSerializer().fields)

    def test_write_serializer_normalizes_resource_sets(self):
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 1,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
                "agent_id": "agent-a",
                "skill_ids": ["skill-a", "skill-a"],
            },
        )

        # agent 是单值，不参与去重排序
        self.assertEqual(data["agent_id"], "agent-a")
        self.assertEqual(data["skill_ids"], ["skill-a"])

    def test_condition_chain_requires_first_connector_to_be_and(self):
        serializer = SourceAnalysisRuleWriteSerializer(
            data={
                "bk_biz_id": 2,
                "priority": 1,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "or"}],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("conditions", serializer.errors)

    def test_condition_chain_uses_previous_connector_semantics(self):
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 1,
                "conditions": [
                    {"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"},
                    {"field": "alert.name", "value": ["cpu"], "method": "eq", "condition": "or"},
                ],
            },
        )

        self.assertEqual([condition["condition"] for condition in data["conditions"]], ["and", "or"])

    def test_aidev_validation_reads_all_pages(self):
        list_resources = Mock(
            side_effect=[
                {"count": 201, "results": [{"id": index} for index in range(200)]},
                {"count": 201, "results": [{"id": 200}]},
            ]
        )

        ids = SourceAnalysisBaseResource.list_visible_aidev_ids(list_resources, "id")

        self.assertEqual(len(ids), 201)
        self.assertEqual(list_resources.call_count, 2)
        list_resources.assert_any_call(space_id="all", page=2, page_size=200)

    @patch.object(
        SourceAnalysisBaseResource,
        "load_visible_aidev_knowledge_bases",
        return_value=([{"id": 10, "knowledgebase_code": "knowledge-a"}], {"space-a": "AIDEV Helper"}),
    )
    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"agent-a", "skill-a"})
    def test_visible_resource_codes_pass_validation(self, list_visible, load_knowledge_bases):
        rule = IssueSourceAnalysisRule(
            bk_biz_id=2,
            priority=1,
            agent_id="agent-a",
            skill_ids=["skill-a"],
            knowledge_base_ids=["knowledge-a"],
        )

        SourceAnalysisBaseResource.validate_resources(rule)

        load_knowledge_bases.assert_called_once_with()
        list_visible.assert_any_call(api.aidev.list_agents, "agent_code")
        list_visible.assert_any_call(api.aidev.list_skills, "skill_code")

    @patch.object(
        SourceAnalysisBaseResource,
        "load_visible_aidev_knowledge_bases",
        return_value=([{"id": 10, "knowledgebase_code": "knowledge-a"}], {"space-a": "AIDEV Helper"}),
    )
    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"agent-a"})
    def test_invisible_knowledge_base_is_rejected(self, _list_visible, _load_knowledge_bases):
        rule = IssueSourceAnalysisRule(
            bk_biz_id=2,
            priority=1,
            agent_id="agent-a",
            knowledge_base_ids=["knowledge-missing"],
        )

        with self.assertRaises(SourceAnalysisResourceNotFoundError):
            SourceAnalysisBaseResource.validate_resources(rule)

    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"agent-a", "agent-b"})
    def test_visible_agent_passes_validation(self, _list_visible):
        rule = IssueSourceAnalysisRule(bk_biz_id=2, priority=1, agent_id="agent-b")

        SourceAnalysisBaseResource.validate_resources(rule)

    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"agent-a", "agent-b"})
    def test_invisible_agent_is_rejected(self, _list_visible):
        rule = IssueSourceAnalysisRule(bk_biz_id=2, priority=1, agent_id="agent-missing")

        with self.assertRaises(SourceAnalysisResourceNotFoundError):
            SourceAnalysisBaseResource.validate_resources(rule)

    @patch("fta_web.issue.resources.get_request_username", return_value="alice")
    @patch("fta_web.issue.resources.get_request", return_value=object())
    @patch("fta_web.issue.resources.oauth_client.get_access_token")
    @patch("fta_web.issue.resources.oauth_client.get_access_token_by_user")
    def test_prepare_rule_run_as_user_persists_and_reads_back_token(
        self,
        get_access_token_by_user,
        get_access_token,
        get_request,
        _get_username,
    ):
        get_access_token.return_value = SimpleNamespace(access_token="web-token")
        get_access_token_by_user.return_value = SimpleNamespace(access_token="persisted-token")

        username = SourceAnalysisBaseResource.prepare_rule_run_as_user()

        self.assertEqual(username, "alice")
        get_access_token.assert_called_once_with(get_request.return_value)
        get_access_token_by_user.assert_called_once_with("alice")

    def test_source_analysis_errors_use_unique_issue_error_codes(self):
        error_classes = [
            IssueAIAnalysisNotEnabledError,
            SourceAnalysisUpstreamUnavailableError,
            SourceAnalysisConfigNotFoundError,
            SourceAnalysisRepositoryInvalidError,
            SourceAnalysisResourceNotFoundError,
            SourceAnalysisRuleIncompleteError,
            SourceAnalysisRulePriorityConflictError,
            SourceAnalysisDefaultRuleCannotDeleteError,
            SourceAnalysisDefaultRulePriorityImmutableError,
            SourceAnalysisExecutionCredentialUnavailableError,
            SourceAnalysisDefaultRuleConditionsInvalidError,
        ]

        self.assertEqual(len({error.code for error in error_classes}), len(error_classes))
        for error_class in error_classes:
            with self.subTest(error_class=error_class.__name__):
                self.assertTrue(issubclass(error_class, IssueError))
                response = custom_exception_handler(error_class(), {})
                self.assertEqual(response.data["code"], error_class.code)
                self.assertIsNone(response.data["data"])

    def test_viewsets_select_read_and_write_permissions(self):
        for viewset_class in (SourceAnalysisConfigViewSet, SourceAnalysisRulesViewSet):
            read_view = viewset_class()
            read_view.request = SimpleNamespace(method="GET")
            write_view = viewset_class()
            write_view.request = SimpleNamespace(method="PATCH")

            read_permission = read_view.get_permissions()[0]
            write_permission = write_view.get_permissions()[0]
            self.assertIsInstance(read_permission, BusinessActionPermission)
            self.assertEqual(read_permission.actions, [ActionEnum.VIEW_RULE])
            self.assertEqual(write_permission.actions, [ActionEnum.MANAGE_RULE])
            self.assertIn("GET", permissions.SAFE_METHODS)

    def test_urls_expose_finalized_http_methods(self):
        config = resolve("/fta/issue/source_analysis_config/")
        config_save = resolve("/fta/issue/source_analysis_config/save/")
        rules = resolve("/fta/issue/source_analysis_rules/")
        rule_detail = resolve("/fta/issue/source_analysis_rules/10/")

        self.assertEqual(config.func.actions, {"get": "list"})
        self.assertEqual(config_save.func.actions, {"put": "save"})
        self.assertEqual(rules.func.actions, {"get": "list", "post": "create"})
        self.assertEqual(
            rule_detail.func.actions,
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"},
        )


@override_settings(ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST=[2])
class TestSourceAnalysisConfigAndRules(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        set_local_username("alice")

    def tearDown(self):
        set_local_username(None)

    @staticmethod
    def create_config(project_id="project-a", repository_alias="repo-a"):
        return IssueSourceAnalysisConfig.objects.create(
            bk_biz_id=2,
            bkci_project_id=project_id,
            repository_alias=repository_alias,
        )

    @staticmethod
    def create_rule(**kwargs):
        defaults = {
            "bk_biz_id": 2,
            "priority": 1,
            "is_enabled": False,
            "is_default": False,
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisRule.objects.create(**defaults)

    def test_get_missing_config_returns_fixed_shape(self):
        result = GetSourceAnalysisConfigResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(
            result,
            {
                "bk_biz_id": 2,
                "bkci_project_id": None,
                "repository_alias": None,
                "updated_by": None,
                "updated_at": None,
            },
        )

    @patch("fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene")
    @patch.object(SourceAnalysisBaseResource, "validate_repository")
    def test_save_config_creates_default_without_initializing_scene(self, validate_repository, ensure_scene):
        custom_rule = self.create_rule()

        result = SaveSourceAnalysisConfigResource().perform_request(
            {"bk_biz_id": 2, "bkci_project_id": "project-a", "repository_alias": "repo-a"}
        )

        validate_repository.assert_called_once_with(2, "project-a", "repo-a")
        ensure_scene.assert_not_called()
        self.assertEqual(result["bkci_project_id"], "project-a")
        default_rule = IssueSourceAnalysisRule.objects.get(bk_biz_id=2, is_default=True)
        self.assertEqual(default_rule.priority, -1)
        self.assertFalse(default_rule.is_enabled)
        custom_rule.refresh_from_db()
        self.assertEqual((custom_rule.bkci_project_id, custom_rule.repository_alias), ("project-a", "repo-a"))

    @patch.object(ListSourceAnalysisBkciRepositoriesResource, "perform_request", return_value={"total": 0, "list": []})
    def test_save_config_rejects_repository_outside_project(self, list_repositories):
        with self.assertRaises(SourceAnalysisRepositoryInvalidError):
            SaveSourceAnalysisConfigResource().perform_request(
                {"bk_biz_id": 2, "bkci_project_id": "project-a", "repository_alias": "missing"}
            )

        # 代码库选项经标准 Resource 调用链取得，参数需通过 RequestSerializer 校验后传入
        self.assertEqual(list_repositories.call_args.args[0], {"bk_biz_id": 2, "bkci_project_id": "project-a"})
        self.assertFalse(IssueSourceAnalysisConfig.objects.exists())

    @patch("fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene")
    @patch.object(SourceAnalysisBaseResource, "validate_repository")
    def test_project_change_only_updates_local_config_and_rule_snapshots(self, _validate_repository, ensure_scene):
        self.create_config()
        self.create_rule(
            is_enabled=True,
            run_as_user="alice",
            conditions=[{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
            agent_id="1",
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        SaveSourceAnalysisConfigResource().perform_request(
            {"bk_biz_id": 2, "bkci_project_id": "project-b", "repository_alias": "repo-b"}
        )

        ensure_scene.assert_not_called()
        config = IssueSourceAnalysisConfig.objects.get(bk_biz_id=2)
        rule = IssueSourceAnalysisRule.objects.get(bk_biz_id=2, is_default=False)
        self.assertEqual((config.bkci_project_id, config.repository_alias), ("project-b", "repo-b"))
        self.assertEqual((rule.bkci_project_id, rule.repository_alias), ("project-b", "repo-b"))
        self.assertEqual(rule.run_as_user, "alice")

    def test_disabled_rule_can_be_saved_without_config(self):
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 10,
                "agent_id": "1",
            },
        )

        result = CreateSourceAnalysisRuleResource().perform_request(data)

        self.assertFalse(result["is_enabled"])
        self.assertEqual(result["agent_id"], "1")
        self.assertIsNone(result["bkci_project_id"])
        self.assertNotIn("name", result)

    def test_enabled_rule_requires_config(self):
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 10,
                "is_enabled": True,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
                "agent_id": "1",
            },
        )

        with self.assertRaises(SourceAnalysisConfigNotFoundError):
            CreateSourceAnalysisRuleResource().perform_request(data)

        self.assertFalse(IssueSourceAnalysisRule.objects.exists())

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(SourceAnalysisBaseResource, "prepare_rule_run_as_user", return_value="alice")
    def test_enabled_rule_validates_resources_and_records_run_as_user(self, prepare_run_as_user, validate_resources):
        self.create_config()
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 10,
                "is_enabled": True,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
                "agent_id": "1",
            },
        )

        result = CreateSourceAnalysisRuleResource().perform_request(data)

        validate_resources.assert_called_once()
        prepare_run_as_user.assert_called_once_with()
        self.assertTrue(result["is_enabled"])
        self.assertEqual(result["run_as_user"], "alice")
        self.assertEqual((result["bkci_project_id"], result["repository_alias"]), ("project-a", "repo-a"))

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(SourceAnalysisBaseResource, "prepare_rule_run_as_user", return_value="bob")
    def test_enabled_rule_uses_current_configurer_as_run_as_user(self, prepare_run_as_user, validate_resources):
        self.create_config()
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 10,
                "is_enabled": True,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
                "agent_id": "agent-a",
            },
        )

        result = CreateSourceAnalysisRuleResource().perform_request(data)

        validate_resources.assert_called_once()
        prepare_run_as_user.assert_called_once_with()
        self.assertTrue(result["is_enabled"])
        self.assertEqual(result["run_as_user"], "bob")

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(
        SourceAnalysisBaseResource,
        "prepare_rule_run_as_user",
        side_effect=SourceAnalysisExecutionCredentialUnavailableError(),
    )
    def test_enabled_rule_save_fails_when_configurer_token_is_unavailable(
        self, _prepare_run_as_user, _validate_resources
    ):
        self.create_config()
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {
                "bk_biz_id": 2,
                "priority": 10,
                "is_enabled": True,
                "conditions": [{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
                "agent_id": "1",
            },
        )

        with self.assertRaises(SourceAnalysisExecutionCredentialUnavailableError):
            CreateSourceAnalysisRuleResource().perform_request(data)

        self.assertFalse(IssueSourceAnalysisRule.objects.exists())

    def test_duplicate_priority_raises_specific_error(self):
        self.create_rule(priority=10)
        data = validate(
            SourceAnalysisRuleWriteSerializer,
            {"bk_biz_id": 2, "priority": 10},
        )

        with self.assertRaises(SourceAnalysisRulePriorityConflictError):
            CreateSourceAnalysisRuleResource().perform_request(data)

    def test_list_is_priority_descending_with_default_last(self):
        self.create_rule(priority=1)
        self.create_rule(priority=100)
        self.create_rule(priority=-1, is_default=True)

        rules = ListSourceAnalysisRulesResource().perform_request({"bk_biz_id": 2})

        self.assertEqual([rule["priority"] for rule in rules], [100, 1, -1])

    def test_default_priority_cannot_be_patched(self):
        default_rule = self.create_rule(priority=-1, is_default=True)
        data = validate(
            SourceAnalysisRulePatchSerializer,
            {"bk_biz_id": 2, "priority": 1},
        )
        data["rule_id"] = default_rule.id

        with self.assertRaises(SourceAnalysisDefaultRulePriorityImmutableError):
            UpdateSourceAnalysisRuleResource().perform_request(data)

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(SourceAnalysisBaseResource, "prepare_rule_run_as_user", return_value="bob")
    def test_enabled_rule_patch_refreshes_run_as_user(self, prepare_run_as_user, validate_resources):
        self.create_config()
        rule = self.create_rule(
            is_enabled=True,
            run_as_user="alice",
            conditions=[{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
            agent_id="1030",
            skill_ids=["11"],
            knowledge_base_ids=["304"],
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )
        data = validate(
            SourceAnalysisRulePatchSerializer,
            {
                "bk_biz_id": 2,
                "agent_id": "ai-log-to-code",
                "skill_ids": ["bk-data-fetcher"],
                "knowledge_base_ids": ["bkmonitor_terms_base"],
            },
        )
        data["rule_id"] = rule.id

        result = UpdateSourceAnalysisRuleResource().perform_request(data)

        validate_resources.assert_called_once()
        prepare_run_as_user.assert_called_once_with()
        self.assertEqual(result["agent_id"], "ai-log-to-code")
        self.assertEqual(result["skill_ids"], ["bk-data-fetcher"])
        self.assertEqual(result["knowledge_base_ids"], ["bkmonitor_terms_base"])
        self.assertEqual(result["run_as_user"], "bob")

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(SourceAnalysisBaseResource, "prepare_rule_run_as_user", return_value="alice")
    def test_enabled_rule_patch_does_not_initialize_scene(self, prepare_run_as_user, _validate_resources):
        self.create_config()
        rule = self.create_rule(
            is_enabled=True,
            run_as_user="old-user",
            conditions=[{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
            agent_id="agent-a",
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )
        data = validate(SourceAnalysisRulePatchSerializer, {"bk_biz_id": 2, "agent_id": "agent-b"})
        data["rule_id"] = rule.id

        result = UpdateSourceAnalysisRuleResource().perform_request(data)

        prepare_run_as_user.assert_called_once_with()
        self.assertEqual(result["agent_id"], "agent-b")
        self.assertEqual(result["run_as_user"], "alice")

    def test_delete_rejects_default_and_hard_deletes_custom_rule(self):
        default_rule = self.create_rule(priority=-1, is_default=True)
        custom_rule = self.create_rule(priority=10)

        with self.assertRaises(SourceAnalysisDefaultRuleCannotDeleteError):
            DeleteSourceAnalysisRuleResource().perform_request({"bk_biz_id": 2, "rule_id": default_rule.id})

        DeleteSourceAnalysisRuleResource().perform_request({"bk_biz_id": 2, "rule_id": custom_rule.id})
        self.assertFalse(IssueSourceAnalysisRule.origin_objects.filter(id=custom_rule.id).exists())
        replacement = self.create_rule(priority=10)
        self.assertEqual(replacement.priority, 10)

    def test_enabling_incomplete_rule_is_rejected(self):
        self.create_config()
        rule = self.create_rule()
        data = validate(SourceAnalysisRulePatchSerializer, {"bk_biz_id": 2, "is_enabled": True})
        data["rule_id"] = rule.id

        with self.assertRaises(SourceAnalysisRuleIncompleteError):
            UpdateSourceAnalysisRuleResource().perform_request(data)

        rule.refresh_from_db()
        self.assertFalse(rule.is_enabled)

    def test_enabled_rule_without_run_as_user_reports_credential_error(self):
        config = self.create_config()
        rule = self.create_rule(
            is_enabled=True,
            conditions=[{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
        )

        with self.assertRaises(SourceAnalysisExecutionCredentialUnavailableError):
            SourceAnalysisBaseResource.validate_rule_local(rule, config)
