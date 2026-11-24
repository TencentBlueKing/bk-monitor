from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.iam import ActionEnum
from apps.iam.exceptions import IAMDependencyError
from apps.log_search.handlers.meta import MetaHandler
from apps.log_search.views.bizs_views import BizsViewSet
from apps.log_search.views.meta_views import MetaViewSet


class MetaGetUserProjectsTest(SimpleTestCase):
    def setUp(self):
        self.projects = [
            SimpleNamespace(project_id=11, project_name="业务甲", bk_biz_id=2, time_zone="Asia/Shanghai"),
            SimpleNamespace(project_id=12, project_name="业务乙", bk_biz_id=3, time_zone="UTC"),
        ]
        projects = patch("apps.log_search.handlers.meta.ProjectInfo.objects.all", return_value=self.projects)
        projects.start()
        self.addCleanup(projects.stop)
        tenant = patch("apps.log_search.handlers.meta.get_request_tenant_id", return_value="tenant-1")
        tenant.start()
        self.addCleanup(tenant.stop)
        permission = patch("apps.log_search.handlers.meta.Permission")
        self.permission_cls = permission.start()
        self.addCleanup(permission.stop)
        self.permission_cls.return_value.filter_space_list_by_action.return_value = [{"bk_biz_id": 2}]

    def test_default_returns_full_catalog_with_real_permissions_and_legacy_fields(self):
        results = MetaHandler.get_user_projects("alice")

        self.assertEqual(
            results,
            [
                {
                    "project_id": 11,
                    "project_name": "[2] 业务甲",
                    "bk_biz_id": 2,
                    "time_zone": "Asia/Shanghai",
                    "project_manage": True,
                    "permission": {ActionEnum.VIEW_BUSINESS.id: True},
                },
                {
                    "project_id": 12,
                    "project_name": "[3] 业务乙",
                    "bk_biz_id": 3,
                    "time_zone": "UTC",
                    "project_manage": False,
                    "permission": {ActionEnum.VIEW_BUSINESS.id: False},
                },
            ],
        )

    def test_permission_filter_keeps_only_authorized_projects(self):
        results = MetaHandler.get_user_projects("alice", has_permission=True)

        self.assertEqual([project["bk_biz_id"] for project in results], [2])
        self.assertTrue(results[0]["permission"][ActionEnum.VIEW_BUSINESS.id])

    def test_no_permissions_produces_an_empty_filtered_list(self):
        self.permission_cls.return_value.filter_space_list_by_action.return_value = []

        self.assertEqual(MetaHandler.get_user_projects("alice", has_permission=True), [])

    def test_username_and_tenant_select_the_shared_space_permission_scope(self):
        for username, allowed_biz_id in [("alice", 2), ("bob", 3)]:
            with self.subTest(username=username):
                self.permission_cls.reset_mock()
                self.permission_cls.return_value.filter_space_list_by_action.return_value = [
                    {"bk_biz_id": allowed_biz_id}
                ]

                results = MetaHandler.get_user_projects(username, has_permission=True)

                self.permission_cls.assert_called_once_with(username=username, bk_tenant_id="tenant-1")
                self.permission_cls.return_value.filter_space_list_by_action.assert_called_once_with(
                    ActionEnum.VIEW_BUSINESS, "tenant-1"
                )
                self.assertEqual([project["bk_biz_id"] for project in results], [allowed_biz_id])

    def test_iam_failure_does_not_return_an_authorized_catalog(self):
        self.permission_cls.return_value.filter_space_list_by_action.side_effect = IAMDependencyError(
            "timeout", provider="v4"
        )

        with self.assertRaises(IAMDependencyError):
            MetaHandler.get_user_projects("alice")

    @patch("apps.log_search.views.bizs_views.get_request_username", return_value="alice")
    def test_bizs_caller_keeps_its_legacy_catalog_and_fields(self, _username):
        response = BizsViewSet().list(Request(APIRequestFactory().get("/api/v1/bizs/")))

        self.assertEqual(
            response.data,
            [
                {"bk_biz_id": 2, "bk_biz_name": "[2] 业务甲"},
                {"bk_biz_id": 3, "bk_biz_name": "[3] 业务乙"},
            ],
        )


class ProjectsMineViewTest(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.log_search.views.meta_views.get_request_username", return_value="alice")
    @patch("apps.log_search.views.meta_views.MetaHandler.get_user_projects", return_value=[])
    def test_query_boolean_controls_permission_filter(self, get_user_projects, _username):
        for query, expected in [
            ({}, False),
            ({"has_permission": "false"}, False),
            ({"has_permission": "0"}, False),
            ({"has_permission": "true"}, True),
            ({"has_permission": "1"}, True),
        ]:
            with self.subTest(query=query):
                get_user_projects.reset_mock()
                request = Request(self.factory.get("/api/v1/meta/projects/mine/", query))
                view = MetaViewSet()
                view.request = request

                response = view.list_projects_mine(request)

                self.assertEqual(response.data, [])
                get_user_projects.assert_called_once_with("alice", has_permission=expected)

    @patch("apps.log_search.views.meta_views.MetaHandler.get_user_projects")
    def test_invalid_permission_filter_is_rejected(self, get_user_projects):
        request = Request(self.factory.get("/api/v1/meta/projects/mine/", {"has_permission": "invalid"}))
        view = MetaViewSet()
        view.request = request

        with self.assertRaises(ValidationError):
            view.list_projects_mine(request)

        get_user_projects.assert_not_called()
