"""日志采集 MCP 通过白名单应用调用时的权限回归测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.iam.handlers.drf import InstanceActionPermission, ViewBusinessPermission
from apps.log_databus.views.collector_views import CollectorViewSet


@override_settings(ESQUERY_WHITE_LIST=["bk_monitorv3"])
class CollectorMCPPermissionTests(SimpleTestCase):
    @staticmethod
    def build_view(action, enforce_permission):
        view = CollectorViewSet()
        view.action = action
        view.request = SimpleNamespace(
            query_params={"enforce_permission": enforce_permission},
        )
        return view

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_whitelisted_app_can_explicitly_enable_instance_permission(self, _mock_get_auth_info):
        permissions = self.build_view("retrieve", "true").get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_whitelisted_app_keeps_legacy_bypass_by_default(self, _mock_get_auth_info):
        self.assertEqual(self.build_view("retrieve", "").get_permissions(), [])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "bk_monitorv3"},
    )
    def test_enforced_list_uses_business_permission(self, _mock_get_auth_info):
        permissions = self.build_view("list", "true").get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], ViewBusinessPermission)
