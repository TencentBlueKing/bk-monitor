"""日志接入列表接口的业务访问权限校验。"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam import ActionEnum
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.iam.handlers.resources import ResourceEnum
from apps.log_databus.views.log_access_views import LogAccessViewSet


@override_settings(IGNORE_IAM_PERMISSION=False, ESQUERY_WHITE_LIST=["bk_monitorv3"])
class LogAccessViewSetPermissionTests(SimpleTestCase):
    def test_list_routes_require_business_permission(self):
        permissions = LogAccessViewSet().get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], ViewBusinessPermission)

    def test_trusted_app_is_not_exempted(self):
        view = LogAccessViewSet()
        view.request = SimpleNamespace(
            query_params={},
            data={"space_uid": "bkcc__2", "enforce_permission": "true"},
            app=SimpleNamespace(bk_app_code="bk_monitorv3"),
        )

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], ViewBusinessPermission)

    @patch("apps.iam.handlers.drf.Permission")
    def test_business_permission_checks_request_space(self, permission_class):
        permission = ViewBusinessPermission()
        request = SimpleNamespace(data={"space_uid": "bkcc__2", "bk_biz_id": 2}, query_params={})
        resource = Mock()

        with patch.object(ResourceEnum.BUSINESS, "create_instance", return_value=resource) as create_instance:
            self.assertTrue(permission.has_permission(request, Mock()))

        create_instance.assert_called_once_with(2)
        permission_class.return_value.is_allowed.assert_called_once_with(
            action=ActionEnum.VIEW_BUSINESS,
            resources=[resource],
            raise_exception=True,
        )
