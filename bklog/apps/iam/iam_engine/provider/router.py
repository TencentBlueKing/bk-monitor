from __future__ import annotations

from typing import Protocol

from apps.iam.iam_engine.core.config import AuthMode
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
from apps.iam.iam_engine.provider.composition.union import UnionDecisionPolicy
from apps.iam.mode import InvalidIAMPermissionModeError


class ModeProvider(Protocol):
    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode: ...


class ModeRouter:
    def __init__(
        self,
        mode_provider: ModeProvider,
        v3_provider: PermissionProvider,
        v4_provider: PermissionProvider | None,
    ) -> None:
        self.mode_provider = mode_provider
        self.providers = {
            AuthMode.V3: v3_provider,
            AuthMode.V4: v4_provider,
        }

    def is_allowed(self, request: AuthRequest) -> AuthDecision:
        try:
            mode = self.mode_provider.get_mode(request.resources)
        except InvalidIAMPermissionModeError as error:
            return self._invalid_mode_decision(error)
        provider_modes = self._provider_modes(mode)
        results = tuple(self._call_provider(provider_mode, request) for provider_mode in provider_modes)
        if mode is AuthMode.UNION:
            return UnionDecisionPolicy.decide(results, mode=mode.value)
        return self._single_decision(results[0], mode)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthDecision:
        # 认为批量鉴权请求只会发生在单业务下
        resources = tuple(resource for resource_group in request.resource_groups for resource in resource_group)
        try:
            mode = self.mode_provider.get_mode(resources)
        except InvalidIAMPermissionModeError as error:
            return self._invalid_mode_batch_decision(request, error)
        provider_modes = self._provider_modes(mode)
        provider_results = {
            provider_mode: self._call_batch_provider(provider_mode, request) for provider_mode in provider_modes
        }
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

    def _call_provider(self, mode: AuthMode, request: AuthRequest) -> AuthResult:
        provider = self.providers[mode]
        if provider is None:
            return self._missing_provider(mode)
        return provider.is_allowed(request)

    def _call_batch_provider(self, mode: AuthMode, request: BatchAuthRequest) -> BatchAuthResult:
        provider = self.providers[mode]
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
    def _invalid_mode_result(error: InvalidIAMPermissionModeError) -> AuthResult:
        return AuthResult.error(
            provider_name="mode",
            reason=error.reason,
            error_type="InvalidPermissionMode",
        )

    def _invalid_mode_decision(self, error: InvalidIAMPermissionModeError) -> AuthDecision:
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
        error: InvalidIAMPermissionModeError,
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
        provider = self.providers[mode]
        if provider is None:
            return self._missing_provider(mode)
        return AuthResult.error(
            provider_name=mode.value,
            reason=f"missing batch result for action={action_id}, resource={resource_id}",
            error_type="IncompleteBatchResult",
        )
