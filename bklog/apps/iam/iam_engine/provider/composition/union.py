from __future__ import annotations

from collections.abc import Iterable

from apps.iam.iam_engine.core.types import AuthDecision, AuthResult, AuthorizedResourceScope, AuthStatus


class UnionDecisionPolicy:
    """union 鉴权：只要一侧明确 ALLOW 就放行。

    ERROR 不会单独否决请求，只会把 AuthDecision.degraded 置 True。
    两侧都不是 ALLOW（DENY 或 ERROR）才拒绝。这是迁移期「旧权限或新权限任一即可」
    的产品语义，不要改成 AllOf，否则灰度用户会被尚未同步的一侧卡住。
    """

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
    """空间范围的 union：与鉴权对称，并集可见；单侧失败用另一侧，双侧失败才 fail-closed。

    一侧 wildcard 即视为全部可见。不要把 ERROR 范围并进 ids，否则超时会被当成「一个空间都没有」。
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
