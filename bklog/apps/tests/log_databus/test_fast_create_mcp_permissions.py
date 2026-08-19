"""日志采集 Fast Create MCP 权限回归测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.iam import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission, InstanceActionPermission
from apps.log_databus.views.collector_views import CollectorViewSet


@override_settings(ESQUERY_WHITE_LIST=["bk_monitorv3"])
class FastCreateMCPPermissionTests(SimpleTestCase):
    @staticmethod
    def build_view(action, enforce_permission):
        view = CollectorViewSet()
        view.action = action
        view.request = SimpleNamespace(
            query_params={},
            data={"bk_biz_id": 2, "enforce_permission": enforce_permission},
        )
        return view

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_fast_create_enforces_create_collection_permission(self, _mock_get_auth_info):
        permissions = self.build_view("fast_create", True).get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], BusinessActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.CREATE_COLLECTION])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_whitelisted_app_keeps_legacy_bypass_without_enforcement(self, _mock_get_auth_info):
        self.assertEqual(self.build_view("fast_create", False).get_permissions(), [])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_enforced_detail_keeps_instance_permission(self, _mock_get_auth_info):
        permissions = self.build_view("retrieve", "true").get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.VIEW_COLLECTION])
