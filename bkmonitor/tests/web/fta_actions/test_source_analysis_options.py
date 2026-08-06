"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from api.devops.default import (
    ListUserProjectResource,
    ListUserRepositoryResource,
)
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import api
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from fta_web.issue.handlers.source_analysis import SourceAnalysisOptionsHandler
from fta_web.issue.resources import (
    SOURCE_ANALYSIS_UPSTREAM_UNAVAILABLE,
    ListSourceAnalysisBkciProjectsResource,
    ListSourceAnalysisBkciRepositoriesResource,
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


class TestSourceAnalysisOptionsHandler(SimpleTestCase):
    def test_projects_are_normalized(self):
        with patch.object(
            api.devops,
            "list_user_project",
            return_value=[
                {"project_code": "project-a", "project_name": "Project A"},
                {"project_code": "project-b", "project_name": "Project B"},
            ],
        ):
            self.assertEqual(
                SourceAnalysisOptionsHandler.list_bkci_projects(),
                [
                    {"id": "project-a", "name": "Project A"},
                    {"id": "project-b", "name": "Project B"},
                ],
            )

    def test_repositories_keep_git_alias_only(self):
        repositories = [
            {
                "aliasName": "git-repo",
                "repositoryHashId": "hash-a",
                "type": "CODE_GIT",
                "url": "https://example.com/git-repo.git",
            },
            {"aliasName": "svn-repo", "repositoryHashId": "hash-b", "type": "CODE_SVN"},
        ]
        with patch.object(
            api.devops, "list_user_repository", return_value={"records": repositories}
        ) as list_repositories:
            self.assertEqual(
                SourceAnalysisOptionsHandler.list_bkci_repositories("project-a"),
                [{"id": "git-repo", "name": "git-repo", "scm_type": "GIT"}],
            )

        list_repositories.assert_called_once_with(project_id="project-a")

    def test_invalid_upstream_shape_is_rejected(self):
        for upstream_data in (None, {}, ["invalid-item"]):
            with self.subTest(upstream_data=upstream_data):
                with patch.object(api.devops, "list_user_project", return_value=upstream_data):
                    with self.assertRaises(ValueError):
                        SourceAnalysisOptionsHandler.list_bkci_projects()


class TestSourceAnalysisOptionsResources(SimpleTestCase):
    def test_request_and_response_contract(self):
        project_request = ListSourceAnalysisBkciProjectsResource.RequestSerializer(data={"bk_biz_id": 2})
        self.assertTrue(project_request.is_valid(), project_request.errors)

        repository_request = ListSourceAnalysisBkciRepositoriesResource.RequestSerializer(
            data={"bk_biz_id": 2, "project_id": "project-a"}
        )
        self.assertTrue(repository_request.is_valid(), repository_request.errors)

        repository_response_fields = set(ListSourceAnalysisBkciRepositoriesResource.ResponseSerializer().fields)
        self.assertEqual(repository_response_fields, {"id", "name", "scm_type"})

    def test_upstream_error_has_stable_reason(self):
        upstream_error = BKAPIError(system_name="devops", url="project/list", result={"message": "failed"})
        with patch.object(SourceAnalysisOptionsHandler, "list_bkci_projects", side_effect=upstream_error):
            with self.assertRaises(CustomException) as error:
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(error.exception.data, {"reason": SOURCE_ANALYSIS_UPSTREAM_UNAVAILABLE})

    def test_viewset_uses_view_rule_permission(self):
        permission = SourceAnalysisOptionsViewSet().get_permissions()[0]

        self.assertIsInstance(permission, BusinessActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.VIEW_RULE])
        self.assertEqual(
            {route.endpoint for route in SourceAnalysisOptionsViewSet.resource_routes},
            {"bkci_projects", "bkci_repositories"},
        )
