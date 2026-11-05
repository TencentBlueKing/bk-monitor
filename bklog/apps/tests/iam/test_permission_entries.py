from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import resolve

from apps.iam.handlers.permission import Permission
from apps.iam.views.meta import MetaViewSet
from iam_engine.core.config import AuthMode
from iam_engine.core.exceptions import InvalidAuthModeError

V3_SAAS_HOST = "https://iam-v3.example.test/saas"
V4_SAAS_HOST = "https://iam-v4.example.test"
V4_APPLY_URL = f"{V4_SAAS_HOST}/permission/apply?cache_id=example"


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="default",
    BK_IAM_SAAS_HOST=V3_SAAS_HOST,
    BK_IAM_V4_SAAS_HOST=V4_SAAS_HOST,
)
class PermissionEntryUrlTest(SimpleTestCase):
    def setUp(self):
        self.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
        self.v4_provider = Mock()
        self.v4_provider.get_permission_center_url.return_value = V4_SAAS_HOST
        self.v4_provider.get_apply_entry_url.return_value = V4_APPLY_URL

        patchers = [
            patch.object(Permission, "get_iam_client", return_value=Mock()),
            patch("apps.iam.handlers.permission.get_mode_provider", return_value=self.mode_provider),
            patch.object(Permission, "get_v4_provider", return_value=self.v4_provider),
            patch.object(Permission, "get_v4_authorization_writer", return_value=None),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _make_permission(self) -> Permission:
        return Permission(username="admin", bk_tenant_id="tenant-1")

    def test_v3_mode_returns_v3_urls(self):
        permission = self._make_permission()

        self.assertEqual(permission.get_permission_center_url(), V3_SAAS_HOST)
        self.assertEqual(permission.get_apply_entry_url(), f"{V3_SAAS_HOST}/apply-join-user-group")
        self.v4_provider.get_apply_entry_url.assert_not_called()

    def test_v4_mode_returns_v4_urls(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()

        self.assertEqual(permission.get_permission_center_url(), V4_SAAS_HOST)
        self.assertEqual(permission.get_apply_entry_url(), V4_APPLY_URL)

    def test_union_mode_uses_current_v4(self):
        self.mode_provider.get_mode.return_value = AuthMode.UNION
        permission = self._make_permission()

        self.assertEqual(permission.get_permission_center_url(), V4_SAAS_HOST)
        self.assertEqual(permission.get_apply_entry_url(), V4_APPLY_URL)

    def test_v4_mode_falls_back_to_v3_when_center_url_missing(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        self.v4_provider.get_permission_center_url.return_value = ""
        permission = self._make_permission()

        self.assertEqual(permission.get_permission_center_url(), V3_SAAS_HOST)

    def test_v4_apply_entry_failure_falls_back_to_v3(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        self.v4_provider.get_apply_entry_url.side_effect = RuntimeError("iam unavailable")
        permission = self._make_permission()

        self.assertEqual(permission.get_apply_entry_url(), f"{V3_SAAS_HOST}/apply-join-user-group")

    def test_invalid_mode_falls_back_to_v3(self):
        self.mode_provider.get_mode.side_effect = InvalidAuthModeError("bad-mode", "unsupported mode")
        permission = self._make_permission()

        self.assertEqual(permission.get_permission_center_url(), V3_SAAS_HOST)
        self.assertEqual(permission.get_apply_entry_url(), f"{V3_SAAS_HOST}/apply-join-user-group")

    def test_meta_entry_routes_are_registered(self):
        paths = (
            "/api/v1/iam/meta/get_permission_center_url/",
            "/api/v1/iam/meta/get_apply_entry_url/",
        )
        for path in paths:
            self.assertIs(resolve(path).func.cls, MetaViewSet)
