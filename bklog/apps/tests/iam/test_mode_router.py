from unittest.mock import Mock, call

from django.test import SimpleTestCase

from apps.feature_toggle.plugins.constants import IAM_V3_PERMISSION_TOGGLE, IAM_V4_PERMISSION_TOGGLE
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthResult, AuthStatus, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import FeatureToggleModeProvider, get_mode_provider


class FeatureToggleModeProviderTest(SimpleTestCase):
    def test_toggle_matrix(self):
        matrix = (
            (True, False, AuthMode.V3),
            (False, True, AuthMode.V4),
            (True, True, AuthMode.UNION),
        )
        resources = self._make_resources(ResourceInstance(type="space", id="42"))

        for v3_enabled, v4_enabled, expected_mode in matrix:
            with self.subTest(v3_enabled=v3_enabled, v4_enabled=v4_enabled):
                toggle_values = {
                    IAM_V3_PERMISSION_TOGGLE: v3_enabled,
                    IAM_V4_PERMISSION_TOGGLE: v4_enabled,
                }
                switch = Mock(side_effect=lambda **kwargs: toggle_values[kwargs["name"]])
                provider = FeatureToggleModeProvider(switch=switch)

                self.assertEqual(provider.get_mode(resources), expected_mode)
                self.assertEqual(
                    switch.call_args_list,
                    [
                        call(name=IAM_V3_PERMISSION_TOGGLE, biz_id=42, default=True),
                        call(name=IAM_V4_PERMISSION_TOGGLE, biz_id=42, default=False),
                    ],
                )

    def test_both_toggles_disabled_falls_back_to_v3_and_records_error(self):
        logger = Mock()
        provider = FeatureToggleModeProvider(switch=Mock(return_value=False), logger=logger)

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        logger.error.assert_called_once_with(
            "both IAM permission feature toggles are disabled, fallback to v3, biz_id=%s",
            None,
        )

    def test_toggle_error_falls_back_to_v3(self):
        logger = Mock()
        provider = FeatureToggleModeProvider(
            switch=Mock(side_effect=RuntimeError("toggle unavailable")),
            logger=logger,
        )

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        logger.exception.assert_called_once_with("failed to load IAM permission feature toggles, fallback to v3")

    def test_business_id_is_resolved_from_resource_metadata(self):
        resources = self._make_resources(
            ResourceInstance(type="space", id="42"),
            ResourceInstance(type="collection", id="1", attributes={"bk_biz_id": "42"}),
            ResourceInstance(type="indices", id="2", attributes={"_bk_iam_path_": "/space,42/"}),
        )
        switch = Mock(side_effect=(True, False))
        provider = FeatureToggleModeProvider(switch=switch)

        self.assertEqual(provider.get_mode(resources), AuthMode.V3)
        self.assertTrue(all(call.kwargs["biz_id"] == 42 for call in switch.call_args_list))

    def test_multiple_business_ids_use_global_toggle(self):
        resources = self._make_resources(
            ResourceInstance(type="space", id="1"),
            ResourceInstance(type="space", id="2"),
        )
        switch = Mock(side_effect=(True, False))
        logger = Mock()
        provider = FeatureToggleModeProvider(switch=switch, logger=logger)

        self.assertEqual(provider.get_mode(resources), AuthMode.V3)
        self.assertTrue(all(call.kwargs["biz_id"] is None for call in switch.call_args_list))
        logger.warning.assert_called_once()

    def test_invalid_business_metadata_is_ignored(self):
        resources = self._make_resources(
            ResourceInstance(
                type="space",
                id="not-a-business-id",
                attributes={"bk_biz_id": "invalid", "_bk_iam_path_": None},
            )
        )
        switch = Mock(side_effect=(True, False))
        provider = FeatureToggleModeProvider(switch=switch)

        self.assertEqual(provider.get_mode(resources), AuthMode.V3)
        self.assertTrue(all(call.kwargs["biz_id"] is None for call in switch.call_args_list))

    def test_empty_resource_group_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "resource group must not be empty"):
            BatchAuthRequest(
                subject=Subject(id="admin"),
                action_ids=("view_collection_v2",),
                resource_groups=((),),
            )

    def test_mode_reads_feature_toggles_for_each_request(self):
        switch = Mock(side_effect=(True, False, True, True, False, True))
        provider = FeatureToggleModeProvider(switch=switch)

        self.assertEqual(provider.get_mode(), AuthMode.V3)
        self.assertEqual(provider.get_mode(), AuthMode.UNION)
        self.assertEqual(provider.get_mode(), AuthMode.V4)
        self.assertEqual(switch.call_count, 6)

    def test_default_provider_does_not_cache_toggle_values(self):
        get_mode_provider.cache_clear()
        self.addCleanup(get_mode_provider.cache_clear)

        provider = get_mode_provider()

        self.assertIsInstance(provider, FeatureToggleModeProvider)
        self.assertFalse(hasattr(provider, "_cache"))

    @staticmethod
    def _make_resources(*resources: ResourceInstance) -> tuple[ResourceInstance, ...]:
        return resources


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
        router = ModeRouter(mode_provider=mode_provider, v3_provider=self.v3, v4_provider=self.v4)

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
            v3_provider=self.v3,
            v4_provider=self.v4,
        )
