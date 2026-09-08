from unittest.mock import Mock

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.feature_toggle.handlers.toggle import Toggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from apps.iam.apps import IamConfig
from apps.iam.iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import (
    AuthResult,
    AuthStatus,
    AuthorizedResourceScope,
    BatchAuthResult,
    BatchAuthResultItem,
)
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import (
    FeatureToggleModeProvider,
    InvalidIAMPermissionModeError,
    get_mode_provider,
    validate_configured_permission_mode,
)


@override_settings(BK_IAM_PERMISSION_MODE="")
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
        logger.exception.assert_called_once_with("failed to load IAM permission mode toggle, fallback to %s", "v3")

    def test_injected_stack_fallback_uses_legacy(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config=None)
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=Mock(
                side_effect=(
                    None,
                    RuntimeError("db unavailable"),
                    toggle,
                )
            ),
            logger=logger,
            stack=stack,
        )

        self.assertEqual(provider.get_mode(), AuthMode.V4)
        self.assertEqual(provider.get_mode(), AuthMode.V4)
        self.assertEqual(provider.get_mode(), AuthMode.V4)
        logger.exception.assert_called_once_with("failed to load IAM permission mode toggle, fallback to %s", "v4")

    def test_injected_stack_still_accepts_both_protocol_modes(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)
        for mode_value, expected_mode in (
            ("v3", AuthMode.V3),
            ("v4", AuthMode.V4),
            ("union", AuthMode.UNION),
        ):
            with self.subTest(mode_value=mode_value):
                toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": mode_value})
                provider = FeatureToggleModeProvider(
                    toggle_loader=Mock(return_value=toggle),
                    stack=stack,
                )
                self.assertEqual(provider.get_mode(), expected_mode)

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

    def test_env_mode_wins_over_toggle_without_reading_toggle(self):
        toggle_loader = Mock(return_value=Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "v3"}))
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=toggle_loader,
            logger=logger,
            env_loader=lambda: "v4",
        )

        self.assertEqual(provider.get_mode(), AuthMode.V4)
        toggle_loader.assert_not_called()
        logger.warning.assert_called_once_with(
            "IAM permission mode uses BKAPP_IAM_PERMISSION_MODE=%s; Feature Toggle %s is ignored",
            "v4",
            IAM_PERMISSION_MODE,
        )

    def test_env_mode_accepts_valid_values(self):
        for mode_value, expected_mode in (
            ("v3", AuthMode.V3),
            ("v4", AuthMode.V4),
            ("union", AuthMode.UNION),
            ("V4", AuthMode.V4),
            ("  Union  ", AuthMode.UNION),
        ):
            with self.subTest(mode_value=mode_value):
                toggle_loader = Mock()
                provider = FeatureToggleModeProvider(
                    toggle_loader=toggle_loader,
                    env_loader=lambda value=mode_value: value,
                )
                self.assertEqual(provider.get_mode(), expected_mode)
                toggle_loader.assert_not_called()

    def test_non_string_env_mode_value_is_coerced(self):
        # 与 Toggle 路径的 test_non_string_mode_value_is_coerced 对称：自定义 env_loader
        # 可能返回非 str；必须先 str() 再校验，非法值 fail-closed 且不读 Toggle。
        toggle_loader = Mock()
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=toggle_loader,
            logger=logger,
            env_loader=lambda: 4,
        )

        with self.assertRaises(InvalidIAMPermissionModeError) as context:
            provider.get_mode()

        self.assertEqual(context.exception.mode_value, "4")
        toggle_loader.assert_not_called()
        logger.error.assert_called_once()
        logger.warning.assert_not_called()

    def test_invalid_env_mode_rejects_without_reading_toggle(self):
        toggle_loader = Mock(return_value=Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "v3"}))
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=toggle_loader,
            logger=logger,
            env_loader=lambda: "both",
        )

        with self.assertRaises(InvalidIAMPermissionModeError) as context:
            provider.get_mode()

        self.assertEqual(context.exception.mode_value, "both")
        toggle_loader.assert_not_called()
        logger.error.assert_called_once()
        logger.warning.assert_not_called()

    def test_blank_env_falls_through_to_toggle(self):
        toggle = Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "union"})
        toggle_loader = Mock(return_value=toggle)
        for env_value in ("", "   ", None):
            with self.subTest(env_value=env_value):
                provider = FeatureToggleModeProvider(
                    toggle_loader=toggle_loader,
                    env_loader=lambda value=env_value: value,
                )
                self.assertEqual(provider.get_mode(), AuthMode.UNION)
        self.assertEqual(toggle_loader.call_count, 3)

    def test_env_override_warning_is_logged_once_per_provider(self):
        logger = Mock()
        provider = FeatureToggleModeProvider(
            toggle_loader=Mock(),
            logger=logger,
            env_loader=lambda: "v4",
        )

        self.assertEqual(provider.get_mode(), AuthMode.V4)
        self.assertEqual(provider.get_mode(), AuthMode.V4)
        logger.warning.assert_called_once()

    @override_settings(BK_IAM_PERMISSION_MODE="union")
    def test_django_settings_env_wins_without_reading_toggle(self):
        toggle_loader = Mock(return_value=Toggle(name=IAM_PERMISSION_MODE, status="on", feature_config={"mode": "v3"}))
        provider = FeatureToggleModeProvider(toggle_loader=toggle_loader)

        self.assertEqual(provider.get_mode(), AuthMode.UNION)
        toggle_loader.assert_not_called()

    def test_empty_resource_group_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "resource group must not be empty"):
            BatchAuthRequest(
                subject=Subject(id="admin"),
                action_ids=("view_collection_v2",),
                resource_groups=((),),
            )


