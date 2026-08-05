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

        permission.get_apply_data.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
            mode=AuthMode.V3.value,
        )

    def test_v4_denial_uses_injected_permission_application_provider(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        application_provider = Mock()
        application_provider.get_apply_data.return_value = (
            {"provider": "v4"},
            "https://iam-v4.example/apply",
        )
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=application_provider)

        with self.assertRaises(PermissionDeniedError):
            permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE, raise_exception=True)

        application_provider.get_apply_data.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_apply_data_entry_resolves_v4_provider_from_feature_toggle_mode(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        application_provider = Mock()
        application_provider.get_apply_data.return_value = (
            {"provider": "v4"},
            "https://iam-v4.example/apply",
        )
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=application_provider)

        result = permission.get_apply_data([ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        self.assertEqual(result, ({"provider": "v4"}, "https://iam-v4.example/apply"))
        application_provider.get_apply_data.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_v4_apply_without_provider_falls_back_to_v3(self):
        permission = self._make_permission()
        permission._get_v3_apply_data = Mock(return_value=({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.V4,
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))
        permission._get_v3_apply_data.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_union_apply_keeps_v3_fallback_until_composition_is_defined(self):
        permission = self._make_permission()
        permission._get_v3_apply_data = Mock(return_value=({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.UNION,
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))

    def test_union_mode_allows_when_v3_allows_and_v4_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.UNION
        self.iam_client.is_allowed.return_value = True
        permission = self._make_permission()

        self.assertTrue(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_v4_mode_denies_when_v4_provider_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()

        self.assertFalse(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_provider_error_observation_includes_reason(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()

        with patch("apps.iam.handlers.permission.logger.warning") as warning:
            self.assertFalse(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

        warning.assert_called_once_with(
            "[IAM Decision] mode=%s action=%s allowed=%s degraded=%s hit=%s errors=%s",
            AuthMode.V4.value,
            ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id,
            False,
            True,
            (),
            (("v4", "ProviderNotConfigured", "IAM v4 provider is not configured"),),
        )

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
        warning.assert_called_once_with(
            "[IAM Batch Decision] error_result_count=%s errors=%s",
            1,
            (("v4", "ProviderNotConfigured", "IAM v4 provider is not configured"),),
        )

    def test_creator_grant_calls_injected_v4_writer_and_keeps_v3_return_value(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        v4_writer = Mock()
        permission = self._make_permission()
        permission.get_v4_authorization_writer = Mock(return_value=v4_writer)
        resource = Resource("bk_log_search", "collection", "1", {"name": "collection-1"})

        result = permission.grant_creator_action(resource, creator="admin")

        application = {
            "system": "bk_log_search",
            "type": "collection",
            "id": "1",
            "name": "collection-1",
            "creator": "admin",
        }
        self.assertEqual(result, "v3-result")
        self.iam_client.grant_resource_creator_actions.assert_called_once_with(application)
        v4_writer.grant_resource_creator_actions.assert_called_once_with(application)

    def test_creator_grant_without_v4_writer_keeps_existing_v3_behavior(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        permission = self._make_permission()
        resource = Resource("bk_log_search", "collection", "1", {})

        self.assertEqual(permission.grant_creator_action(resource), "v3-result")
        self.iam_client.grant_resource_creator_actions.assert_called_once()

    def test_creator_grant_propagates_v4_writer_error_when_requested(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        v4_writer = Mock()
        v4_writer.grant_resource_creator_actions.side_effect = RuntimeError("v4 grant failed")
        permission = self._make_permission()
        permission.get_v4_authorization_writer = Mock(return_value=v4_writer)
        resource = Resource("bk_log_search", "collection", "1", {})

        with self.assertRaisesMessage(RuntimeError, "v4 grant failed"):
            permission.grant_creator_action(resource, raise_exception=True)

    @staticmethod
    def _make_permission() -> Permission:
        return Permission(username="admin", bk_tenant_id="tenant-1")
