from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from iam import Resource
from iam.exceptions import AuthAPIError

from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.config import AuthMode


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="default",
    DEMO_BIZ_ID=0,
    DEMO_BIZ_EDIT_ENABLED=False,
)
class PermissionFacadeTest(SimpleTestCase):
    def setUp(self):
        self.iam_client = Mock()
        self.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
        self.client_patcher = patch.object(Permission, "get_iam_client", return_value=self.iam_client)
        self.mode_patcher = patch("apps.iam.handlers.permission.get_mode_provider", return_value=self.mode_provider)
        self.client_patcher.start()
        self.mode_patcher.start()
        self.addCleanup(self.client_patcher.stop)
        self.addCleanup(self.mode_patcher.stop)

    def test_v3_mode_keeps_boolean_allow_result(self):
        self.iam_client.is_allowed.return_value = True
        permission = self._make_permission()

        self.assertTrue(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_v3_auth_api_error_is_safely_denied(self):
        self.iam_client.is_allowed.side_effect = AuthAPIError("request timeout")
        permission = self._make_permission()

        self.assertFalse(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_raise_exception_keeps_existing_permission_denied_contract(self):
        self.iam_client.is_allowed.return_value = False
        permission = self._make_permission()
        permission.get_apply_data = Mock(return_value=({"actions": []}, "https://iam.example/apply"))

        with self.assertRaises(PermissionDeniedError):
            permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE, raise_exception=True)

    def test_union_mode_allows_when_v3_allows_and_v4_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.UNION
        self.iam_client.is_allowed.return_value = True
        permission = self._make_permission()

        self.assertTrue(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_v4_mode_denies_when_v4_provider_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()

        self.assertFalse(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_batch_result_keeps_existing_nested_dictionary_shape(self):
        self.iam_client.batch_resource_multi_actions_allowed.return_value = {
            "1": {
                ActionEnum.VIEW_COLLECTION.id: True,
                ActionEnum.MANAGE_COLLECTION.id: False,
            }
        }
        permission = self._make_permission()
        resources = [[Resource("bk_log_search", "collection", "1", {})]]

        result = permission.batch_is_allowed(
            [ActionEnum.VIEW_COLLECTION, ActionEnum.MANAGE_COLLECTION],
            resources,
        )

        self.assertEqual(
            result,
            {
                "1": {
                    ActionEnum.VIEW_COLLECTION.id: True,
                    ActionEnum.MANAGE_COLLECTION.id: False,
                }
            },
        )

    def test_batch_provider_error_is_safely_denied_and_recorded(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()
        resources = [[Resource("bk_log_search", "collection", "1", {})]]

        with patch("apps.iam.handlers.permission.logger.warning") as warning:
            result = permission.batch_is_allowed([ActionEnum.VIEW_COLLECTION], resources)

        self.assertEqual(result, {"1": {ActionEnum.VIEW_COLLECTION.id: False}})
        warning.assert_called_once_with("[IAM Batch Decision] error_result_count=%s", 1)

    @staticmethod
    def _make_permission() -> Permission:
        return Permission(username="admin", bk_tenant_id="tenant-1")
