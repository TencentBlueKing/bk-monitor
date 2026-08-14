from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from iam import Resource
from iam.exceptions import AuthAPIError

from apps.iam.exceptions import GetSystemInfoError, PermissionDeniedError
from apps.iam.handlers.actions import ActionEnum, get_action_by_id
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import ResourceInstance as EngineResourceInstance
from apps.iam.iam_engine.core.types import AuthResult
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="default",
    DEMO_BIZ_ID=0,
    DEMO_BIZ_EDIT_ENABLED=False,
)
class PermissionFacadeTest(TestCase):
    def setUp(self):
        self.iam_client = Mock()
        self.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
        self.client_patcher = patch.object(Permission, "get_iam_client", return_value=self.iam_client)
        self.mode_patcher = patch("apps.iam.handlers.permission.get_mode_provider", return_value=self.mode_provider)
        self.v4_provider_patcher = patch.object(Permission, "get_v4_provider", return_value=None)
        self.v4_writer_patcher = patch.object(Permission, "get_v4_authorization_writer", return_value=None)
        self.client_patcher.start()
        self.mode_patcher.start()
        self.v4_provider_patcher.start()
        self.v4_writer_patcher.start()
        self.addCleanup(self.client_patcher.stop)
        self.addCleanup(self.mode_patcher.stop)
        self.addCleanup(self.v4_provider_patcher.stop)
        self.addCleanup(self.v4_writer_patcher.stop)

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
        v4_provider = Mock()
        v4_provider.is_allowed.return_value = AuthResult.deny("v4")
        application_provider = Mock()
        application_provider.get_apply_data.return_value = (
            {"provider": "v4"},
            "https://iam-v4.example/apply",
        )
        permission = self._make_permission()
        permission.get_v4_provider = Mock(return_value=v4_provider)
        permission.get_v4_permission_application_provider = Mock(return_value=application_provider)
        permission._mode_router = None

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

    def test_v4_apply_converts_v3_sdk_resources_at_permission_boundary(self):
        application_provider = Mock()
        application_provider.get_apply_data.return_value = (
            {"provider": "v4"},
            "https://iam-v4.example/apply",
        )
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=application_provider)
        resource = Resource(
            "bk_log_search",
            "collection",
            "1",
            {"name": "collection-1", "_bk_iam_path_": "/space,10/"},
        )

        permission.get_apply_data(
            [ActionEnum.VIEW_COLLECTION],
            [resource],
            mode=AuthMode.V4,
        )

        application_provider.get_apply_data.assert_called_once_with(
            [ActionEnum.VIEW_COLLECTION],
            [
                EngineResourceInstance(
                    system="bk_log_search",
                    type="collection",
                    id="1",
                    name="collection-1",
                    attributes={"name": "collection-1", "_bk_iam_path_": "/space,10/"},
                )
            ],
        )

    def test_v4_apply_without_provider_falls_back_to_v3(self):
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=None)
        v3_apply = self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.V4,
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))
        v3_apply.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_union_apply_uses_v4_provider_when_injected(self):
        application_provider = Mock()
        application_provider.get_apply_data.return_value = (
            {"provider": "v4"},
            "https://iam-v4.example/apply",
        )
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=application_provider)

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.UNION,
        )

        self.assertEqual(result, ({"provider": "v4"}, "https://iam-v4.example/apply"))
        application_provider.get_apply_data.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_union_apply_falls_back_to_v3_without_v4_provider(self):
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=None)
        self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.UNION,
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))

    def test_invalid_auth_mode_falls_back_to_v3_apply_instead_of_raising_value_error(self):
        # 非法模式（例如 toggle status=off/bad）会让 decision.mode 携带原始非法字符串；
        # get_apply_data 必须安全回退到 V3 申请，而不是把非法字符串传给 AuthMode() 抛出 ValueError，
        # 否则 DRF 默认 raise_exception=True 的入口会返回 500 而不是约定的 PermissionDeniedError。
        self.mode_provider.get_mode.side_effect = InvalidAuthModeError(
            "bad", "invalid IAM permission mode configured: bad"
        )
        permission = self._make_permission()
        v3_apply = self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        with self.assertRaises(PermissionDeniedError):
            permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE, raise_exception=True)

        v3_apply.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_invalid_auth_mode_apply_data_entry_also_falls_back_to_v3(self):
        permission = self._make_permission()
        self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode="off",
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))

    def test_direct_apply_call_without_mode_falls_back_to_v3_when_mode_provider_is_invalid(self):
        # 直接调用 get_apply_data() 不传 mode 是生产代码的真实入口（例如 IAM 申请数据接口、
        # 场景检索无权限处理），不能只在 mode 显式传入时才安全兜底。
        self.mode_provider.get_mode.side_effect = InvalidAuthModeError(
            "bad", "invalid IAM permission mode configured: bad"
        )
        permission = self._make_permission()
        v3_apply = self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data([ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE])

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))
        v3_apply.assert_called_once_with(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [],
        )

    def test_union_apply_falls_back_to_v3_when_v4_provider_raises(self):
        v4_provider = Mock()
        v4_provider.get_apply_data.side_effect = RuntimeError("v4 apply unavailable")
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=v4_provider)
        self._stub_v3_apply(permission, ({"provider": "v3"}, "https://iam-v3.example/apply"))

        result = permission.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            mode=AuthMode.UNION,
        )

        self.assertEqual(result, ({"provider": "v3"}, "https://iam-v3.example/apply"))
        v4_provider.get_apply_data.assert_called_once()

    def test_pure_v4_apply_failure_logs_error_and_returns_degraded_data_instead_of_raising(self):
        # 纯 V4 模式最终不再保留 V3 回退；申请数据生成失败时只记录错误并返回退化数据，
        # 不能让异常从 get_apply_data 冒出去，否则 is_allowed(raise_exception=True) 会变成 500
        # 而不是约定的 PermissionDeniedError。
        v4_provider = Mock()
        v4_provider.get_apply_data.side_effect = RuntimeError("v4 apply unavailable")
        permission = self._make_permission()
        permission.get_v4_permission_application_provider = Mock(return_value=v4_provider)
        v3_apply = self._stub_v3_apply(permission)

        with patch("apps.iam.handlers.permission.logger.error") as error_log:
            result = permission.get_apply_data(
                [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
                mode=AuthMode.V4,
            )

        self.assertEqual(result, ({}, settings.BK_IAM_SAAS_HOST))
        v4_provider.get_apply_data.assert_called_once()
        v3_apply.assert_not_called()
        error_log.assert_called_once()

    def test_v3_apply_error_is_not_hidden_by_v4_degradation_logic(self):
        permission = self._make_permission()
        self._stub_v3_apply(permission, side_effect=RuntimeError("v3 apply unavailable"))

        with self.assertRaisesMessage(RuntimeError, "v3 apply unavailable"):
            permission.get_apply_data(
                [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
                mode=AuthMode.V3,
            )

    def test_union_mode_allows_when_v3_allows_and_v4_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.UNION
        self.iam_client.is_allowed.return_value = True
        permission = self._make_permission()

        self.assertTrue(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_v4_mode_denies_when_v4_provider_is_not_configured(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        permission = self._make_permission()
        permission.get_v4_provider = Mock(return_value=None)
        permission._mode_router = None

        self.assertFalse(permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

    def test_provider_error_observation_includes_reason(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        v4_provider = Mock()
        v4_provider.is_allowed.return_value = AuthResult.error(
            "v4",
            reason="IAM v4 provider is not configured",
            error_type="ProviderNotConfigured",
        )
        permission = self._make_permission()
        permission.get_v4_provider = Mock(return_value=v4_provider)
        permission._mode_router = None

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
        permission.get_v4_provider = Mock(return_value=None)
        permission._mode_router = None
        resources = [[Resource("bk_log_search", "collection", "1", {})]]

        with patch("apps.iam.handlers.permission.logger.warning") as warning:
            result = permission.batch_is_allowed([ActionEnum.VIEW_COLLECTION], resources)

        self.assertEqual(result, {"1": {ActionEnum.VIEW_COLLECTION.id: False}})
        warning.assert_called_once_with(
            "[IAM Batch Decision] error_result_count=%s errors=%s",
            1,
            (("v4", "ProviderNotConfigured", "IAM v4 provider is not configured"),),
        )

    def test_creator_grant_keeps_v3_return_value_and_grants_v4_synchronously(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        prepared = PreparedAuthorizationGrant(
            payload=[{"role_id": "space_operator"}],
            role_id="space_operator",
            expired_at=1893456000,
        )
        v4_writer = Mock()
        v4_writer.prepare_resource_creator_actions.return_value = prepared
        permission = self._make_permission()
        permission.get_v4_authorization_writer = Mock(return_value=v4_writer)
        resource = Resource("bk_log_search", "collection", "1", {"name": "collection-1"})

        with patch("apps.iam.tasks.grant.grant_v4_creator_action.apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
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
        v4_writer.prepare_resource_creator_actions.assert_called_once_with(application)
        # 首次授权同步完成，不进重试队列。
        v4_writer.grant_prepared.assert_called_once_with(prepared)
        apply_async.assert_not_called()

    def test_creator_grant_falls_back_to_the_retry_task_when_v4_sync_grant_fails(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        v4_writer = Mock()
        v4_writer.prepare_resource_creator_actions.return_value = PreparedAuthorizationGrant(
            payload=[{"role_id": "space_operator"}],
            role_id="space_operator",
            expired_at=1893456000,
        )
        v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")
        permission = self._make_permission()
        permission.get_v4_authorization_writer = Mock(return_value=v4_writer)
        resource = Resource("bk_log_search", "collection", "1", {"name": "collection-1"})

        with patch("apps.iam.tasks.grant.grant_v4_creator_action.apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                result = permission.grant_creator_action(resource, creator="admin")

        # V4 同步失败不改变 V3 返回值，回落任务原样重放冻结请求。
        self.assertEqual(result, "v3-result")
        apply_async.assert_called_once_with(
            kwargs={
                "tenant_id": "tenant-1",
                "operator": "admin",
                "payload": [{"role_id": "space_operator"}],
                "role_id": "space_operator",
                "expired_at": 1893456000,
                "resource_meta": {
                    "subject_id": "admin",
                    "resource_system": "bk_log_search",
                    "resource_type": "collection",
                    "resource_id": "1",
                },
            }
        )

    def test_creator_grant_without_v4_writer_keeps_existing_v3_behavior(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        permission = self._make_permission()
        resource = Resource("bk_log_search", "collection", "1", {})

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(permission.grant_creator_action(resource), "v3-result")

        self.iam_client.grant_resource_creator_actions.assert_called_once()

    def test_creator_grant_propagates_v4_preparation_error_when_requested(self):
        self.iam_client.grant_resource_creator_actions.return_value = "v3-result"
        v4_writer = Mock()
        v4_writer.prepare_resource_creator_actions.side_effect = RuntimeError("v4 prepare failed")
        permission = self._make_permission()
        permission.get_v4_authorization_writer = Mock(return_value=v4_writer)
        resource = Resource("bk_log_search", "collection", "1", {})

        with patch("apps.iam.tasks.grant.grant_v4_creator_action.apply_async") as apply_async:
            with self.assertRaisesMessage(RuntimeError, "v4 prepare failed"):
                with self.captureOnCommitCallbacks(execute=True):
                    permission.grant_creator_action(resource, raise_exception=True)

        apply_async.assert_not_called()

    @staticmethod
    def _make_permission() -> Permission:
        return Permission(username="admin", bk_tenant_id="tenant-1")

    @staticmethod
    def _stub_v3_apply(permission: Permission, return_value=None, *, side_effect=None) -> Mock:
        """替换 V3 Provider 的申请数据能力，返回被打桩的 get_apply_data。"""
        provider = Mock()
        provider.get_apply_data = Mock(return_value=return_value, side_effect=side_effect)
        permission._v3_provider = provider
        return provider.get_apply_data


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_APP_TENANT_ID="default")
class PermissionDelegationTest(SimpleTestCase):
    """Permission 上仍对外暴露、但实现已下沉到 backends/v3 的委托壳。"""

    def setUp(self):
        self.iam_client = Mock()
        patcher = patch.object(Permission, "get_iam_client", return_value=self.iam_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.permission = Permission(username="admin", bk_tenant_id="tenant-1")

    def test_get_apply_url_delegates_to_the_v3_provider(self):
        provider = Mock()
        provider.get_apply_url.return_value = "https://iam.example/apply"
        self.permission._v3_provider = provider
        resources = [Resource("bk_log_search", "collection", "28", {})]

        url = self.permission.get_apply_url(["view_collection_v2"], resources, "bk_log_search")

        self.assertEqual(url, "https://iam.example/apply")
        provider.get_apply_url.assert_called_once_with(["view_collection_v2"], resources, "bk_log_search")

    def test_get_system_info_delegates_to_the_v3_meta_query(self):
        self.iam_client._client.query.return_value = (True, "ok", {"actions": []})

        self.assertEqual(self.permission.get_system_info(), {"actions": []})
        self.iam_client._client.query.assert_called_once_with("bk_log_search")

    def test_get_system_info_raises_when_iam_rejects_the_query(self):
        self.iam_client._client.query.return_value = (False, "system not registered", None)

        with self.assertRaises(GetSystemInfoError):
            self.permission.get_system_info()


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_APP_TENANT_ID="default")
class V4ProviderConstructionTest(SimpleTestCase):
    @patch("apps.iam.handlers.permission.V4PermissionProvider.from_settings")
    @patch.object(Permission, "get_iam_client", return_value=Mock())
    def test_v4_provider_is_built_lazily_once_with_platform_action_resolver(self, _, from_settings):
        provider = Mock()
        from_settings.return_value = provider
        permission = Permission(username="admin", bk_tenant_id="tenant-1")

        self.assertIs(permission.get_v4_provider(), provider)
        self.assertIs(permission.get_v4_provider(), provider)

        from_settings.assert_called_once_with(
            username="admin",
            bk_tenant_id="tenant-1",
            action_resolver=get_action_by_id,
        )

    @patch("apps.iam.handlers.permission.get_request", return_value=None)
    @patch("apps.iam.handlers.permission.get_local_username", return_value="local-user")
    @patch.object(Permission, "get_iam_client", return_value=Mock())
    def test_username_without_explicit_tenant_keeps_legacy_background_resolution(self, _, __, ___):
        permission = Permission(username="creator")

        self.assertEqual(permission.username, "local-user")
        self.assertEqual(permission.bk_tenant_id, "default")

    @override_settings(BK_IAM_V4_APIGATEWAY_URL="")
    @patch("apps.iam.handlers.permission.V4AuthorizationWriter.from_settings")
    @patch.object(Permission, "get_iam_client", return_value=Mock())
    def test_v4_writer_is_not_registered_when_gateway_is_unconfigured(self, _, from_settings):
        permission = Permission(username="admin", bk_tenant_id="tenant-1")

        self.assertIsNone(permission.get_v4_authorization_writer())
        from_settings.assert_not_called()

    @override_settings(BK_IAM_V4_APIGATEWAY_URL="https://iam.example/")
    @patch("apps.iam.handlers.permission.V4AuthorizationWriter.from_settings")
    @patch.object(Permission, "get_iam_client", return_value=Mock())
    def test_v4_writer_is_built_lazily_once_when_gateway_is_configured(self, _, from_settings):
        writer = Mock()
        from_settings.return_value = writer
        permission = Permission(username="admin", bk_tenant_id="tenant-1")

        self.assertIs(permission.get_v4_authorization_writer(), writer)
        self.assertIs(permission.get_v4_authorization_writer(), writer)
        from_settings.assert_called_once_with(username="admin", bk_tenant_id="tenant-1")
