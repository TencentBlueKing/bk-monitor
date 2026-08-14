from __future__ import annotations

from collections.abc import Iterable

from apps.iam.iam_engine.core.types import AuthDecision, AuthResult, AuthorizedResourceScope, AuthStatus


class UnionDecisionPolicy:
    """只要至少一个 Provider 明确允许请求，Union 决策就允许请求。"""

    @staticmethod
    def decide(results: Iterable[AuthResult], mode: str = "union") -> AuthDecision:
        provider_results = tuple(results)
        hit_provider_names = tuple(result.provider_name for result in provider_results if result.allowed)

        return AuthDecision(
            allowed=bool(hit_provider_names),
            provider_results=provider_results,
            hit_provider_names=hit_provider_names,
            degraded=any(result.status is AuthStatus.ERROR for result in provider_results),
            mode=mode,
        )


class UnionScopePolicy:
    """把多个 Provider 的授权范围合并为一个范围，与 UnionDecisionPolicy.decide 对称。

    单侧失败降级为使用另一侧的结果，全部失败才 fail-closed 返回错误范围。
    """

    @staticmethod
    def merge(scopes: Iterable[AuthorizedResourceScope], provider_name: str = "union") -> AuthorizedResourceScope:
        provider_scopes = tuple(scopes)
        if not provider_scopes:
            raise ValueError("at least one authorized resource scope is required")

        resource_type = next(
            (scope.resource_type for scope in provider_scopes if scope.resource_type),
            "",
        )
        failed = tuple(scope for scope in provider_scopes if not scope.ok)
        if len(failed) == len(provider_scopes):
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=provider_name,
                reason="; ".join(f"{scope.provider_name or 'unknown'}={scope.reason}" for scope in failed),
                error_type="; ".join(scope.error_type for scope in failed if scope.error_type),
            )

        allowed_scopes = tuple(scope for scope in provider_scopes if scope.ok)
        if any(scope.is_wildcard for scope in allowed_scopes):
            return AuthorizedResourceScope.wildcard(resource_type, provider_name=provider_name)

        merged_ids: set[str] = set()
        for scope in allowed_scopes:
            merged_ids.update(scope.ids)
        return AuthorizedResourceScope.concrete(resource_type, merged_ids, provider_name=provider_name)
