from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.feature_toggle.handlers.toggle import Toggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthResult, AuthStatus, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import FeatureToggleModeProvider, InvalidIAMPermissionModeError, get_mode_provider


class FeatureToggleModeProviderTest(SimpleTestCase):
    def test_missing_toggle_defaults_to_v3(self):
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=None))

        self.assertEqual(provider.get_mode(), AuthMode.V3)

    def test_valid_modes(self):
        for mode_value, expected_mode in (
            ("v3", AuthMode.V3),
            ("v4", AuthMode.V4),
            ("union", AuthMode.UNION),
            ("V4", AuthMode.V4),
        ):
            with self.subTest(mode_value=mode_value):
                toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": mode_value})
                provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle))
                self.assertEqual(provider.get_mode(), expected_mode)

    def test_invalid_mode_rejects_auth(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "both"})
        logger = Mock()
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle), logger=logger)

        with self.assertRaises(InvalidIAMPermissionModeError):
            provider.get_mode()

        logger.error.assert_called_once()

    def test_disabled_toggle_rejects_auth(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="off", feature_config={"mode": "v3"})
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle))

        with self.assertRaises(InvalidIAMPermissionModeError):
            provider.get_mode()

    def test_debug_status_rejects_auth_instead_of_reading_mode(self):
        # IAM 鉴权模式不做业务级灰度，debug 状态没有实现白名单/黑名单语义，必须显式拒绝，
        # 不能被通用 FeatureToggle 语义当作已开启继续读取 feature_config.mode。
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="debug", feature_config={"mode": "v4"})
        logger = Mock()
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle), logger=logger)

        with self.assertRaises(InvalidIAMPermissionModeError):
            provider.get_mode()

        logger.error.assert_called_once()

    def test_unknown_status_rejects_auth_instead_of_defaulting_to_enabled(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="broken", feature_config={"mode": "v4"})
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle))

        with self.assertRaises(InvalidIAMPermissionModeError):
            provider.get_mode()

    def test_none_feature_config_defaults_to_v3(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config=None)
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle))

        self.assertEqual(provider.get_mode(), AuthMode.V3)

    def test_non_mapping_feature_config_rejects_auth_instead_of_attribute_error(self):
        # feature_config 是普通 JSONField，可能存成字符串/数组/数字；不能假设一定是字典，
        # 否则 feature_config.get(...) 会抛出未捕获的 AttributeError 而不是安全拒绝。
        logger = Mock()
        for invalid_feature_config in ("v4", ["v4"], 1):
            with self.subTest(feature_config=invalid_feature_config):
                toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config=invalid_feature_config)
                provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle), logger=logger)

                with self.assertRaises(InvalidIAMPermissionModeError):
                    provider.get_mode()

    def test_toggle_loader_error_falls_back_to_v3(self):
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=Mock(side_effect=RuntimeError("db unavailable")),
            logger=logger,
        )

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        logger.exception.assert_called_once_with("failed to load IAM permission mode toggle, fallback to v3")

    def test_mode_reads_toggle_for_each_request(self):
        toggle_loader = Mock(
            side_effect=(
                Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "v3"}),
                Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "union"}),
                Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "v4"}),
            )
        )
        provider = FeatureToggleModeProvider(toggle_loader=toggle_loader)

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        self.assertEqual(provider.get_mode(), AuthMode.UNION)
        self.assertEqual(provider.get_mode(), AuthMode.V4)
        self.assertEqual(toggle_loader.call_count, 3)
        toggle_loader.assert_called_with(IAM_PERMISSION_MODE)

    def test_default_provider_does_not_cache_toggle_values(self):
        get_mode_provider.cache_clear()
        self.addCleanup(get_mode_provider.cache_clear)

        provider = get_mode_provider()

        self.assertIsInstance(provider, FeatureToggleModeProvider)
        self.assertFalse(hasattr(provider, "_cache"))

    def test_non_string_mode_value_is_coerced(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": 4})
        provider = FeatureToggleModeProvider(toggle_loader=Mock(return_value=toggle))

        with self.assertRaises(InvalidIAMPermissionModeError):
            provider.get_mode()

    def test_empty_resource_group_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "resource group must not be empty"):
            BatchAuthRequest(
                subject=Subject(id="admin"),
                action_ids=("view_collection_v2",),
                resource_groups=((),),
            )


