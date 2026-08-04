from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import IAMPermission


@override_settings(IGNORE_IAM_PERMISSION=False)
class IAMPermissionCompatibilityTest(SimpleTestCase):
    @patch("apps.iam.handlers.drf.Permission")
    def test_drf_permission_keeps_using_permission_facade(self, permission_class):
        permission_client = permission_class.return_value
        drf_permission = IAMPermission(actions=[ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        result = drf_permission.has_permission(Mock(), Mock())

        self.assertTrue(result)
        permission_client.is_allowed.assert_called_once_with(
            action=ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE,
            resources=[],
            raise_exception=True,
        )

    @override_settings(IGNORE_IAM_PERMISSION=True)
    @patch("apps.iam.handlers.drf.Permission")
    def test_global_ignore_switch_still_short_circuits_facade(self, permission_class):
        drf_permission = IAMPermission(actions=[ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        self.assertTrue(drf_permission.has_permission(Mock(), Mock()))
        permission_class.assert_not_called()
