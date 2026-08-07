from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, TypeVar

from apps.iam.backends.v4.concurrency import run_pair_concurrently
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance
from apps.iam.iam_engine.core.types import (
    AuthDecision,
    AuthResult,
    AuthStatus,
    BatchAuthDecision,
    BatchAuthDecisionItem,
    BatchAuthResult,
)
from apps.iam.iam_engine.provider.base import PermissionProvider
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.composition.union import UnionDecisionPolicy

T = TypeVar("T")


class ModeProvider(Protocol):
    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode: ...


class ModeRouter:
    def __init__(
        self,
        mode_provider: ModeProvider,
        bundles: Mapping[AuthMode, ProviderBundle],
    ) -> None:
        self.mode_provider = mode_provider
        self.bundles = dict(bundles)

    def is_allowed(self, request: AuthRequest) -> AuthDecision:
        try:
            mode = self.mode_provider.get_mode(request.resources)
        except InvalidAuthModeError as error:
            return self._invalid_mode_decision(error)
        provider_modes = self._provider_modes(mode)
        results = self._map_providers(
            provider_modes,
            lambda provider_mode: self._call_provider(provider_mode, request),
        )
        if mode is AuthMode.UNION:
            return UnionDecisionPolicy.decide(results, mode=mode.value)
        return self._single_decision(results[0], mode)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthDecision:
        # 认为批量鉴权请求只会发生在单业务下
        resources = tuple(resource for resource_group in request.resource_groups for resource in resource_group)
        try:
            mode = self.mode_provider.get_mode(resources)
        except InvalidAuthModeError as error:
            return self._invalid_mode_batch_decision(request, error)
        provider_modes = self._provider_modes(mode)
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

    @staticmethod
    def _provider_modes(mode: AuthMode) -> tuple[AuthMode, ...]:
        if mode is AuthMode.UNION:
            return AuthMode.V3, AuthMode.V4
        return (mode,)

    @staticmethod
    def _map_providers(
        provider_modes: tuple[AuthMode, ...],
        call: Callable[[AuthMode], T],
    ) -> tuple[T, ...]:
        """按 provider_modes 顺序调用；union 双栈时并行执行。"""
        if len(provider_modes) == 1:
            return (call(provider_modes[0]),)
        left_mode, right_mode = provider_modes
        left, right = run_pair_concurrently(
            lambda: call(left_mode),
            lambda: call(right_mode),
        )
        return (left, right)

    def _auth_provider(self, mode: AuthMode) -> PermissionProvider | None:
        bundle = self.bundles.get(mode)
        if bundle is None:
            return None
        return bundle.auth

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