class AuthModeSafeCoerceTest(SimpleTestCase):
    def test_valid_string_is_converted(self):
        self.assertEqual(AuthMode.safe_coerce("v4"), AuthMode.V4)

    def test_existing_auth_mode_instance_passes_through(self):
        self.assertEqual(AuthMode.safe_coerce(AuthMode.UNION), AuthMode.UNION)

    def test_invalid_string_falls_back_to_v3_by_default(self):
        self.assertEqual(AuthMode.safe_coerce("bad"), AuthMode.V3)
        self.assertEqual(AuthMode.safe_coerce("off"), AuthMode.V3)

    def test_invalid_string_falls_back_to_custom_default(self):
        self.assertEqual(AuthMode.safe_coerce("bad", default=AuthMode.V4), AuthMode.V4)


class ModeRouterTest(SimpleTestCase):
    def setUp(self):
        self.request = AuthRequest(subject=Subject(id="admin"), action_id="search_log_v2")
        self.v3 = Mock(name="v3-provider")
        self.v3.name = "v3"
        self.v4 = Mock(name="v4-provider")
        self.v4.name = "v4"

    def test_v3_mode_only_calls_v3_provider(self):
        self.v3.is_allowed.return_value = AuthResult.allow("v3")
        router = self._make_router(AuthMode.V3)

        decision = router.is_allowed(self.request)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.mode, AuthMode.V3.value)
        self.assertEqual(decision.hit_provider_names, ("v3",))
        self.v3.is_allowed.assert_called_once_with(self.request)
        self.v4.is_allowed.assert_not_called()

    def test_v4_mode_only_calls_v4_provider(self):
        self.v4.is_allowed.return_value = AuthResult.deny("v4")
        router = self._make_router(AuthMode.V4)

        decision = router.is_allowed(self.request)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.mode, AuthMode.V4.value)
        self.v3.is_allowed.assert_not_called()
        self.v4.is_allowed.assert_called_once_with(self.request)

    def test_union_mode_combines_both_provider_results(self):
        self.v3.is_allowed.return_value = AuthResult.deny("v3")
        self.v4.is_allowed.return_value = AuthResult.allow("v4")
        router = self._make_router(AuthMode.UNION)

        decision = router.is_allowed(self.request)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.mode, AuthMode.UNION.value)
        self.assertEqual(decision.hit_provider_names, ("v4",))
        self.v3.is_allowed.assert_called_once_with(self.request)
        self.v4.is_allowed.assert_called_once_with(self.request)

    def test_union_mode_calls_providers_concurrently(self):
        import threading
        import time

        started = threading.Event()
        release = threading.Event()

        def v3_is_allowed(_request):
            started.set()
            release.wait(timeout=1)
            return AuthResult.deny("v3")

        def v4_is_allowed(_request):
            if not started.wait(timeout=1):
                return AuthResult.deny("v4")
            release.set()
            return AuthResult.allow("v4")

        self.v3.is_allowed.side_effect = v3_is_allowed
        self.v4.is_allowed.side_effect = v4_is_allowed
        router = self._make_router(AuthMode.UNION)

        started_at = time.monotonic()
        decision = router.is_allowed(self.request)
        elapsed = time.monotonic() - started_at

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.hit_provider_names, ("v4",))
        self.assertLess(elapsed, 0.5)

    def test_invalid_mode_rejects_auth(self):
        mode_provider = Mock(
            get_mode=Mock(side_effect=InvalidAuthModeError("bad", "invalid IAM permission mode configured: bad"))
        )
        router = ModeRouter(mode_provider=mode_provider, bundles=self._bundles())

        decision = router.is_allowed(self.request)

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.degraded)
        self.assertEqual(decision.mode, "bad")
        self.assertEqual(decision.provider_results[0].error_type, "InvalidPermissionMode")
        self.v3.is_allowed.assert_not_called()
        self.v4.is_allowed.assert_not_called()

    def test_invalid_mode_batch_rejects_all_items(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        mode_provider = Mock(
            get_mode=Mock(side_effect=InvalidAuthModeError("bad", "invalid IAM permission mode configured: bad"))
        )
        router = ModeRouter(mode_provider=mode_provider, bundles=self._bundles())

        result = router.batch_is_allowed(request)

        self.assertFalse(result.items[0].decision.allowed)
        self.assertEqual(result.items[0].decision.provider_results[0].error_type, "InvalidPermissionMode")

    def test_missing_v4_bundle_is_provider_not_configured(self):
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={AuthMode.V3: ProviderBundle(auth=self.v3)},
        )

        decision = router.is_allowed(self.request)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.provider_results[0].error_type, "ProviderNotConfigured")

    def test_missing_v4_provider_is_error_instead_of_implicit_v3_fallback(self):
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={
                AuthMode.V3: ProviderBundle(auth=self.v3),
                AuthMode.V4: ProviderBundle(auth=None),
            },
        )

        decision = router.is_allowed(self.request)

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.degraded)
        self.assertEqual(decision.provider_results[0].status, AuthStatus.ERROR)

    def test_union_batch_decision_preserves_old_resource_action_shape(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2", "manage_collection_v2"),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        self.v3.batch_is_allowed.return_value = BatchAuthResult(
            items=(
                BatchAuthResultItem("view_collection_v2", "1", AuthResult.allow("v3")),
                BatchAuthResultItem("manage_collection_v2", "1", AuthResult.deny("v3")),
            )
        )
        self.v4.batch_is_allowed.return_value = BatchAuthResult(
            items=(
                BatchAuthResultItem("view_collection_v2", "1", AuthResult.deny("v4")),
                BatchAuthResultItem("manage_collection_v2", "1", AuthResult.allow("v4")),
            )
        )
        router = self._make_router(AuthMode.UNION)

        result = router.batch_is_allowed(request)

        self.assertEqual(
            result.as_allowed_dict(),
            {"1": {"view_collection_v2": True, "manage_collection_v2": True}},
        )

    def test_missing_v4_batch_provider_is_safely_denied(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={
                AuthMode.V3: ProviderBundle(auth=self.v3),
                AuthMode.V4: ProviderBundle(auth=None),
            },
        )

        result = router.batch_is_allowed(request)

        self.assertFalse(result.items[0].decision.allowed)
        self.assertEqual(result.items[0].decision.provider_results[0].error_type, "ProviderNotConfigured")

    def test_incomplete_provider_batch_result_is_safely_denied(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        self.v3.batch_is_allowed.return_value = BatchAuthResult()
        router = self._make_router(AuthMode.V3)

        result = router.batch_is_allowed(request)

        self.assertFalse(result.items[0].decision.allowed)
        self.assertEqual(result.items[0].decision.provider_results[0].error_type, "IncompleteBatchResult")

    def test_batch_uses_one_mode_for_all_resources(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=(
                (ResourceInstance(type="collection", id="1", attributes={"bk_biz_id": "10"}),),
                (ResourceInstance(type="collection", id="2", attributes={"bk_biz_id": "10"}),),
            ),
        )
        mode_provider = Mock(get_mode=Mock(return_value=AuthMode.UNION))
        self.v3.batch_is_allowed.return_value = BatchAuthResult(
            items=(
                BatchAuthResultItem("view_collection_v2", "1", AuthResult.allow("v3")),
                BatchAuthResultItem("view_collection_v2", "2", AuthResult.deny("v3")),
            )
        )
        self.v4.batch_is_allowed.return_value = BatchAuthResult(
            items=(
                BatchAuthResultItem("view_collection_v2", "1", AuthResult.deny("v4")),
                BatchAuthResultItem("view_collection_v2", "2", AuthResult.allow("v4")),
            )
        )
        router = ModeRouter(mode_provider=mode_provider, bundles=self._bundles())

        result = router.batch_is_allowed(request)

        self.assertEqual(
            result.as_allowed_dict(), {"1": {"view_collection_v2": True}, "2": {"view_collection_v2": True}}
        )
        self.assertEqual(tuple(item.decision.mode for item in result.items), ("union", "union"))
        mode_provider.get_mode.assert_called_once_with(
            (
                request.resource_groups[0][0],
                request.resource_groups[1][0],
            )
        )
        self.v3.batch_is_allowed.assert_called_once_with(request)
        self.v4.batch_is_allowed.assert_called_once_with(request)

    def _make_router(self, mode: AuthMode) -> ModeRouter:
        return ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=mode)),
            bundles=self._bundles(),
        )

    def _bundles(self) -> dict[AuthMode, ProviderBundle]:
        return {
            AuthMode.V3: ProviderBundle(auth=self.v3),
            AuthMode.V4: ProviderBundle(auth=self.v4),
        }
