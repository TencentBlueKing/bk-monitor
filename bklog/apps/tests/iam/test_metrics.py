import time
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from iam.exceptions import AuthAPIError
from prometheus_client import generate_latest

from apps.iam import metrics
from apps.iam.backends.v3.provider import V3PermissionProvider
from apps.iam.backends.v4.exceptions import V4TimeoutError
from apps.iam.backends.v4.provider import V4PermissionProvider
from apps.iam.handlers.actions import ActionEnum, get_action_by_id
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthorizedResourceScope, AuthResult
from apps.iam.iam_engine.migration.dual_write import DualWriteGrantOrchestrator
from apps.iam.concurrency import run_pair_concurrently
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.utils.prometheus import REGISTRY


def label_kwargs(metric: Mock) -> list[dict]:
    """取出指标每次 labels() 的入参。

    不断言 Prometheus 样本值：BkLogRegistry.collect() 采集后会清空 collector._metrics，
    而指标是模块级单例，跨用例读样本会互相污染。
    """
    return [call.kwargs for call in metric.labels.call_args_list]


class MetricPatchMixin:
    def patch_metric(self, name: str) -> Mock:
        patcher = patch(f"apps.iam.metrics.{name}")
        metric = patcher.start()
        self.addCleanup(patcher.stop)
        return metric

    def patch_permission_dependencies(self) -> None:
        self.iam_client = Mock()
        self.v4_provider = Mock()
        self.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
        for patcher in (
            patch.object(Permission, "get_iam_client", return_value=self.iam_client),
            patch.object(Permission, "get_v4_provider", return_value=self.v4_provider),
            patch.object(Permission, "get_v4_authorization_writer", return_value=None),
            patch("apps.iam.handlers.permission.get_mode_provider", return_value=self.mode_provider),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)


