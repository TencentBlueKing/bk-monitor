from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.iam import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission, InstanceActionPermission
from apps.log_search.views.index_set_views import IndexSetViewSet


@override_settings(ESQUERY_WHITE_LIST=["bk_monitor"])
class IndexSetPermissionTests(SimpleTestCase):
    @staticmethod
    def build_view(action: str, enforce_permission: bool):
        view = IndexSetViewSet()
        view.action = action
        view.request = SimpleNamespace(
            query_params={},
            data={"enforce_permission": enforce_permission},
        )
        return view

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_keeps_legacy_bypass_without_enforcement(self, get_auth_info):
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}

        self.assertEqual(self.build_view("update", False).get_permissions(), [])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_can_enforce_create_permission(self, get_auth_info):
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}

        permissions = self.build_view("create", True).get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], BusinessActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.CREATE_INDICES])

    @patch("apps.log_search.views.index_set_views.Permission.get_auth_info")
    def test_white_list_can_enforce_update_permission(self, get_auth_info):
        get_auth_info.return_value = {"bk_app_code": "bk_monitor", "bk_username": "alice"}

        permissions = self.build_view("update", True).get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_INDICES])
