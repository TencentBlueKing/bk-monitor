from __future__ import annotations

from collections.abc import Iterable

from apps.iam.iam_engine.core.types import AuthDecision, AuthResult, AuthStatus


class UnionDecisionPolicy:
    """Allow when at least one provider explicitly allows the request."""

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