class MetricRegistrationTest(SimpleTestCase):
    """真实注册表冒烟：其余用例都在 mock 上断言，写错 label 名或指标重名不会被发现。"""

    def test_every_metric_is_registered_and_collectible(self):
        metrics.IAM_AUTH_DECISION_COUNT.labels(
            mode="union",
            action_id="view_business_v2",
            resource_type="space",
            api="is_allowed",
            allowed="true",
            hit_provider="v3+v4",
            degraded="false",
        ).inc()
        metrics.IAM_PROVIDER_RESULT_COUNT.labels(
            mode="union",
            provider="v4",
            action_id="view_business_v2",
            api="is_allowed",
            status="allow",
            error_type="",
        ).inc()
        metrics.IAM_UNION_DIVERGENCE_COUNT.labels(
            action_id="view_business_v2", api="space_scope", pattern="v4_error"
        ).inc()
        metrics.IAM_GRANT_SYNC_COUNT.labels(target_version="v4", resource_type="collection", result="succeeded").inc()
        metrics.observe_provider_latency("v4", metrics.AUTH_API_IS_ALLOWED, time.time(), ok=True)

        # collect() 会清空 collector，本次采集同时把用例写入的样本取走，不会累加到后续用例
        exposition = generate_latest(REGISTRY).decode()

        for sample_name in (
            "iam_auth_decision_count_total",
            "iam_provider_result_count_total",
            "iam_union_divergence_count_total",
            "iam_grant_sync_count_total",
            "iam_provider_latency_count",
        ):
            self.assertIn(sample_name, exposition)
        self.assertIn('hit_provider="v3+v4"', exposition)
        self.assertIn('pattern="v4_error"', exposition)


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="default",
    DEMO_BIZ_ID=0,
    DEMO_BIZ_EDIT_ENABLED=False,
)
class AuthDecisionMetricsTest(MetricPatchMixin, TestCase):
    """通过 Permission 门面驱动真实决策，校验决策级与 per-provider 指标的 label 归一。"""

    def setUp(self):
        self.patch_permission_dependencies()
        self.decision_count = self.patch_metric("IAM_AUTH_DECISION_COUNT")
        self.provider_count = self.patch_metric("IAM_PROVIDER_RESULT_COUNT")
        self.divergence_count = self.patch_metric("IAM_UNION_DIVERGENCE_COUNT")
        self.permission = Permission(username="tester", bk_tenant_id="default")

    def _is_allowed(self, biz_id: str = "2") -> bool:
        return self.permission.is_allowed(
            ActionEnum.VIEW_BUSINESS,
            [ResourceEnum.BUSINESS.create_simple_instance(biz_id)],
        )

    def test_v3_allow_records_decision_and_provider_labels(self):
        self.iam_client.is_allowed.return_value = True

        self.assertTrue(self._is_allowed())

        self.assertEqual(
            label_kwargs(self.decision_count),
            [
                {
                    "mode": "v3",
                    "action_id": "view_business_v2",
                    "resource_type": "space",
                    "api": "is_allowed",
                    "allowed": "true",
                    "hit_provider": "v3",
                    "degraded": "false",
                }
            ],
        )
        self.assertEqual(
            label_kwargs(self.provider_count),
            [
                {
                    "mode": "v3",
                    "provider": "v3",
                    "action_id": "view_business_v2",
                    "api": "is_allowed",
                    "status": "allow",
                    "error_type": "",
                }
            ],
        )
        self.divergence_count.labels.assert_not_called()

    def test_v3_dependency_error_is_recorded_as_degraded_deny(self):
        self.iam_client.is_allowed.side_effect = AuthAPIError("request timeout")

        self.assertFalse(self._is_allowed())

        decision = label_kwargs(self.decision_count)[0]
        self.assertEqual(decision["allowed"], "false")
        self.assertEqual(decision["degraded"], "true")
        self.assertEqual(decision["hit_provider"], "none")
        provider = label_kwargs(self.provider_count)[0]
        self.assertEqual(provider["status"], "error")
        self.assertEqual(provider["error_type"], "AuthAPIError")

    def test_v4_mode_deny_records_v4_provider_only(self):
        self.mode_provider.get_mode.return_value = AuthMode.V4
        self.v4_provider.is_allowed.return_value = AuthResult.deny("v4")

        self.assertFalse(self._is_allowed())

        self.assertEqual(label_kwargs(self.decision_count)[0]["mode"], "v4")
        self.assertEqual(
            [(call["provider"], call["status"]) for call in label_kwargs(self.provider_count)],
            [("v4", "deny")],
        )
        self.divergence_count.labels.assert_not_called()

    def test_illegal_mode_configuration_is_normalized_to_invalid(self):
        self.mode_provider.get_mode.side_effect = InvalidAuthModeError("v5-typo", "unsupported auth mode")

        self.assertFalse(self._is_allowed())

        # 非法模式来自环境变量或 Feature Toggle，是运维可改写的配置，不归一 label 就不再是有限枚举
        self.assertEqual(label_kwargs(self.decision_count)[0]["mode"], "invalid")
        provider = label_kwargs(self.provider_count)[0]
        self.assertEqual((provider["mode"], provider["provider"]), ("invalid", "mode"))
        self.assertEqual(provider["error_type"], "InvalidPermissionMode")

    def test_action_without_related_resource_uses_none_resource_type(self):
        self.iam_client.is_allowed.return_value = True

        self.assertTrue(self.permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE))

        self.assertEqual(label_kwargs(self.decision_count)[0]["resource_type"], "none")

    def test_batch_decision_records_one_sample_per_action_and_resource(self):
        self.iam_client.batch_resource_multi_actions_allowed.return_value = {
            "2": {"view_business_v2": True, "create_client_log_task": False},
            "3": {"view_business_v2": False, "create_client_log_task": False},
        }

        result = self.permission.batch_is_allowed(
            [ActionEnum.VIEW_BUSINESS, ActionEnum.CREATE_CLIENT_LOG_TASK],
            [
                [ResourceEnum.BUSINESS.create_simple_instance("2")],
                [ResourceEnum.BUSINESS.create_simple_instance("3")],
            ],
        )

        # 埋点不改变批量鉴权结果
        self.assertEqual(
            result,
            {
                "2": {"view_business_v2": True, "create_client_log_task": False},
                "3": {"view_business_v2": False, "create_client_log_task": False},
            },
        )
        decisions = label_kwargs(self.decision_count)
        self.assertEqual(len(decisions), 4)
        self.assertEqual({call["api"] for call in decisions}, {"batch_is_allowed"})
        self.assertEqual({call["resource_type"] for call in decisions}, {"space"})
        self.assertEqual(
            {(call["action_id"], call["allowed"]) for call in decisions},
            {
                ("view_business_v2", "true"),
                ("view_business_v2", "false"),
                ("create_client_log_task", "false"),
            },
        )


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="default",
    DEMO_BIZ_ID=0,
    DEMO_BIZ_EDIT_ENABLED=False,
)
class UnionDivergenceMetricsTest(MetricPatchMixin, TestCase):
    """union 模式下的分歧口径：策略不一致与单侧依赖故障必须分开计数。"""

    def setUp(self):
        self.patch_permission_dependencies()
        self.mode_provider.get_mode.return_value = AuthMode.UNION
        self.decision_count = self.patch_metric("IAM_AUTH_DECISION_COUNT")
        self.divergence_count = self.patch_metric("IAM_UNION_DIVERGENCE_COUNT")
        self.permission = Permission(username="tester", bk_tenant_id="default")

    def _is_allowed(self) -> bool:
        return self.permission.is_allowed(
            ActionEnum.VIEW_BUSINESS,
            [ResourceEnum.BUSINESS.create_simple_instance("2")],
        )

    def _patterns(self) -> list[str]:
        return [call["pattern"] for call in label_kwargs(self.divergence_count)]

    def test_both_sides_allow_is_not_a_divergence(self):
        self.iam_client.is_allowed.return_value = True
        self.v4_provider.is_allowed.return_value = AuthResult.allow("v4")

        self.assertTrue(self._is_allowed())

        self.assertEqual(self._patterns(), [])
        self.assertEqual(label_kwargs(self.decision_count)[0]["hit_provider"], "v3+v4")

    def test_v3_allow_against_v4_deny_is_a_policy_divergence(self):
        self.iam_client.is_allowed.return_value = True
        self.v4_provider.is_allowed.return_value = AuthResult.deny("v4")

        self.assertTrue(self._is_allowed())

        self.assertEqual(self._patterns(), ["v3_only_allow"])
        self.assertEqual(label_kwargs(self.divergence_count)[0]["api"], "is_allowed")

    def test_v4_allow_against_v3_deny_is_a_policy_divergence(self):
        self.iam_client.is_allowed.return_value = False
        self.v4_provider.is_allowed.return_value = AuthResult.allow("v4")

        self.assertTrue(self._is_allowed())

        self.assertEqual(self._patterns(), ["v4_only_allow"])

    def test_single_side_error_is_recorded_as_error_not_policy_divergence(self):
        self.iam_client.is_allowed.side_effect = AuthAPIError("request timeout")
        self.v4_provider.is_allowed.return_value = AuthResult.allow("v4")

        self.assertTrue(self._is_allowed())

        # 报错一侧只计 v3_error，不能再计一次 only_allow，否则依赖故障会混进策略差异口径
        self.assertEqual(self._patterns(), ["v3_error"])

    def test_v4_error_is_attributed_to_v4(self):
        self.iam_client.is_allowed.return_value = False
        self.v4_provider.is_allowed.return_value = AuthResult.error(
            "v4", reason="IAM V4 request timeout", error_type="V4TimeoutError"
        )

        self.assertFalse(self._is_allowed())

        self.assertEqual(self._patterns(), ["v4_error"])

    def test_both_sides_error_collapses_to_a_single_pattern(self):
        self.iam_client.is_allowed.side_effect = AuthAPIError("request timeout")
        self.v4_provider.is_allowed.return_value = AuthResult.error(
            "v4", reason="IAM V4 request timeout", error_type="V4TimeoutError"
        )

        self.assertFalse(self._is_allowed())

        self.assertEqual(self._patterns(), ["both_error"])


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_APP_TENANT_ID="default")
class SpaceScopeDivergenceMetricsTest(MetricPatchMixin, TestCase):
    """授权范围查询的降级与 is_allowed 共用 pattern 口径，只是 api 不同。"""

    def setUp(self):
        self.patch_permission_dependencies()
        self.divergence_count = self.patch_metric("IAM_UNION_DIVERGENCE_COUNT")
        self.permission = Permission(username="tester", bk_tenant_id="default")

    def _resolve(
        self,
        left: AuthorizedResourceScope,
        right: AuthorizedResourceScope,
        *,
        mode: AuthMode = AuthMode.UNION,
    ):
        v3 = Mock(list_authorized_resources=Mock(return_value=left), requires_candidate_ids=True)
        v4 = Mock(list_authorized_resources=Mock(return_value=right), requires_candidate_ids=False)
        self.permission._mode_router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=mode)),
            bundles={
                AuthMode.V3: ProviderBundle(scope=v3),
                AuthMode.V4: ProviderBundle(scope=v4),
            },
            pair_executor=run_pair_concurrently,
        )
        return self.permission._resolve_authorized_scope(
            ActionEnum.VIEW_BUSINESS,
            mode,
            candidate_ids=None,
        )

    @staticmethod
    def _failed_scope(provider_name: str) -> AuthorizedResourceScope:
        return AuthorizedResourceScope.error(
            "space",
            provider_name=provider_name,
            reason="IAM authorized-resources failed",
            error_type="V4TimeoutError",
        )

    def test_both_sides_ok_is_not_a_divergence(self):
        scope = self._resolve(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3"),
            AuthorizedResourceScope.concrete("space", {"3"}, provider_name="v4"),
        )

        self.assertEqual(scope.ids, frozenset({"2", "3"}))
        self.divergence_count.labels.assert_not_called()

    def test_single_side_failure_is_recorded_with_space_scope_api(self):
        scope = self._resolve(
            AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3"),
            self._failed_scope("v4"),
        )

        self.assertTrue(scope.ok)
        self.assertEqual(
            label_kwargs(self.divergence_count),
            [{"action_id": "view_business_v2", "api": "space_scope", "pattern": "v4_error"}],
        )

    def test_both_sides_failure_collapses_to_a_single_pattern(self):
        scope = self._resolve(self._failed_scope("v3"), self._failed_scope("v4"))

        self.assertFalse(scope.ok)
        self.assertEqual([call["pattern"] for call in label_kwargs(self.divergence_count)], ["both_error"])

    def test_single_stack_failure_is_not_a_union_divergence(self):
        """生产默认 v3 / 纯 v4 只有一侧，失败不能打 both_error，否则灰度基线被 IAM 抖动污染。"""
        unused = AuthorizedResourceScope.concrete("space", {"2"}, provider_name="unused")
        for mode, left, right in (
            (AuthMode.V3, self._failed_scope("v3"), unused),
            (AuthMode.V4, unused, self._failed_scope("v4")),
        ):
            with self.subTest(mode=mode.value):
                self.divergence_count.reset_mock()
                scope = self._resolve(left, right, mode=mode)
                self.assertFalse(scope.ok)
                self.divergence_count.labels.assert_not_called()


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search")
class ProviderLatencyMetricsTest(SimpleTestCase):
    """两侧 Provider 的每个调用入口在成功与失败路径都必须记录耗时。"""

    def setUp(self):
        self.latency = None
        patcher = patch("apps.iam.metrics.IAM_PROVIDER_LATENCY")
        self.latency = patcher.start()
        self.addCleanup(patcher.stop)

        self.v3_client = Mock()
        self.v3 = V3PermissionProvider(self.v3_client, "bk_log_search", action_resolver=get_action_by_id)
        self.v4_client = Mock()
        self.v4_client.options.system_id = "bk_log_search"
        self.v4_client.options.batch_chunk_size = 100
        self.v4_client.options.batch_max_workers = 4
        self.v4_client.username = "tester"
        self.v4 = V4PermissionProvider(self.v4_client, action_resolver=get_action_by_id)

        self.request = AuthRequest(
            subject=Subject(id="tester", tenant_id="default"),
            action_id=ActionEnum.VIEW_BUSINESS,
            resources=(ResourceInstance(type="space", id="2", system="bk_monitorv3"),),
        )
        self.batch_request = BatchAuthRequest(
            subject=Subject(id="tester", tenant_id="default"),
            action_ids=(ActionEnum.VIEW_BUSINESS,),
            resource_groups=((ResourceInstance(type="space", id="2", system="bk_monitorv3"),),),
        )

    def _observations(self) -> list[tuple[str, str, str]]:
        return [(call["provider"], call["api"], call["status"]) for call in label_kwargs(self.latency)]

    def test_v3_records_ok_and_error_for_every_entry_point(self):
        self.v3_client.is_allowed.return_value = True
        self.v3.is_allowed(self.request)
        self.v3_client.is_allowed.side_effect = AuthAPIError("request timeout")
        self.v3.is_allowed(self.request)

        self.v3_client.batch_resource_multi_actions_allowed.return_value = {"2": {"view_business_v2": True}}
        self.v3.batch_is_allowed(self.batch_request)
        self.v3_client.batch_resource_multi_actions_allowed.side_effect = AuthAPIError("request timeout")
        self.v3.batch_is_allowed(self.batch_request)

        self.assertEqual(
            self._observations(),
            [
                ("v3", "is_allowed", "ok"),
                ("v3", "is_allowed", "error"),
                ("v3", "batch_is_allowed", "ok"),
                ("v3", "batch_is_allowed", "error"),
            ],
        )

    def test_v3_batch_with_missing_entries_is_counted_as_error_like_v4(self):
        # 请求本身成功，但响应缺了该 Action 的结果，逐条会生成 IncompleteBatchResult
        self.v3_client.batch_resource_multi_actions_allowed.return_value = {"2": {}}

        self.v3.batch_is_allowed(self.batch_request)

        # V4 用「任一条目失败即 error」判定，V3 必须同口径，两侧错误率曲线才可比
        self.assertEqual(self._observations(), [("v3", "batch_is_allowed", "error")])

    def test_v3_space_scope_status_follows_the_returned_scope(self):
        self.v3.scope_query = Mock(
            list_authorized_resources=Mock(
                return_value=AuthorizedResourceScope.concrete("space", {"2"}, provider_name="v3")
            )
        )
        self.v3.list_authorized_resources(action_id="view_business_v2", resource_type="space")

        self.v3.scope_query.list_authorized_resources.return_value = AuthorizedResourceScope.error(
            "space", provider_name="v3", reason="policy query failed", error_type="AuthAPIError"
        )
        self.v3.list_authorized_resources(action_id="view_business_v2", resource_type="space")

        self.assertEqual(
            self._observations(),
            [("v3", "space_scope", "ok"), ("v3", "space_scope", "error")],
        )

    def test_v4_records_ok_and_error_for_every_entry_point(self):
        self.v4_client.direct_auth.return_value = True
        self.v4.is_allowed(self.request)
        self.v4_client.direct_auth.side_effect = V4TimeoutError("IAM V4 request timeout")
        self.v4.is_allowed(self.request)

        self.v4_client.direct_auth.side_effect = None
        self.v4_client.direct_auth_by_resources.return_value = {"2": True}
        self.v4.batch_is_allowed(self.batch_request)
        self.v4_client.direct_auth_by_resources.side_effect = V4TimeoutError("IAM V4 request timeout")
        self.v4.batch_is_allowed(self.batch_request)

        self.v4_client.list_authorized_resource.return_value = {"type": "space", "ids": ["2"]}
        self.v4.list_authorized_resources(action_id="view_business_v2", resource_type="space")
        self.v4_client.list_authorized_resource.side_effect = V4TimeoutError("IAM V4 request timeout")
        self.v4.list_authorized_resources(action_id="view_business_v2", resource_type="space")

        self.assertEqual(
            self._observations(),
            [
                ("v4", "is_allowed", "ok"),
                ("v4", "is_allowed", "error"),
                ("v4", "batch_is_allowed", "ok"),
                ("v4", "batch_is_allowed", "error"),
                ("v4", "space_scope", "ok"),
                ("v4", "space_scope", "error"),
            ],
        )


