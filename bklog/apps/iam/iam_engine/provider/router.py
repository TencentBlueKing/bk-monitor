from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar

from apps.iam.iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance
from apps.iam.iam_engine.core.types import (
    AuthDecision,
    AuthResult,
    AuthStatus,
    AuthorizedResourceScope,
    BatchAuthDecision,
    BatchAuthDecisionItem,
    BatchAuthResult,
)
from apps.iam.iam_engine.provider.base import PermissionProvider
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import AuthorizedScopeProvider
from apps.iam.iam_engine.provider.composition.union import UnionDecisionPolicy, UnionScopePolicy
from apps.iam.iam_engine.provider.execution import PairExecutor

# ---------------------------------------------------------------------------
# ModeRouter —— 按 Toggle 选择单栈或双栈
#
# 不在这里写死 V3/V4：union 成员来自 DualStackSpec.modes_for。
# 非法 Toggle 必须返回 degraded + 拒绝，不能回退 V3 继续鉴权。
# 批量路径整批共用一次 get_mode，避免同一请求里一半走 V3、一半走 V4。
# 空间范围走 Bundle.scope，缺能力返回错误范围，不对 auth 做鸭子调用。
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ModeProvider(Protocol):
    """解析当前鉴权模式。resources 预留给按空间灰度，当前 Feature Toggle 实现会忽略它。"""

    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode: ...


@dataclass(frozen=True, slots=True)
class ScopeResolution:
    """范围查询的路由结果。

    scope 是单栈原值或 union 并集；provider_scopes 保留各侧原始结果，
    给门面打降级指标和 warning，不要在 Router 里依赖 Django 日志。
    """

    scope: AuthorizedResourceScope
    provider_scopes: tuple[AuthorizedResourceScope, ...]
    mode: AuthMode