class ConfiguredPermissionModeValidationTest(SimpleTestCase):
    def test_blank_setting_is_allowed(self):
        for mode_value in ("", "   ", None):
            with self.subTest(mode_value=mode_value):
                validate_configured_permission_mode(mode_value)

    def test_valid_modes_are_allowed(self):
        for mode_value in ("v3", "v4", "union", "V4", "  Union  "):
            with self.subTest(mode_value=mode_value):
                validate_configured_permission_mode(mode_value)

    def test_invalid_mode_raises_improperly_configured(self):
        with self.assertRaises(ImproperlyConfigured) as context:
            validate_configured_permission_mode("iam_v4")

        self.assertIn("BKAPP_IAM_PERMISSION_MODE='iam_v4'", str(context.exception))
        self.assertIn("v3", str(context.exception))
        self.assertIn("v4", str(context.exception))
        self.assertIn("union", str(context.exception))

    def test_uses_injected_stack_valid_mode_values(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)

        validate_configured_permission_mode("v3", stack=stack)
        with self.assertRaises(ImproperlyConfigured):
            validate_configured_permission_mode("both", stack=stack)

    @override_settings(BK_IAM_PERMISSION_MODE="both")
    def test_reads_django_settings_when_value_omitted(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_configured_permission_mode()

    def test_iam_app_config_is_registered(self):
        config = apps.get_app_config("iam")

        self.assertIsInstance(config, IamConfig)
        self.assertEqual(config.name, "apps.iam")

    @override_settings(BK_IAM_PERMISSION_MODE="iam_v4")
    def test_ready_raises_improperly_configured_for_invalid_setting(self):
        with self.assertRaises(ImproperlyConfigured):
            apps.get_app_config("iam").ready()

    @override_settings(BK_IAM_PERMISSION_MODE="v3")
    def test_ready_accepts_valid_setting(self):
        apps.get_app_config("iam").ready()


class DualStackSpecTest(SimpleTestCase):
    def test_default_topology_is_v3_legacy_and_v4_current(self):
        self.assertEqual(DEFAULT_DUAL_STACK.legacy, AuthMode.V3)
        self.assertEqual(DEFAULT_DUAL_STACK.current, AuthMode.V4)
        self.assertEqual(DEFAULT_DUAL_STACK.modes_for(AuthMode.UNION), (AuthMode.V3, AuthMode.V4))
        self.assertEqual(DEFAULT_DUAL_STACK.application_candidates(AuthMode.UNION), (AuthMode.V4, AuthMode.V3))
        self.assertEqual(DEFAULT_DUAL_STACK.application_candidates(AuthMode.V4), (AuthMode.V4, AuthMode.V3))
        self.assertEqual(DEFAULT_DUAL_STACK.application_candidates(AuthMode.V3), (AuthMode.V3,))
        self.assertEqual(DEFAULT_DUAL_STACK.fallback_mode, AuthMode.V3)
        self.assertEqual(
            DEFAULT_DUAL_STACK.valid_mode_values,
            frozenset({AuthMode.V3.value, AuthMode.V4.value, AuthMode.UNION.value}),
        )

    def test_fallback_and_valid_modes_follow_injected_topology(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)

        self.assertEqual(stack.fallback_mode, AuthMode.V4)
        self.assertEqual(
            stack.valid_mode_values,
            frozenset({AuthMode.V3.value, AuthMode.V4.value, AuthMode.UNION.value}),
        )

    def test_rejects_union_or_identical_stacks(self):
        with self.assertRaises(ValueError):
            DualStackSpec(legacy=AuthMode.UNION, current=AuthMode.V4)
        with self.assertRaises(ValueError):
            DualStackSpec(legacy=AuthMode.V3, current=AuthMode.V3)


class AuthModeSafeCoerceTest(SimpleTestCase):
    def test_valid_string_is_converted(self):
        self.assertEqual(AuthMode.safe_coerce("v4"), AuthMode.V4)

    def test_existing_auth_mode_instance_passes_through(self):
        self.assertEqual(AuthMode.safe_coerce(AuthMode.UNION), AuthMode.UNION)

    def test_invalid_string_falls_back_to_default_stack_legacy(self):
        self.assertEqual(AuthMode.safe_coerce("bad"), DEFAULT_DUAL_STACK.legacy)
        self.assertEqual(AuthMode.safe_coerce("off"), DEFAULT_DUAL_STACK.legacy)

    def test_invalid_string_falls_back_to_custom_default(self):
        self.assertEqual(AuthMode.safe_coerce("bad", default=AuthMode.V4), AuthMode.V4)


class ModeRouterTest(SimpleTestCase):
    def setUp(self):
        self.request = AuthRequest(subject=Subject(id="admin"), action_id="search_log_v2")
        self.v3 = Mock(name="v3-provider")
        self.v3.name = "v3"
        self.v4 = Mock(name="v4-provider")
        self.v4.name = "v4"
        self.pair_executor = Mock(side_effect=lambda left, right: (left(), right()))

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

    def test_union_follows_injected_stack_order(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)
        call_order = []
        self.v3.is_allowed.side_effect = lambda _request: call_order.append("v3") or AuthResult.allow("v3")
        self.v4.is_allowed.side_effect = lambda _request: call_order.append("v4") or AuthResult.deny("v4")
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.UNION)),
            bundles=self._bundles(),
            pair_executor=self.pair_executor,
            stack=stack,
        )

        decision = router.is_allowed(self.request)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.hit_provider_names, ("v3",))
        self.assertEqual(call_order, ["v4", "v3"])
        self.pair_executor.assert_called_once()

    def test_union_mode_delegates_provider_calls_to_pair_executor(self):
        self.v3.is_allowed.return_value = AuthResult.deny("v3")
        self.v4.is_allowed.return_value = AuthResult.allow("v4")
        router = self._make_router(AuthMode.UNION)

        decision = router.is_allowed(self.request)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.hit_provider_names, ("v4",))
        self.pair_executor.assert_called_once()

    def test_invalid_mode_rejects_auth(self):
        mode_provider = Mock(
            get_mode=Mock(side_effect=InvalidAuthModeError("bad", "invalid IAM permission mode configured: bad"))
        )
        router = ModeRouter(
            mode_provider=mode_provider,
            bundles=self._bundles(),
            pair_executor=self.pair_executor,
        )

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
        router = ModeRouter(
            mode_provider=mode_provider,
            bundles=self._bundles(),
            pair_executor=self.pair_executor,
        )

        result = router.batch_is_allowed(request)

        self.assertFalse(result.items[0].decision.allowed)
        self.assertEqual(result.items[0].decision.provider_results[0].error_type, "InvalidPermissionMode")

    def test_missing_v4_bundle_is_provider_not_configured(self):
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={AuthMode.V3: ProviderBundle(auth=self.v3)},
            pair_executor=self.pair_executor,
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
            pair_executor=self.pair_executor,
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
            pair_executor=self.pair_executor,
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
        router = ModeRouter(
            mode_provider=mode_provider,
            bundles=self._bundles(),
            pair_executor=self.pair_executor,
        )

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

    def test_list_authorized_scope_uses_bundle_scope_not_auth(self):
        auth = Mock(name="auth")
        scope = Mock(name="scope")
        scope.list_authorized_resources.return_value = AuthorizedResourceScope.concrete(
            "space", {"2"}, provider_name="v4"
        )
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={AuthMode.V4: ProviderBundle(auth=auth, scope=scope)},
            pair_executor=self.pair_executor,
        )

        resolution = router.list_authorized_scope(
            AuthMode.V4,
            action_id="view_business_v2",
            resource_type="space",
            subject={"type": "user", "id": "admin"},
            candidate_ids=None,
        )

        self.assertEqual(resolution.scope.ids, frozenset({"2"}))
        self.assertEqual(resolution.provider_scopes, (resolution.scope,))
        scope.list_authorized_resources.assert_called_once_with(
            action_id="view_business_v2",
            resource_type="space",
            subject={"type": "user", "id": "admin"},
            candidate_ids=None,
        )
        auth.list_authorized_resources.assert_not_called()

    def test_missing_scope_is_error_even_when_auth_exists(self):
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            bundles={AuthMode.V4: ProviderBundle(auth=self.v4, scope=None)},
            pair_executor=self.pair_executor,
        )

        resolution = router.list_authorized_scope(
            AuthMode.V4,
            action_id="view_business_v2",
            resource_type="space",
        )

        self.assertFalse(resolution.scope.ok)
        self.assertEqual(resolution.scope.error_type, "ProviderNotConfigured")
        self.assertEqual(resolution.scope.reason, "IAM v4 provider is not configured")
        self.v4.list_authorized_resources.assert_not_called()

    def test_union_scope_merges_and_uses_pair_executor(self):
        v3_scope = Mock(name="v3-scope")
        v3_scope.list_authorized_resources.return_value = AuthorizedResourceScope.concrete(
            "space", {"2"}, provider_name="v3"
        )
        v4_scope = Mock(name="v4-scope")
        v4_scope.list_authorized_resources.return_value = AuthorizedResourceScope.concrete(
            "space", {"4"}, provider_name="v4"
        )
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.UNION)),
            bundles={
                AuthMode.V3: ProviderBundle(scope=v3_scope),
                AuthMode.V4: ProviderBundle(scope=v4_scope),
            },
            pair_executor=self.pair_executor,
        )

        resolution = router.list_authorized_scope(
            AuthMode.UNION,
            action_id="view_business_v2",
            resource_type="space",
        )

        self.assertEqual(resolution.scope.ids, frozenset({"2", "4"}))
        self.assertEqual(resolution.scope.provider_name, "union")
        self.assertEqual(len(resolution.provider_scopes), 2)
        self.pair_executor.assert_called_once()

    def test_scope_providers_for_follows_injected_stack(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)
        v3_scope = Mock(name="v3-scope")
        v4_scope = Mock(name="v4-scope")
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.UNION)),
            bundles={
                AuthMode.V3: ProviderBundle(scope=v3_scope),
                AuthMode.V4: ProviderBundle(scope=v4_scope),
            },
            pair_executor=self.pair_executor,
            stack=stack,
        )

        self.assertEqual(
            router.scope_providers_for(AuthMode.UNION),
            (("v4", v4_scope), ("v3", v3_scope)),
        )

    def test_map_providers_rejects_unexpected_arity(self):
        router = self._make_router(AuthMode.V3)

        with self.assertRaises(ValueError) as ctx:
            router._map_providers((), lambda mode: mode)

        self.assertIn("exactly two provider modes", str(ctx.exception))
        self.pair_executor.assert_not_called()

    def _make_router(self, mode: AuthMode) -> ModeRouter:
        return ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=mode)),
            bundles=self._bundles(),
            pair_executor=self.pair_executor,
        )

    def _bundles(self) -> dict[AuthMode, ProviderBundle]:
        return {
            AuthMode.V3: ProviderBundle(auth=self.v3),
            AuthMode.V4: ProviderBundle(auth=self.v4),
        }