class GrantSyncMetricsTest(TestCase):
    """双写同步路径的每个分支各对应一个 result，指标由 Permission 注入的观测出口发出。"""

    application = {
        "system": "bk_log_search",
        "type": "collection",
        "id": "28",
        "name": "collection-28",
        "creator": "creator",
    }

    def setUp(self):
        patcher = patch("apps.iam.metrics.IAM_GRANT_SYNC_COUNT")
        self.grant_count = patcher.start()
        self.addCleanup(patcher.stop)

        self.v3_writer = Mock()
        self.v3_writer.grant_resource_creator_actions.return_value = (True, "success")
        self.v4_writer = Mock()
        self.v4_writer.prepare_resource_creator_actions.return_value = PreparedAuthorizationGrant(
            payload=[{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
            role_id="space_operator",
            expired_at=1893456000,
        )
        self.dispatch = Mock()
        self.orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer), ("v4", self.v4_writer)),
            tenant_id="tenant-1",
            operator="operator",
            grant_observer=Permission._observe_grant,
            dispatch_retry_grant=self.dispatch,
        )

    def _grant(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.orchestrator.grant_creator_action(self.application)

    def _results(self) -> list[tuple[str, str, str]]:
        return [
            (call["target_version"], call["resource_type"], call["result"]) for call in label_kwargs(self.grant_count)
        ]

    def test_both_sides_succeed_synchronously(self):
        # 埋点不改变双写返回值
        self.assertEqual(self._grant(), (True, "success"))

        self.assertEqual(
            self._results(),
            [("v3", "collection", "succeeded"), ("v4", "collection", "succeeded")],
        )

    def test_v3_failure_is_recorded_without_blocking_v4(self):
        self.v3_writer.grant_resource_creator_actions.side_effect = RuntimeError("iam v3 unavailable")

        self.assertIsNone(self._grant())

        self.assertEqual(
            self._results(),
            [("v3", "collection", "failed"), ("v4", "collection", "succeeded")],
        )

    def test_v4_prepare_failure_is_a_terminal_result(self):
        self.v4_writer.prepare_resource_creator_actions.side_effect = ValueError("unsupported resource type")

        self.assertEqual(self._grant(), (True, "success"))

        self.assertEqual(
            self._results(),
            [("v3", "collection", "succeeded"), ("v4", "collection", "prepare_failed")],
        )
        self.dispatch.assert_not_called()

    def test_v4_sync_failure_and_dispatch_result_are_counted_separately(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")

        self.assertEqual(self._grant(), (True, "success"))

        # 同步失败与投递结果是两件事，各记一次，V4 同步失败率才能独立算出来
        self.assertEqual(
            self._results(),
            [
                ("v3", "collection", "succeeded"),
                ("v4", "collection", "sync_failed"),
                ("v4", "collection", "fallback_dispatched"),
            ],
        )

    def test_dispatch_failure_is_recorded_separately(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")
        self.dispatch.side_effect = RuntimeError("broker unavailable")

        self.assertEqual(self._grant(), (True, "success"))

        self.assertEqual(
            self._results(),
            [
                ("v3", "collection", "succeeded"),
                ("v4", "collection", "sync_failed"),
                ("v4", "collection", "dispatch_failed"),
            ],
        )

    def test_rolled_back_transaction_still_reports_the_sync_failure(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")

        with self.captureOnCommitCallbacks(execute=False):
            self.orchestrator.grant_creator_action(self.application)

        # 回滚时回落任务不投递，所以没有投递类结果；但同步失败已经发生，不能因回滚而丢样本，
        # 否则同一次调用里 V3 全额上报、V4 静默，失败率会系统性偏低。
        self.assertEqual(
            self._results(),
            [("v3", "collection", "succeeded"), ("v4", "collection", "sync_failed")],
        )
        self.dispatch.assert_not_called()

    def test_observer_failure_neither_breaks_the_grant_nor_the_commit_callback(self):
        observer = Mock(side_effect=RuntimeError("metrics backend unavailable"))
        orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer), ("v4", self.v4_writer)),
            tenant_id="tenant-1",
            operator="operator",
            grant_observer=observer,
            dispatch_retry_grant=self.dispatch,
        )
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")

        with self.captureOnCommitCallbacks(execute=True):
            result = orchestrator.grant_creator_action(self.application, raise_exception=True)

        # 观测是纯旁路：observer 抛异常既不能改变授权结果，也不能打断提交后回调
        self.assertEqual(result, (True, "success"))
        self.dispatch.assert_called_once()
        self.assertEqual(observer.call_count, 3)