class ModeRouter:
    """把一次引擎请求路由到拓扑指定的 Provider，并合并鉴权决策或授权范围。"""

    def __init__(
        self,
        mode_provider: ModeProvider,
        bundles: Mapping[AuthMode, ProviderBundle],
        *,
        pair_executor: PairExecutor,
        stack: DualStackSpec | None = None,
    ) -> None:
        self.mode_provider = mode_provider
        self.bundles = dict(bundles)
        self.pair_executor = pair_executor
        self.stack = stack or DEFAULT_DUAL_STACK

    def is_allowed(self, request: AuthRequest) -> AuthDecision:
        """单点鉴权。union 两侧都跑完再合并，不做短路，便于观测两侧分歧。"""

        try:
            mode = self.mode_provider.get_mode(request.resources)
        except InvalidAuthModeError as error:
            return self._invalid_mode_decision(error)
        provider_modes = self.stack.modes_for(mode)
        results = self._map_providers(
            provider_modes,
            lambda provider_mode: self._call_provider(provider_mode, request),
        )
        if mode is AuthMode.UNION:
            return UnionDecisionPolicy.decide(results, mode=mode.value)
        return self._single_decision(results[0], mode)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthDecision:
        # 当前批量入口都来自同一业务下的资源列表，整批共用一次模式解析。
        resources = tuple(resource for resource_group in request.resource_groups for resource in resource_group)
        try:
            mode = self.mode_provider.get_mode(resources)
        except InvalidAuthModeError as error:
            return self._invalid_mode_batch_decision(request, error)
        provider_modes = self.stack.modes_for(mode)
        provider_result_list = self._map_providers(
            provider_modes,
            lambda provider_mode: self._call_batch_provider(provider_mode, request),
        )
        provider_results = dict(zip(provider_modes, provider_result_list, strict=True))
        provider_result_maps = {mode_: result.by_key() for mode_, result in provider_results.items()}

        items = []
        for action_id, resource_id in request.iter_keys():
            results = []
            for provider_mode in provider_modes:
                result = provider_result_maps[provider_mode].get((action_id, resource_id))
                if result is None:
                    result = self._missing_batch_item(provider_mode, action_id, resource_id)
                results.append(result)
            decision = (
                UnionDecisionPolicy.decide(tuple(results), mode=mode.value)
                if mode is AuthMode.UNION
                else self._single_decision(results[0], mode)
            )
            items.append(BatchAuthDecisionItem(action_id, resource_id, decision))
        return BatchAuthDecision(items=tuple(items))

    def scope_providers_for(self, mode: AuthMode) -> tuple[tuple[str, AuthorizedScopeProvider | None], ...]:
        """按拓扑取出参与范围查询的 Provider；缺 Bundle 或缺 scope 槽都记为 None。"""

        providers = []
        for provider_mode in self.stack.modes_for(mode):
            bundle = self.bundles.get(provider_mode)
            scope = bundle.scope if bundle is not None else None
            providers.append((provider_mode.value, scope))
        return tuple(providers)

    def list_authorized_scope(
        self,
        mode: AuthMode,
        *,
        action_id: str,
        resource_type: str,
        subject: dict[str, str] | None = None,
        candidate_ids: frozenset[str] | None = None,
    ) -> ScopeResolution:
        """查询授权范围。缺 scope 能力返回错误范围，不打 auth 的鸭子方法。"""

        provider_modes = self.stack.modes_for(mode)
        scopes = self._map_providers(
            provider_modes,
            lambda provider_mode: self._call_scope_provider(
                provider_mode,
                action_id=action_id,
                resource_type=resource_type,
                subject=subject,
                candidate_ids=candidate_ids,
            ),
        )
        merged = UnionScopePolicy.merge(scopes) if mode is AuthMode.UNION else scopes[0]
        return ScopeResolution(scope=merged, provider_scopes=scopes, mode=mode)

    def _map_providers(
        self,
        provider_modes: tuple[AuthMode, ...],
        call: Callable[[AuthMode], T],
    ) -> tuple[T, ...]:
        """按 provider_modes 顺序调用；双栈时交给 pair_executor 并行。

        迁移期永远是一对协议，所以这里只接受 1 或 2 路。需要 N 路时先改 DualStackSpec，
        不要在调用方绕过本方法自己起线程池。
        """
        if len(provider_modes) == 1:
            return (call(provider_modes[0]),)
        if len(provider_modes) != 2:
            raise ValueError("dual-stack union expects exactly two provider modes")
        left_mode, right_mode = provider_modes
        left, right = self.pair_executor(
            lambda: call(left_mode),
            lambda: call(right_mode),
        )
        return (left, right)

    def _auth_provider(self, mode: AuthMode) -> PermissionProvider | None:
        bundle = self.bundles.get(mode)
        if bundle is None:
            return None
        return bundle.auth

    def _scope_provider(self, mode: AuthMode) -> AuthorizedScopeProvider | None:
        bundle = self.bundles.get(mode)
        if bundle is None:
            return None
        return bundle.scope

    def _call_scope_provider(
        self,
        mode: AuthMode,
        *,
        action_id: str,
        resource_type: str,
        subject: dict[str, str] | None,
        candidate_ids: frozenset[str] | None,
    ) -> AuthorizedResourceScope:
        provider = self._scope_provider(mode)
        if provider is None:
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=mode.value,
                reason=f"IAM {mode.value} provider is not configured",
                error_type="ProviderNotConfigured",
            )
        return provider.list_authorized_resources(
            action_id=action_id,
            resource_type=resource_type,
            subject=subject,
            candidate_ids=candidate_ids,
        )

    def _call_provider(self, mode: AuthMode, request: AuthRequest) -> AuthResult:
        provider = self._auth_provider(mode)
        if provider is None:
            return self._missing_provider(mode)
        return provider.is_allowed(request)

    def _call_batch_provider(self, mode: AuthMode, request: BatchAuthRequest) -> BatchAuthResult:
        provider = self._auth_provider(mode)
        if provider is None:
            return BatchAuthResult()
        return provider.batch_is_allowed(request)

    @staticmethod
    def _single_decision(result: AuthResult, mode: AuthMode) -> AuthDecision:
        return AuthDecision(
            allowed=result.allowed,
            provider_results=(result,),
            hit_provider_names=(result.provider_name,) if result.allowed else (),
            degraded=result.status is AuthStatus.ERROR,
            mode=mode.value,
        )

    @staticmethod
    def _invalid_mode_result(error: InvalidAuthModeError) -> AuthResult:
        return AuthResult.error(
            provider_name="mode",
            reason=error.reason,
            error_type="InvalidPermissionMode",
        )

    def _invalid_mode_decision(self, error: InvalidAuthModeError) -> AuthDecision:
        result = self._invalid_mode_result(error)
        return AuthDecision(
            allowed=False,
            provider_results=(result,),
            hit_provider_names=(),
            degraded=True,
            mode=error.mode_value,
        )

    def _invalid_mode_batch_decision(
        self,
        request: BatchAuthRequest,
        error: InvalidAuthModeError,
    ) -> BatchAuthDecision:
        return BatchAuthDecision(
            items=tuple(
                BatchAuthDecisionItem(action_id, resource_id, self._invalid_mode_decision(error))
                for action_id, resource_id in request.iter_keys()
            )
        )

    @staticmethod
    def _missing_provider(mode: AuthMode) -> AuthResult:
        return AuthResult.error(
            provider_name=mode.value,
            reason=f"IAM {mode.value} provider is not configured",
            error_type="ProviderNotConfigured",
        )

    def _missing_batch_item(self, mode: AuthMode, action_id: str, resource_id: str) -> AuthResult:
        provider = self._auth_provider(mode)
        if provider is None:
            return self._missing_provider(mode)
        return AuthResult.error(
            provider_name=mode.value,
            reason=f"missing batch result for action={action_id}, resource={resource_id}",
            error_type="IncompleteBatchResult",
        )
