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

from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import IssueSourceAnalysisConfig, IssueSourceAnalysisRule
from bkmonitor.utils.user import set_local_username
from core.drf_resource.exceptions import custom_exception_handler
from core.errors.issue import (
    IssueError,
    SourceAnalysisConfigNotFoundError,
    SourceAnalysisDefaultRuleCannotDeleteError,
    SourceAnalysisDefaultRuleConditionsInvalidError,
    SourceAnalysisDefaultRulePriorityImmutableError,
    SourceAnalysisFlowInitializationFailedError,
    SourceAnalysisRepositoryInvalidError,
    SourceAnalysisResourceNotFoundError,
    SourceAnalysisRuleIncompleteError,
    SourceAnalysisRulePriorityConflictError,
    SourceAnalysisUpstreamUnavailableError,
)
from fta_web.issue.resources import (
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
from fta_web.issue.views import SourceAnalysisConfigViewSet, SourceAnalysisRulesViewSet


def validate(serializer_class, data):
    serializer = serializer_class(data=data)
    assert serializer.is_valid(), serializer.errors
    return dict(serializer.validated_data)


class TestSourceAnalysisRuleSerializers(SimpleTestCase):
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
                "agent_id": "1",
                "skill_ids": ["3", "3"],
            },
        )

        # agent 是单值，不参与去重排序
        self.assertEqual(data["agent_id"], "1")
        self.assertEqual(data["skill_ids"], ["3"])

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

    def test_non_empty_knowledge_base_is_rejected_until_user_api_exists(self):
        rule = IssueSourceAnalysisRule(
            bk_biz_id=2,
            priority=1,
            agent_id="1",
            knowledge_base_ids=["10"],
        )

        with self.assertRaises(SourceAnalysisResourceNotFoundError):
            SourceAnalysisBaseResource.validate_resources(rule)

    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"1", "2"})
    def test_visible_agent_passes_validation(self, _list_visible):
        rule = IssueSourceAnalysisRule(bk_biz_id=2, priority=1, agent_id="2")

        SourceAnalysisBaseResource.validate_resources(rule)

    @patch.object(SourceAnalysisBaseResource, "list_visible_aidev_ids", return_value={"1", "2"})
    def test_invisible_agent_is_rejected(self, _list_visible):
        rule = IssueSourceAnalysisRule(bk_biz_id=2, priority=1, agent_id="99")

        with self.assertRaises(SourceAnalysisResourceNotFoundError):
            SourceAnalysisBaseResource.validate_resources(rule)

    @patch(
        "fta_web.issue.resources.api.bk_incident.ensure_source_analysis_scene",
        side_effect=ValueError("BKFara APIGW is not configured"),
    )
    def test_bkfara_initialization_error_fails_closed(self, _ensure_scene):
        with self.assertRaises(SourceAnalysisFlowInitializationFailedError):
            SourceAnalysisBaseResource.ensure_flow_initialized(2, "project-a")

    def test_source_analysis_errors_use_unique_issue_error_codes(self):
        error_classes = [
            SourceAnalysisUpstreamUnavailableError,
            SourceAnalysisConfigNotFoundError,
            SourceAnalysisRepositoryInvalidError,
            SourceAnalysisResourceNotFoundError,
            SourceAnalysisRuleIncompleteError,
            SourceAnalysisRulePriorityConflictError,
            SourceAnalysisDefaultRuleCannotDeleteError,
            SourceAnalysisDefaultRulePriorityImmutableError,
            SourceAnalysisFlowInitializationFailedError,
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

    @patch.object(SourceAnalysisBaseResource, "validate_repository")
    @patch.object(SourceAnalysisBaseResource, "ensure_flow_initialized")
    def test_save_config_creates_default_and_syncs_rule_snapshots(self, ensure_initialized, validate_repository):
        custom_rule = self.create_rule()

        result = SaveSourceAnalysisConfigResource().perform_request(
            {"bk_biz_id": 2, "bkci_project_id": "project-a", "repository_alias": "repo-a"}
        )

        validate_repository.assert_called_once_with(2, "project-a", "repo-a")
        ensure_initialized.assert_not_called()
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

    @patch.object(SourceAnalysisBaseResource, "validate_repository")
    @patch.object(
        SourceAnalysisBaseResource,
        "ensure_flow_initialized",
        side_effect=SourceAnalysisFlowInitializationFailedError(),
    )
    def test_project_change_rolls_back_when_flow_initialization_fails(self, ensure_initialized, _validate_repository):
        self.create_config()
        self.create_rule(
            is_enabled=True,
            conditions=[{"field": "alert.strategy_id", "value": ["1"], "method": "eq", "condition": "and"}],
            agent_id="1",
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        with self.assertRaises(SourceAnalysisFlowInitializationFailedError):
            SaveSourceAnalysisConfigResource().perform_request(
                {"bk_biz_id": 2, "bkci_project_id": "project-b", "repository_alias": "repo-b"}
            )

        ensure_initialized.assert_called_once_with(2, "project-b")
        config = IssueSourceAnalysisConfig.objects.get(bk_biz_id=2)
        rule = IssueSourceAnalysisRule.objects.get(bk_biz_id=2, is_default=False)
        self.assertEqual((config.bkci_project_id, config.repository_alias), ("project-a", "repo-a"))
        self.assertEqual((rule.bkci_project_id, rule.repository_alias), ("project-a", "repo-a"))

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
    @patch.object(SourceAnalysisBaseResource, "ensure_flow_initialized", return_value="provision-1")
    def test_enabled_rule_validates_resources_and_initializes_flow(self, ensure_initialized, validate_resources):
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
        ensure_initialized.assert_called_once_with(2, "project-a")
        self.assertEqual(
            IssueSourceAnalysisConfig.objects.get(bk_biz_id=2).bkfara_provision_id,
            "provision-1",
        )
        self.assertTrue(result["is_enabled"])
        self.assertEqual((result["bkci_project_id"], result["repository_alias"]), ("project-a", "repo-a"))

    @patch.object(SourceAnalysisBaseResource, "validate_resources")
    @patch.object(
        SourceAnalysisBaseResource,
        "ensure_flow_initialized",
        side_effect=SourceAnalysisFlowInitializationFailedError(),
    )
    def test_enabled_rule_save_rolls_back_when_flow_initialization_fails(
        self, _ensure_initialized, _validate_resources
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

        with self.assertRaises(SourceAnalysisFlowInitializationFailedError):
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
