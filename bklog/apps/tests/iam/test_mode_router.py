from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.iam_engine.core.config import AuthMode, DynamicModeConfigProvider
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthResult, AuthStatus, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import IAM_PERMISSION_MODE_CONFIG_ID, _load_mode_from_global_config, get_mode_provider


class DynamicModeConfigProviderTest(SimpleTestCase):
    def test_missing_or_invalid_config_falls_back_to_v3(self):
        for raw_mode in (None, "", "invalid"):
            with self.subTest(raw_mode=raw_mode):
                provider = DynamicModeConfigProvider(loader=lambda: raw_mode, ttl_seconds=0)
                self.assertEqual(provider.get_mode(), AuthMode.V3)

    def test_loader_error_falls_back_to_v3(self):
        loader = Mock(side_effect=RuntimeError("config unavailable"))
        provider = DynamicModeConfigProvider(loader=loader, ttl_seconds=0)

        self.assertEqual(provider.get_mode(), AuthMode.V3)

    def test_loader_accepts_normalized_auth_mode(self):
        provider = DynamicModeConfigProvider(loader=lambda: AuthMode.UNION, ttl_seconds=0)

        self.assertEqual(provider.get_mode(), AuthMode.UNION)

    def test_empty_resource_group_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "resource group must not be empty"):
            BatchAuthRequest(
                subject=Subject(id="admin"),
                action_ids=("view_collection_v2",),
                resource_groups=((),),
            )


class GlobalConfigModeProviderTest(SimpleTestCase):
    @patch("apps.log_search.models.GlobalConfig.objects")
    def test_load_mode_uses_fixed_global_config_key(self, objects):
        objects.filter.return_value.values_list.return_value.first.return_value = "union"

        self.assertEqual(_load_mode_from_global_config(), "union")
        objects.filter.assert_called_once_with(config_id=IAM_PERMISSION_MODE_CONFIG_ID)

    @override_settings(IAM_PERMISSION_MODE_CACHE_TTL=15)
    def test_default_provider_uses_configured_ttl(self):
        get_mode_provider.cache_clear()
        self.addCleanup(get_mode_provider.cache_clear)

        self.assertEqual(get_mode_provider().ttl_seconds, 15)

    def test_mode_refreshes_after_ttl_without_process_restart(self):
        modes = iter(("v3", "union"))
        now = Mock(side_effect=(100.0, 105.0, 111.0))
        provider = DynamicModeConfigProvider(loader=lambda: next(modes), ttl_seconds=10, clock=now)

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        self.assertEqual(provider.get_mode(), AuthMode.V3)
        self.assertEqual(provider.get_mode(), AuthMode.UNION)


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

    def test_missing_v4_provider_is_error_instead_of_implicit_v3_fallback(self):
        router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=AuthMode.V4)),
            v3_provider=self.v3,
            v4_provider=None,
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
            v3_provider=self.v3,
            v4_provider=None,
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

    def _make_router(self, mode: AuthMode) -> ModeRouter:
        return ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=mode)),
            v3_provider=self.v3,
            v4_provider=self.v4,
        )
