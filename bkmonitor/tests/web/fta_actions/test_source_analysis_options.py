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

import requests
from django.test import SimpleTestCase

from api.devops.default import (
    ListUserProjectResource,
    ListUserRepositoryResource,
)
from core.drf_resource.contrib.api import APIResource
from api.aidev.default import (
    ListAgentsResource,
    ListKnowledgeBasesResource,
    ListSkillsResource,
    ListSpacesResource,
)
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import IssueSourceAnalysisRule
from bkmonitor.utils.cache import CacheType
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.errors.issue import SourceAnalysisUpstreamUnavailableError
from fta_web.issue.resources import (
    ListSourceAnalysisBkciProjectsResource,
    ListSourceAnalysisBkciRepositoriesResource,
    ListSourceAnalysisAgentsResource,
    ListSourceAnalysisKnowledgeBasesResource,
    ListSourceAnalysisSkillsResource,
    SourceAnalysisBaseResource,
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

    def test_user_ticket_travels_in_authorization_header(self):
        """用户凭证必须放在 X-Bkapi-Authorization 中。

        APIGW 只从该请求头识别用户态身份，放进请求参数时 apigw-user 接口会返回
        1640001 认证失败，同时 ticket 会随 GET URL 进入访问日志与失败日志。
        """

        base_headers = {"x-bkapi-authorization": json.dumps({"bk_username": "tester"})}

        class _WithoutAppCredential:
            BKCI_APP_CODE = ""
            BKCI_APP_SECRET = ""

        class _WithAppCredential:
            BKCI_APP_CODE = "bkci-app"
            BKCI_APP_SECRET = "bkci-secret"

        # 每次返回新字典：get_headers 会就地改写返回值，共享同一份会串台
        with patch.object(APIResource, "get_headers", side_effect=lambda *args, **kwargs: dict(base_headers)):
            # 蓝盾专用应用凭证缺省时，仍需注入用户凭证
            with patch("api.devops.default.settings", _WithoutAppCredential()):
                resource = ListUserProjectResource()
                resource.bk_ticket = "ticket-xyz"
                authorization = json.loads(resource.get_headers()["x-bkapi-authorization"])
                self.assertEqual(authorization["bk_ticket"], "ticket-xyz")
                self.assertEqual(authorization["bk_username"], "tester")
                self.assertNotIn("bk_app_code", authorization)

                # 无用户凭证时不写入空值，避免网关按无效身份处理
                authorization = json.loads(ListUserProjectResource().get_headers()["x-bkapi-authorization"])
                self.assertNotIn("bk_ticket", authorization)

            # 应用凭证与用户凭证并存
            with patch("api.devops.default.settings", _WithAppCredential()):
                resource = ListUserProjectResource()
                resource.bk_ticket = "ticket-xyz"
                authorization = json.loads(resource.get_headers()["x-bkapi-authorization"])
                self.assertEqual(authorization["bk_app_code"], "bkci-app")
                self.assertEqual(authorization["bk_app_secret"], "bkci-secret")
                self.assertEqual(authorization["bk_ticket"], "ticket-xyz")

    def test_user_ticket_is_stripped_from_request_params(self):
        resource = ListUserRepositoryResource()
        with patch.object(
            APIResource,
            "full_request_data",
            return_value={"bk_ticket": "ticket-xyz", "bk_username": "tester", "project_id": "project-a"},
        ):
            self.assertEqual(resource.full_request_data({}), {"bk_username": "tester", "project_id": "project-a"})


class TestAidevResources(SimpleTestCase):
    def test_actions_follow_aidev_private_gateway_contract(self):
        self.assertEqual(ListAgentsResource.action, "/openapi/aidev/private/v1/agents/")
        self.assertEqual(ListSpacesResource.action, "/openapi/aidev/private/v1/spaces/")
        self.assertEqual(ListSkillsResource.action, "/openapi/aidev/private/v1/skills/")
        self.assertEqual(
            ListKnowledgeBasesResource.action,
            "/openapi/aidev/private/v1/knowledgebase/list/",
        )
        self.assertEqual(ListKnowledgeBasesResource.method, "POST")

        for resource_class in (ListAgentsResource, ListSkillsResource):
            with self.subTest(resource_class=resource_class.__name__):
                self.assertFalse(resource_class.INSERT_BK_USERNAME_TO_REQUEST_DATA)
                serializer = resource_class.RequestSerializer(data={"fuzzy": "source"})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data["space_id"], "all")
                self.assertEqual(serializer.validated_data["page"], 1)
                self.assertEqual(serializer.validated_data["page_size"], 20)

        knowledge_base_serializer = ListKnowledgeBasesResource.RequestSerializer(data={"space_id": "space-a"})
        self.assertTrue(knowledge_base_serializer.is_valid(), knowledge_base_serializer.errors)
        self.assertEqual(knowledge_base_serializer.validated_data["page"], 1)
        self.assertEqual(knowledge_base_serializer.validated_data["page_size"], 20)
        self.assertEqual(knowledge_base_serializer.validated_data["order_by"], "name")
        self.assertTrue(knowledge_base_serializer.validated_data["with_private"])
        self.assertFalse(ListKnowledgeBasesResource.RequestSerializer(data={}).is_valid())

    def test_private_gateway_preserves_application_credentials_and_current_user_ticket(self):
        base_headers = {
            "x-bkapi-authorization": json.dumps(
                {
                    "bk_app_code": "bkmonitorv3",
                    "bk_app_secret": "app-secret",
                    "bk_ticket": "user-ticket",
                    "bk_username": "tester",
                }
            )
        }
        with patch.object(APIResource, "get_headers", return_value=base_headers):
            headers = ListAgentsResource().get_headers()

        self.assertEqual(
            json.loads(headers["x-bkapi-authorization"]),
            {
                "bk_app_code": "bkmonitorv3",
                "bk_app_secret": "app-secret",
                "bk_ticket": "user-ticket",
                "bk_username": "tester",
            },
        )

    def test_private_gateway_converts_connection_error(self):
        resource = ListAgentsResource()

        with (
            patch.object(resource, "get_headers", return_value={}),
            patch.object(resource, "report_api_failure_metric"),
            patch.object(resource.session, "get", side_effect=requests.ConnectionError("connection unavailable")),
            self.assertRaises(BKAPIError),
        ):
            resource.perform_request({"space_id": "all", "page": 1, "page_size": 20})


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
                {
                    "total": 2,
                    "list": [
                        {"id": "project-a", "name": "Project A"},
                        {"id": "project-b", "name": "Project B"},
                    ],
                },
            )

    def test_projects_fall_back_to_legacy_fields(self):
        with patch.object(
            api.devops,
            "list_user_project",
            return_value=[{"project_code": "legacy-project", "project_name": "Legacy Project"}],
        ):
            self.assertEqual(
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2}),
                {"total": 1, "list": [{"id": "legacy-project", "name": "Legacy Project"}]},
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
                    {"bk_biz_id": 2, "bkci_project_id": "project-a"}
                ),
                {
                    "total": 2,
                    "list": [
                        {"id": "git-repo", "name": "git-repo", "scm_type": "GIT"},
                        {"id": "scm-git-repo", "name": "scm-git-repo", "scm_type": "GIT"},
                    ],
                },
            )

        # 对外统一为 bkci_project_id，蓝盾接口自身的参数名仍是 project_id
        list_repositories.assert_called_once_with(project_id="project-a")

    def test_invalid_upstream_shape_is_rejected(self):
        for upstream_data in (None, {}, ["invalid-item"]):
            with self.subTest(upstream_data=upstream_data):
                with patch.object(api.devops, "list_user_project", return_value=upstream_data):
                    with self.assertRaises(SourceAnalysisUpstreamUnavailableError):
                        ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})

    def test_aidev_options_are_normalized(self):
        spaces = [
            {"space_id": "space-a", "space_name": "AIDEV Helper"},
            {"space_id": "space-b", "space_name": "Source Analysis"},
        ]
        cases = [
            (
                ListSourceAnalysisAgentsResource,
                "list_agents",
                {
                    "count": 1,
                    "results": [{"id": 11, "agent_name": "源码分析 Agent", "space_id": "space-a"}],
                },
                {
                    "total": 1,
                    "list": [
                        {
                            "id": "11",
                            "name": "源码分析 Agent",
                            "space_id": "space-a",
                            "space_name": "AIDEV Helper",
                        }
                    ],
                },
            ),
            (
                ListSourceAnalysisSkillsResource,
                "list_skills",
                {
                    "count": 1,
                    "results": [{"id": 22, "skill_name": "代码检索 Skill", "space_id": "space-b"}],
                },
                {
                    "total": 1,
                    "list": [
                        {
                            "id": "22",
                            "name": "代码检索 Skill",
                            "space_id": "space-b",
                            "space_name": "Source Analysis",
                        }
                    ],
                },
            ),
        ]
        for resource_class, api_name, upstream_data, expected in cases:
            with self.subTest(resource_class=resource_class.__name__):
                with (
                    patch.object(api.aidev, api_name, return_value=upstream_data) as list_resources,
                    patch.object(api.aidev, "list_spaces", return_value=spaces) as list_spaces,
                ):
                    actual = resource_class().perform_request({"bk_biz_id": 2})
                self.assertEqual(actual, expected)
                # 接口不分页，BKM 按安全分页大小遍历上游，不再把页码和关键词透给 AIDEV
                list_resources.assert_called_once_with(space_id="all", page=1, page_size=200)
                list_spaces.assert_called_once_with()

    def test_aidev_options_traverse_all_upstream_pages(self):
        """规则只存 ID，前端要用 ID 回填名称，因此选项接口必须一次返回全量而不是首页。"""

        with (
            patch.object(
                api.aidev,
                "list_agents",
                side_effect=[
                    {"count": 201, "results": [{"id": index, "agent_name": f"agent-{index}"} for index in range(200)]},
                    {"count": 201, "results": [{"id": 200, "agent_name": "agent-200"}]},
                ],
            ) as list_agents,
            patch.object(api.aidev, "list_spaces", return_value=[]),
        ):
            result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(result["total"], 201)
        self.assertEqual(len(result["list"]), 201)
        self.assertEqual(result["list"][-1]["id"], "200")
        self.assertEqual(list_agents.call_count, 2)
        list_agents.assert_any_call(space_id="all", page=2, page_size=200)

    def test_aidev_options_dedupe_items_repeated_across_pages(self):
        """上游翻页期间数据变动可能让同一资源出现在两页，选项列表不能出现重复项。"""

        with (
            patch.object(
                api.aidev,
                "list_agents",
                side_effect=[
                    {"count": 3, "results": [{"id": 1, "agent_name": "agent-1"}, {"id": 2, "agent_name": "agent-2"}]},
                    {"count": 3, "results": [{"id": 2, "agent_name": "agent-2"}, {"id": 3, "agent_name": "agent-3"}]},
                ],
            ),
            patch.object(api.aidev, "list_spaces", return_value=[]),
        ):
            result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(result["total"], 3)
        self.assertEqual([item["id"] for item in result["list"]], ["1", "2", "3"])

    def test_aidev_options_reject_pagination_beyond_safety_limit(self):
        """上游 count 与实际条目长期不一致时必须终止遍历，不能无限翻页。"""

        with (
            patch.object(
                api.aidev,
                "list_agents",
                return_value={"count": 10000, "results": [{"id": 1, "agent_name": "agent-1"}]},
            ) as list_agents,
            patch.object(api.aidev, "list_spaces", return_value=[]),
            self.assertRaises(SourceAnalysisUpstreamUnavailableError),
        ):
            ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(list_agents.call_count, 100)

    def test_aidev_options_query_through_user_cached_entry(self):
        """选项查询必须走带缓存的入口：一次展开就要遍历上游全部分页，重复查询会持续压 AIDEV。"""

        # using_cache 包装后会挂上 cacheless / refresh 调用模式，可用于确认装饰器没被摘掉
        self.assertTrue(hasattr(SourceAnalysisBaseResource.query_visible_aidev_items, "cacheless"))
        # AIDEV 资源按当前用户登录态过滤，缓存必须按用户隔离，否则会跨用户串资源
        self.assertTrue(CacheType.AIDEV.user_related)

        # 缓存键由入参 md5 生成，因此入参只能是资源类型标识，不能是 api 方法对象
        self.assertEqual(ListSourceAnalysisAgentsResource.aidev_resource_type, "agents")
        self.assertEqual(ListSourceAnalysisSkillsResource.aidev_resource_type, "skills")
        self.assertEqual(
            SourceAnalysisBaseResource.AIDEV_LIST_APIS,
            {"agents": "list_agents", "skills": "list_skills"},
        )

        for resource_class, resource_type in (
            (ListSourceAnalysisAgentsResource, "agents"),
            (ListSourceAnalysisSkillsResource, "skills"),
        ):
            with self.subTest(resource_type=resource_type):
                with patch.object(
                    SourceAnalysisBaseResource, "query_visible_aidev_items", return_value=[]
                ) as query_items:
                    resource_class().perform_request({"bk_biz_id": 2})
                query_items.assert_called_once_with(resource_type, "id")

    def test_aidev_cached_entry_reaches_matching_upstream_api(self):
        """资源类型到上游接口的映射不能串：Agent 缓存条目不能由 Skill 列表填充。"""

        upstream = {"count": 1, "results": [{"id": 1, "agent_name": "agent-1", "skill_name": "skill-1"}]}
        with (
            patch.object(api.aidev, "list_agents", return_value=upstream) as list_agents,
            patch.object(api.aidev, "list_skills", return_value=upstream) as list_skills,
        ):
            SourceAnalysisBaseResource.query_visible_aidev_items.cacheless("agents", "id")
            list_agents.assert_called_once_with(space_id="all", page=1, page_size=200)
            list_skills.assert_not_called()

            SourceAnalysisBaseResource.query_visible_aidev_items.cacheless("skills", "id")
            list_skills.assert_called_once_with(space_id="all", page=1, page_size=200)

    def test_enable_validation_does_not_reuse_option_cache(self):
        """启用校验决定规则能否保存，必须实时遍历：用选项缓存会把刚建好的资源判为无效。"""

        rule = IssueSourceAnalysisRule(bk_biz_id=2, priority=1, agent_id="1")
        with (
            patch.object(SourceAnalysisBaseResource, "query_visible_aidev_items") as query_items,
            patch.object(api.aidev, "list_agents", return_value={"count": 1, "results": [{"id": 1}]}) as list_agents,
        ):
            SourceAnalysisBaseResource.validate_resources(rule)

        query_items.assert_not_called()
        list_agents.assert_called_once_with(space_id="all", page=1, page_size=200)

    def test_aidev_options_return_empty_list_without_querying_spaces(self):
        with (
            patch.object(api.aidev, "list_agents", return_value={"count": 0, "results": []}) as list_agents,
            patch.object(api.aidev, "list_spaces") as list_spaces,
        ):
            result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(result, {"total": 0, "list": []})
        list_agents.assert_called_once_with(space_id="all", page=1, page_size=200)
        list_spaces.assert_not_called()

    def test_knowledge_base_options_are_aggregated_by_visible_space(self):
        spaces = [
            {"space_id": "space-a", "space_name": "AIDEV Helper"},
            {"space_id": "space-b", "space_name": "Source Analysis"},
        ]

        def list_knowledge_bases(**kwargs):
            if kwargs["space_id"] == "space-a":
                return {
                    "count": 1,
                    "results": [{"id": 556, "name": "APM 领域知识库", "space_id": "space-a"}],
                }
            return {
                "count": 2,
                "results": [
                    {"id": 556, "name": "重复知识库", "space_id": "space-a"},
                    {"id": 1228, "name": "BKFara 使用手册", "space_id": "space-b"},
                ],
            }

        with (
            patch.object(api.aidev, "list_spaces", return_value=spaces) as list_spaces,
            patch.object(api.aidev, "list_knowledge_bases", side_effect=list_knowledge_bases) as list_knowledge_bases,
        ):
            result = SourceAnalysisBaseResource.query_visible_aidev_knowledge_bases.cacheless()
            options = ListSourceAnalysisKnowledgeBasesResource.build_aidev_options(*result)

        self.assertEqual(
            options,
            {
                "total": 2,
                "list": [
                    {
                        "id": "556",
                        "name": "APM 领域知识库",
                        "space_id": "space-a",
                        "space_name": "AIDEV Helper",
                    },
                    {
                        "id": "1228",
                        "name": "BKFara 使用手册",
                        "space_id": "space-b",
                        "space_name": "Source Analysis",
                    },
                ],
            },
        )
        list_spaces.assert_called_once_with()
        self.assertEqual(list_knowledge_bases.call_count, 2)
        for space_id in ("space-a", "space-b"):
            list_knowledge_bases.assert_any_call(
                space_id=space_id,
                page=1,
                page_size=200,
                order_by="name",
                with_private=True,
            )

    def test_knowledge_base_options_return_empty_when_user_has_no_visible_space(self):
        with (
            patch.object(api.aidev, "list_spaces", return_value=[]),
            patch.object(api.aidev, "list_knowledge_bases") as list_knowledge_bases,
        ):
            result = SourceAnalysisBaseResource.query_visible_aidev_knowledge_bases.cacheless()

        self.assertEqual(result, ([], {}))
        list_knowledge_bases.assert_not_called()

    def test_knowledge_base_option_fails_closed_when_one_space_query_fails(self):
        spaces = [
            {"space_id": "space-a", "space_name": "AIDEV Helper"},
            {"space_id": "space-b", "space_name": "Source Analysis"},
        ]
        upstream_error = BKAPIError(system_name="aidev", url="knowledgebase/list/", result={"message": "failed"})
        with (
            patch.object(api.aidev, "list_spaces", return_value=spaces),
            patch.object(
                api.aidev,
                "list_knowledge_bases",
                side_effect=[{"count": 0, "results": []}, upstream_error],
            ),
            patch.object(
                ListSourceAnalysisKnowledgeBasesResource,
                "query_visible_aidev_knowledge_bases",
                side_effect=SourceAnalysisBaseResource.load_visible_aidev_knowledge_bases,
            ),
            self.assertRaises(SourceAnalysisUpstreamUnavailableError),
        ):
            ListSourceAnalysisKnowledgeBasesResource().perform_request({"bk_biz_id": 2})

    def test_invalid_aidev_shape_is_rejected(self):
        for upstream_data in (None, {}, {"count": 1, "results": ["invalid-item"]}):
            with self.subTest(upstream_data=upstream_data):
                with patch.object(api.aidev, "list_agents", return_value=upstream_data):
                    with self.assertRaises(SourceAnalysisUpstreamUnavailableError):
                        ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

    def test_aidev_option_degrades_when_space_query_fails(self):
        """空间名称只用于展示，/spaces/ 异常或协议不符时资源列表必须照常返回。"""

        upstream_data = {
            "count": 1,
            "results": [{"id": 11, "agent_name": "源码分析 Agent", "space_id": "space-a"}],
        }
        broken_space_results = (
            {"return_value": None},
            {"return_value": [{"space_id": "space-a"}]},
            {"side_effect": BKAPIError(system_name="aidev", url="spaces/", result={"message": "failed"})},
        )
        for space_result in broken_space_results:
            with self.subTest(space_result=space_result):
                with (
                    patch.object(api.aidev, "list_agents", return_value=upstream_data),
                    patch.object(api.aidev, "list_spaces", **space_result),
                ):
                    result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

                self.assertEqual(
                    result,
                    {
                        "total": 1,
                        "list": [
                            {
                                "id": "11",
                                "name": "源码分析 Agent",
                                "space_id": "space-a",
                                "space_name": "space-a",
                            }
                        ],
                    },
                )

    def test_aidev_option_keeps_resource_missing_space_id(self):
        """空间字段不进入规则保存协议，上游缺失 space_id 时不能拖垮整个选择器。"""

        for broken_item in (
            {"id": 11, "agent_name": "源码分析 Agent"},
            {"id": 11, "agent_name": "源码分析 Agent", "space_id": None},
            {"id": 11, "agent_name": "源码分析 Agent", "space_id": ""},
        ):
            with self.subTest(broken_item=broken_item):
                with (
                    patch.object(api.aidev, "list_agents", return_value={"count": 1, "results": [broken_item]}),
                    patch.object(
                        api.aidev,
                        "list_spaces",
                        return_value=[{"space_id": "space-a", "space_name": "AIDEV Helper"}],
                    ),
                ):
                    result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

                self.assertEqual(
                    result,
                    {
                        "total": 1,
                        "list": [{"id": "11", "name": "源码分析 Agent", "space_id": "", "space_name": ""}],
                    },
                )

    def test_aidev_option_rejects_resource_missing_id_or_name(self):
        """id 与 name 是选项的必要内容，缺失时仍按上游不可用处理。"""

        for broken_item in (
            {"agent_name": "源码分析 Agent", "space_id": "space-a"},
            {"id": 11, "space_id": "space-a"},
            {"id": 11, "agent_name": "", "space_id": "space-a"},
        ):
            with self.subTest(broken_item=broken_item):
                with (
                    patch.object(api.aidev, "list_agents", return_value={"count": 1, "results": [broken_item]}),
                    patch.object(
                        api.aidev,
                        "list_spaces",
                        return_value=[{"space_id": "space-a", "space_name": "AIDEV Helper"}],
                    ),
                    self.assertRaises(SourceAnalysisUpstreamUnavailableError),
                ):
                    ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

    def test_aidev_option_falls_back_to_space_id_for_public_cross_space_resource(self):
        upstream_data = {
            "count": 1,
            "results": [{"id": 11, "agent_name": "源码分析 Agent", "space_id": "space-a"}],
        }
        with (
            patch.object(api.aidev, "list_agents", return_value=upstream_data),
            patch.object(
                api.aidev,
                "list_spaces",
                return_value=[{"space_id": "space-b", "space_name": "Other Space"}],
            ),
        ):
            result = ListSourceAnalysisAgentsResource().perform_request({"bk_biz_id": 2})

        self.assertEqual(
            result,
            {
                "total": 1,
                "list": [
                    {
                        "id": "11",
                        "name": "源码分析 Agent",
                        "space_id": "space-a",
                        "space_name": "space-a",
                    }
                ],
            },
        )

    def test_request_contract(self):
        project_request = ListSourceAnalysisBkciProjectsResource.RequestSerializer(data={"bk_biz_id": 2})
        self.assertTrue(project_request.is_valid(), project_request.errors)

        repository_request = ListSourceAnalysisBkciRepositoriesResource.RequestSerializer(
            data={"bk_biz_id": 2, "bkci_project_id": "project-a"}
        )
        self.assertTrue(repository_request.is_valid(), repository_request.errors)

        missing_project = ListSourceAnalysisBkciRepositoriesResource.RequestSerializer(data={"bk_biz_id": 2})
        self.assertFalse(missing_project.is_valid())

        # 选项接口不分页，请求协议只保留 bk_biz_id
        aidev_request = ListSourceAnalysisAgentsResource.RequestSerializer(
            data={"bk_biz_id": 2, "page": 3, "page_size": 50, "keyword": "source"}
        )
        self.assertTrue(aidev_request.is_valid(), aidev_request.errors)
        self.assertEqual(dict(aidev_request.validated_data), {"bk_biz_id": 2})

    def test_upstream_error_raises_specific_error(self):
        upstream_error = BKAPIError(system_name="devops", url="project/list", result={"message": "failed"})
        with patch.object(api.devops, "list_user_project", side_effect=upstream_error):
            with self.assertRaises(SourceAnalysisUpstreamUnavailableError):
                ListSourceAnalysisBkciProjectsResource().perform_request({"bk_biz_id": 2})

    def test_viewset_uses_view_rule_permission(self):
        permission = SourceAnalysisOptionsViewSet().get_permissions()[0]

        self.assertIsInstance(permission, BusinessActionPermission)
        self.assertEqual(permission.actions, [ActionEnum.VIEW_RULE])
        self.assertEqual(
            {route.endpoint for route in SourceAnalysisOptionsViewSet.resource_routes},
            {"bkci_projects", "bkci_repositories", "agents", "skills", "knowledge_bases"},
        )
