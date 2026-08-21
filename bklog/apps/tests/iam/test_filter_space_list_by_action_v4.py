from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from iam.exceptions import AuthAPIError

from apps.iam.exceptions import IAMDependencyError
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.types import AuthorizedResourceScope


def make_scope_provider(scope=None, *, side_effect=None, requires_candidate_ids=False) -> MagicMock:
    """构造实现 AuthorizedScopeProvider 契约的假 Provider。"""
    provider = MagicMock()
    provider.requires_candidate_ids = requires_candidate_ids
    provider.list_authorized_resources = MagicMock(return_value=scope, side_effect=side_effect)
    return provider


class FilterSpaceListByActionV4Test(SimpleTestCase):
    def setUp(self):
        self.permission = Permission(username="admin", bk_tenant_id="tenant-1")
        self.spaces = [
            {"bk_biz_id": 2, "space_name": "biz-2"},
            {"bk_biz_id": 3, "space_name": "biz-3"},
            {"bk_biz_id": 4, "space_name": "biz-4"},
        ]

    def test_dependency_error_hides_internal_reason_from_public_message(self):
        with self.assertNoLogs(level="ERROR"):
            error = IAMDependencyError("upstream response contains private detail", provider="v4")

        self.assertEqual(error.message, "权限中心依赖异常")
        self.assertNotIn("private detail", str(error))
        self.assertEqual(error.reason, "upstream response contains private detail")
        self.assertEqual(error.provider, "v4")
        self.assertIsNone(error.data)

    def test_provider_bundles_wire_scope_separately_from_auth(self):
        v3 = make_scope_provider(requires_candidate_ids=True)
        v4 = make_scope_provider()
        self.permission._v3_provider = v3
        self.permission._v4_provider = v4
        self.permission._provider_bundles = None

        bundles = self.permission.provider_bundles

        self.assertIs(bundles[AuthMode.V3].scope, v3)
        self.assertIs(bundles[AuthMode.V4].scope, v4)
        self.assertIs(bundles[AuthMode.V3].auth, v3)
        self.assertIs(bundles[AuthMode.V4].auth, v4)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_intersects_authorized_ids_with_local_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2", "4", "100"}, provider_name="v4")
        )

        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_wildcard_returns_all_local_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.wildcard("space", provider_name="v4")
        )

        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 3, 4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_error_is_not_disguised_as_empty_deny(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.error("space", provider_name="v4", reason="timeout", error_type="TimeoutError")
        )

        with self.assertLogs(level="ERROR") as logs, self.assertRaises(IAMDependencyError):
            self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

        self.assertEqual(len(logs.records), 1)
        self.assertIn("provider=v4", logs.records[0].getMessage())

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v3_auth_api_error_raises_dependency_error(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V3
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)
        self.permission.iam_client = MagicMock()
        self.permission.iam_client._do_policy_query.side_effect = AuthAPIError("boom")

        with self.assertRaises(IAMDependencyError):
            self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_union_merges_v3_and_v4_and_tolerates_one_side_error(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.UNION
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v3_provider = make_scope_provider(
            AuthorizedResourceScope.error("space", provider_name="v3", reason="v3 down", error_type="AuthAPIError"),
            requires_candidate_ids=True,
        )
        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"3"}, provider_name="v4")
        )

        with self.assertLogs(level="WARNING") as logs:
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

        self.assertEqual([space["bk_biz_id"] for space in results], [3])
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(logs.records[0].levelname, "WARNING")
        self.assertIn("union space scope degraded", logs.records[0].getMessage())

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_union_merges_successful_v3_and_v4_ids(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.UNION
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v3_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3"),
            requires_candidate_ids=True,
        )
        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"4"}, provider_name="v4")
        )

        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_union_degrades_when_one_side_provider_is_not_configured(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.UNION
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v3_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3"),
            requires_candidate_ids=True,
        )

        with patch.object(Permission, "get_v4_provider", return_value=None), self.assertLogs(level="WARNING") as logs:
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

        self.assertEqual([space["bk_biz_id"] for space in results], [2])
        self.assertIn("v4_error=IAM v4 provider is not configured", logs.records[0].getMessage())

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_unconfigured_provider_fails_closed_without_loading_all_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        # 未配置的 Provider 读不到 requires_candidate_ids，早期实现会在选路时抛 AttributeError。
        with (
            patch.object(Permission, "get_v4_provider", return_value=None),
            self.assertLogs(level="ERROR"),
            self.assertRaises(IAMDependencyError),
        ):
            self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_union_calls_v3_and_v4_concurrently(self):
        import threading
        import time

        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.UNION
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        started = threading.Event()
        release = threading.Event()

        def v3_side_effect(**_kwargs):
            started.set()
            release.wait(timeout=1)
            return AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3")

        def v4_side_effect(**_kwargs):
            if not started.wait(timeout=1):
                return AuthorizedResourceScope.empty("space", provider_name="v4")
            release.set()
            return AuthorizedResourceScope.concrete("space", {"4"}, provider_name="v4")

        self.permission._v3_provider = make_scope_provider(side_effect=v3_side_effect, requires_candidate_ids=True)
        self.permission._v4_provider = make_scope_provider(side_effect=v4_side_effect)

        started_at = time.monotonic()
        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        elapsed = time.monotonic() - started_at

        self.assertEqual([space["bk_biz_id"] for space in results], [2, 4])
        self.assertLess(elapsed, 0.5)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_union_both_errors_fail_closed(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.UNION
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v3_provider = make_scope_provider(
            AuthorizedResourceScope.error("space", provider_name="v3", reason="v3", error_type="AuthAPIError"),
            requires_candidate_ids=True,
        )
        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.error("space", provider_name="v4", reason="v4", error_type="V4ClientError")
        )

        with self.assertLogs(level="ERROR") as logs, self.assertRaises(IAMDependencyError):
            self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

        self.assertEqual(len(logs.records), 1)
        self.assertIn("provider=union", logs.records[0].getMessage())

    @override_settings(IGNORE_IAM_PERMISSION=True, DEMO_BIZ_ID=-1)
    def test_ignore_permission_returns_all_spaces(self):
        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual(len(results), 3)

    @override_settings(IGNORE_IAM_PERMISSION=True, DEMO_BIZ_ID=-1)
    def test_ignore_permission_without_space_list_loads_all_spaces(self):
        with patch(
            "apps.log_search.models.Space.get_all_spaces",
            return_value=self.spaces,
        ) as get_all_spaces:
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")
        get_all_spaces.assert_called_once_with(bk_tenant_id="tenant-1")
        self.assertEqual(results, self.spaces)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=4)
    def test_demo_biz_is_always_kept(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)
        self.permission._v4_provider = make_scope_provider(AuthorizedResourceScope.empty("space", provider_name="v4"))

        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual([space["bk_biz_id"] for space in results], [4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_invalid_mode_raises_dependency_error(self):
        from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError

        mode_provider = MagicMock()
        mode_provider.get_mode.side_effect = InvalidAuthModeError("bad", "invalid mode")
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        with self.assertRaises(IAMDependencyError):
            self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v3_policy_eval_keeps_allowed_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V3
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)
        self.permission.iam_client = MagicMock()
        self.permission.iam_client._do_policy_query.return_value = {"op": "any"}

        def _eval(_expr, obj_set):
            return obj_set.get_object("space")["id"] == "2"

        self.permission.iam_client._eval_expr.side_effect = _eval

        with patch("apps.iam.backends.v3.scope.make_expression", return_value="expr"):
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual([space["bk_biz_id"] for space in results], [2])
        self.assertEqual(self.permission.iam_client._eval_expr.call_count, 3)

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v3_empty_policies_return_empty(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V3
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)
        self.permission.iam_client = MagicMock()
        self.permission.iam_client._do_policy_query.return_value = None

        results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1", self.spaces)
        self.assertEqual(results, [])


class FilterSpaceListByActionV4TargetedQueryTest(SimpleTestCase):
    """纯 V4 且未传入 space_list：IAM 先查 → 定向查库。"""

    def setUp(self):
        self.permission = Permission(username="admin", bk_tenant_id="tenant-1")

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_targeted_query_avoids_get_all_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2", "4", "100"}, provider_name="v4")
        )

        targeted_spaces = [
            {"bk_biz_id": 2, "space_name": "biz-2"},
            {"bk_biz_id": 4, "space_name": "biz-4"},
        ]
        with patch("apps.log_search.models.Space.get_all_spaces") as get_all_spaces:
            with patch(
                "apps.log_search.models.Space.get_spaces_by_bk_biz_ids",
                return_value=targeted_spaces,
            ) as get_by_ids:
                results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

        get_all_spaces.assert_not_called()
        get_by_ids.assert_called_once()
        called_ids = set(get_by_ids.call_args[0][1])
        self.assertEqual(called_ids, {"2", "4", "100"})
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_targeted_wildcard_falls_back_to_get_all_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.wildcard("space", provider_name="v4")
        )

        all_spaces = [
            {"bk_biz_id": 2, "space_name": "biz-2"},
            {"bk_biz_id": 3, "space_name": "biz-3"},
        ]
        with patch("apps.log_search.models.Space.get_all_spaces", return_value=all_spaces) as get_all_spaces:
            with patch("apps.log_search.models.Space.get_spaces_by_bk_biz_ids") as get_by_ids:
                results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

        get_all_spaces.assert_called_once_with(bk_tenant_id="tenant-1")
        get_by_ids.assert_not_called()
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 3])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_targeted_empty_scope_returns_empty_without_full_scan(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(AuthorizedResourceScope.empty("space", provider_name="v4"))

        with patch("apps.log_search.models.Space.get_all_spaces") as get_all_spaces:
            with patch(
                "apps.log_search.models.Space.get_spaces_by_bk_biz_ids",
                return_value=[],
            ) as get_by_ids:
                results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

        get_all_spaces.assert_not_called()
        get_by_ids.assert_called_once()
        self.assertEqual(results, [])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v4_targeted_error_raises_dependency_error(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.error("space", provider_name="v4", reason="timeout", error_type="TimeoutError")
        )

        with patch("apps.log_search.models.Space.get_all_spaces") as get_all_spaces:
            with self.assertRaises(IAMDependencyError):
                self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")
        get_all_spaces.assert_not_called()

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=4)
    def test_v4_targeted_includes_demo_biz_in_query_ids(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V4
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)

        self.permission._v4_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v4")
        )

        targeted_spaces = [
            {"bk_biz_id": 2, "space_name": "biz-2"},
            {"bk_biz_id": 4, "space_name": "demo"},
        ]
        with patch(
            "apps.log_search.models.Space.get_spaces_by_bk_biz_ids",
            return_value=targeted_spaces,
        ) as get_by_ids:
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

        called_ids = set(get_by_ids.call_args[0][1])
        self.assertEqual(called_ids, {"2", "4"})
        self.assertEqual([space["bk_biz_id"] for space in results], [2, 4])

    @override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=-1)
    def test_v3_without_space_list_loads_all_spaces(self):
        mode_provider = MagicMock()
        mode_provider.get_mode.return_value = AuthMode.V3
        self.permission._mode_router = MagicMock(mode_provider=mode_provider)
        self.permission._v3_provider = make_scope_provider(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3"),
            requires_candidate_ids=True,
        )

        with patch(
            "apps.log_search.models.Space.get_all_spaces",
            return_value=[{"bk_biz_id": 2, "space_name": "biz-2"}],
        ) as get_all_spaces:
            results = self.permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, "tenant-1")

        get_all_spaces.assert_called_once_with(bk_tenant_id="tenant-1")
        self.assertEqual([space["bk_biz_id"] for space in results], [2])

    @override_settings(DEMO_BIZ_ID=0)
    def test_default_demo_biz_id_is_not_treated_as_enabled(self):
        spaces = [{"bk_biz_id": 0}, {"bk_biz_id": 2}]

        results = self.permission._keep_spaces_by_allowed_ids(spaces, {"2"})

        self.assertEqual(results, [{"bk_biz_id": 2}])

    @override_settings(DEMO_BIZ_ID="invalid")
    def test_invalid_demo_biz_id_is_not_treated_as_enabled(self):
        self.assertEqual(self.permission._get_enabled_demo_biz_id(), "")
