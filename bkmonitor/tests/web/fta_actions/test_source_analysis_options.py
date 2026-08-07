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
from unittest.mock import patch

from django.test import SimpleTestCase

from api.devops.default import (
    ListUserProjectResource,
    ListUserRepositoryResource,
)
from api.aidev.default import ListAgentsResource, ListSkillsResource
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.errors.issue import SourceAnalysisUpstreamUnavailableError
from fta_web.issue.resources import (
    ListSourceAnalysisBkciProjectsResource,
    ListSourceAnalysisBkciRepositoriesResource,
    ListSourceAnalysisAgentsResource,
    ListSourceAnalysisKnowledgeBasesResource,
    ListSourceAnalysisSkillsResource,
)
from fta_web.issue.views import SourceAnalysisOptionsViewSet


class TestDevopsUserResources(SimpleTestCase):
    def test_actions_follow_devops_gateway_contract(self):
        self.assertEqual(ListUserProjectResource.action, "/v4/apigw-user/projects/project_list")
        self.assertEqual(
            ListUserRepositoryResource.action,
            "/v4/apigw-user/repositories/projects/{project_id}/repository_info_list",
        )

        serializer = ListUserRepositoryResource.RequestSerializer(data={"project_id": "project-a"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        request_data = serializer.validated_data.copy()
        self.assertTrue(
            ListUserRepositoryResource()
            .get_request_url(request_data)
            .endswith("/v4/apigw-user/repositories/projects/project-a/repository_info_list")
        )
        self.assertEqual(request_data, {})

    def test_repository_response_uses_devops_status_envelope(self):
        resource = ListUserRepositoryResource()
        with patch.object(resource, "report_api_failure_metric"):
            self.assertEqual(
                resource.render_response_data({}, {"status": 0, "message": "", "data": {"records": []}}),
                {"records": []},
            )
            with self.assertRaises(BKAPIError):
                resource.render_response_data({}, {"status": 1, "message": "failed", "data": None})


class TestAidevResources(SimpleTestCase):
    def test_actions_follow_aidev_private_gateway_contract(self):
        self.assertEqual(ListAgentsResource.action, "/openapi/aidev/private/v1/agents/")
        self.assertEqual(ListSkillsResource.action, "/openapi/aidev/private/v1/skills/")

        for resource_class in (ListAgentsResource, ListSkillsResource):
            with self.subTest(resource_class=resource_class.__name__):
                self.assertFalse(resource_class.INSERT_BK_USERNAME_TO_REQUEST_DATA)
                serializer = resource_class.RequestSerializer(data={"fuzzy": "source"})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data["space_id"], "all")
                self.assertEqual(serializer.validated_data["page"], 1)
                self.assertEqual(serializer.validated_data["page_size"], 20)

    @patch("api.aidev.default.get_local_request", return_value=object())
    @patch("api.aidev.default.get_mcp_access_token", return_value="user-access-token")
    def test_private_gateway_uses_current_user_access_token_only(self, get_access_token, get_request):
        headers = ListAgentsResource().get_headers()

        self.assertEqual(json.loads(headers["x-bkapi-authorization"]), {"access_token": "user-access-token"})
        get_access_token.assert_called_once_with(request=get_request.return_value)


class TestSourceAnalysisOptionsResources(SimpleTestCase):
    def test_projects_are_normalized(self):
        with patch.object(
            api.devops,
            "list_user_project",
            return_value=[
                {"projectCode": "project-a", "projectName": "Project A"},
                {"projectCode": "project-b", "projectName": "Project B"},
            ],
        ):
            self.assertEqual(
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2}),
                [
                    {"id": "project-a", "name": "Project A"},
                    {"id": "project-b", "name": "Project B"},
                ],
            )

    def test_projects_fall_back_to_legacy_fields(self):
        with patch.object(
            api.devops,
            "list_user_project",
            return_value=[{"project_code": "legacy-project", "project_name": "Legacy Project"}],
        ):
            self.assertEqual(
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2}),
                [{"id": "legacy-project", "name": "Legacy Project"}],
            )

    def test_repositories_keep_git_alias_only(self):
        repositories = [
            {
                "aliasName": "git-repo",
                "repositoryHashId": "hash-a",
                "type": "CODE_GIT",
                "url": "https://example.com/git-repo.git",
            },
            {
                "aliasName": "scm-git-repo",
                "repositoryHashId": "hash-b",
                "type": "SCM_GIT",
                "url": "https://example.com/scm-git-repo.git",
            },
            {"aliasName": "svn-repo", "repositoryHashId": "hash-c", "type": "CODE_SVN"},
        ]
        with patch.object(
            api.devops, "list_user_repository", return_value={"records": repositories}
        ) as list_repositories:
            self.assertEqual(
                ListSourceAnalysisBkciRepositoriesResource().perform_request(
                    {"bk_biz_id": 2, "project_id": "project-a"}
                ),
                [
                    {"id": "git-repo", "name": "git-repo", "scm_type": "GIT"},
                    {"id": "scm-git-repo", "name": "scm-git-repo", "scm_type": "GIT"},
                ],
            )

        list_repositories.assert_called_once_with(project_id="project-a")

    def test_invalid_upstream_shape_is_rejected(self):
        for upstream_data in (None, {}, ["invalid-item"]):
            with self.subTest(upstream_data=upstream_data):
                with patch.object(api.devops, "list_user_project", return_value=upstream_data):
                    with self.assertRaises(SourceAnalysisUpstreamUnavailableError) as error:
                        ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})
                self.assertEqual(error.exception.data, {"reason": SourceAnalysisUpstreamUnavailableError.reason})

    def test_aidev_options_are_normalized(self):
        cases = [
            (
                ListSourceAnalysisAgentsResource,
                "list_agents",
                {"count": 1, "results": [{"id": 11, "agent_name": "源码分析 Agent"}]},
                {"total": 1, "list": [{"id": "11", "name": "源码分析 Agent"}]},
            ),
            (
                ListSourceAnalysisSkillsResource,
                "list_skills",
                {"count": 1, "results": [{"id": 22, "skill_name": "代码检索 Skill"}]},
                {"total": 1, "list": [{"id": "22", "name": "代码检索 Skill"}]},
            ),
        ]
        for resource_class, api_name, upstream_data, expected in cases:
            with self.subTest(resource_class=resource_class.__name__):
                with patch.object(api.aidev, api_name, return_value=upstream_data) as list_resources:
                    actual = resource_class().perform_request(
                        {"bk_biz_id": 2, "keyword": "source", "page": 2, "page_size": 10}
                    )
                self.assertEqual(actual, expected)
                list_resources.assert_called_once_with(space_id="all", fuzzy="source", page=2, page_size=10)

    def test_aidev_options_omit_empty_keyword(self):
        with patch.object(api.aidev, "list_agents", return_value={"count": 0, "results": []}) as list_agents:
            result = ListSourceAnalysisAgentsResource().perform_request(
                {"bk_biz_id": 2, "keyword": "", "page": 1, "page_size": 20}
            )

        self.assertEqual(result, {"total": 0, "list": []})
        list_agents.assert_called_once_with(space_id="all", page=1, page_size=20)

    def test_knowledge_base_options_remain_empty_until_aidev_supports_user_list(self):
        resource = ListSourceAnalysisKnowledgeBasesResource()
        with patch.object(resource, "list_aidev_resources") as list_resources:
            self.assertEqual(
                resource.perform_request({"bk_biz_id": 2, "keyword": "source", "page": 1, "page_size": 20}),
                {"total": 0, "list": []},
            )
        list_resources.assert_not_called()

    def test_invalid_aidev_shape_is_rejected(self):
        for upstream_data in (None, {}, {"count": 1, "results": ["invalid-item"]}):
            with self.subTest(upstream_data=upstream_data):
                with patch.object(api.aidev, "list_agents", return_value=upstream_data):
                    with self.assertRaises(SourceAnalysisUpstreamUnavailableError) as error:
                        ListSourceAnalysisAgentsResource().perform_request(
                            {"bk_biz_id": 2, "keyword": "", "page": 1, "page_size": 20}
                        )
                self.assertEqual(error.exception.data, {"reason": SourceAnalysisUpstreamUnavailableError.reason})

    def test_request_and_response_contract(self):
        project_request = ListSourceAnalysisBkciProjectsResource.RequestSerializer(data={"bk_biz_id": 2})
        self.assertTrue(project_request.is_valid(), project_request.errors)

        repository_request = ListSourceAnalysisBkciRepositoriesResource.RequestSerializer(
            data={"bk_biz_id": 2, "project_id": "project-a"}
        )
        self.assertTrue(repository_request.is_valid(), repository_request.errors)

        repository_response_fields = set(ListSourceAnalysisBkciRepositoriesResource.ResponseSerializer().fields)
        self.assertEqual(repository_response_fields, {"id", "name", "scm_type"})

        aidev_request = ListSourceAnalysisAgentsResource.RequestSerializer(data={"bk_biz_id": 2})
        self.assertTrue(aidev_request.is_valid(), aidev_request.errors)
        self.assertEqual(aidev_request.validated_data["page"], 1)
        self.assertEqual(aidev_request.validated_data["page_size"], 20)
        self.assertEqual(set(ListSourceAnalysisAgentsResource.ResponseSerializer().fields), {"total", "list"})

        oversized_page = ListSourceAnalysisAgentsResource.RequestSerializer(data={"bk_biz_id": 2, "page_size": 101})
        self.assertFalse(oversized_page.is_valid())

    def test_upstream_error_has_stable_reason(self):
        upstream_error = BKAPIError(system_name="devops", url="project/list", result={"message": "failed"})
        with patch.object(api.devops, "list_user_project", side_effect=upstream_error):
            with self.assertRaises(SourceAnalysisUpstreamUnavailableError) as error:
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(error.exception.data, {"reason": SourceAnalysisUpstreamUnavailableError.reason})

    def test_viewset_uses_view_rule_permission(self):
        permission = SourceAnalysisOptionsViewSet().get_permissions()[0]

        self.assertIsInstance(permission, BusinessActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.VIEW_RULE])
        self.assertEqual(
            {route.endpoint for route in SourceAnalysisOptionsViewSet.resource_routes},
            {"bkci_projects", "bkci_repositories", "agents", "skills", "knowledge_bases"},
        )
