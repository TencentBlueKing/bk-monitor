from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthStatus(str, Enum):
    """Provider 返回的原始鉴权结果。"""

    ALLOW = "allow"
    DENY = "deny"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuthResult:
    """单个权限 Provider 返回的鉴权结果。"""

    status: AuthStatus
    provider_name: str
    reason: str = ""
    error_type: str = ""

    def __post_init__(self) -> None:
        if not self.provider_name:
            raise ValueError("provider_name must not be empty")
        if self.status is AuthStatus.ERROR and not self.reason:
            raise ValueError("error result must include a reason")
        if self.status is not AuthStatus.ERROR and self.error_type:
            raise ValueError("error_type is only valid for error results")

    @property
    def allowed(self) -> bool:
        return self.status is AuthStatus.ALLOW

    @classmethod
    def allow(cls, provider_name: str, reason: str = "") -> AuthResult:
        return cls(status=AuthStatus.ALLOW, provider_name=provider_name, reason=reason)

    @classmethod
    def deny(cls, provider_name: str, reason: str = "") -> AuthResult:
        return cls(status=AuthStatus.DENY, provider_name=provider_name, reason=reason)

    @classmethod
    def error(cls, provider_name: str, reason: str, error_type: str = "") -> AuthResult:
        return cls(
            status=AuthStatus.ERROR,
            provider_name=provider_name,
            reason=reason,
            error_type=error_type,
        )


@dataclass(frozen=True, slots=True)
class AuthDecision:
    """最终鉴权决策及其对应的 Provider 结果明细。"""

    allowed: bool
    provider_results: tuple[AuthResult, ...]
    hit_provider_names: tuple[str, ...] = ()
    degraded: bool = False
    mode: str = ""


@dataclass(frozen=True, slots=True)
class BatchAuthResultItem:
    action_id: str
    resource_id: str
    result: AuthResult


@dataclass(frozen=True, slots=True)
class BatchAuthResult:
    items: tuple[BatchAuthResultItem, ...] = ()

    def by_key(self) -> dict[tuple[str, str], AuthResult]:
        return {(item.action_id, item.resource_id): item.result for item in self.items}


@dataclass(frozen=True, slots=True)
class BatchAuthDecisionItem:
    action_id: str
    resource_id: str
    decision: AuthDecision


@dataclass(frozen=True, slots=True)
class BatchAuthDecision:
    items: tuple[BatchAuthDecisionItem, ...] = ()

    def as_allowed_dict(self) -> dict[str, dict[str, bool]]:
        result: dict[str, dict[str, bool]] = {}
        for item in self.items:
            result.setdefault(item.resource_id, {})[item.action_id] = item.decision.allowed
        return result


@dataclass(frozen=True, slots=True)
class AuthorizedResourceScope:
    """顶层资源范围查询结果。is_wildcard=True 时 ids 为空集合，表示覆盖全部本地候选。"""

    resource_type: str
    ids: frozenset[str] = frozenset()
    is_wildcard: bool = False
    provider_name: str = ""
    status: AuthStatus = AuthStatus.ALLOW
    reason: str = ""
    error_type: str = ""

    @classmethod
    def wildcard(cls, resource_type: str, *, provider_name: str = "") -> AuthorizedResourceScope:
        return cls(
            resource_type=resource_type,
            ids=frozenset(),
            is_wildcard=True,
            provider_name=provider_name,
            status=AuthStatus.ALLOW,
        )

    @classmethod
    def concrete(
        cls, resource_type: str, ids: set[str] | frozenset[str], *, provider_name: str = ""
    ) -> AuthorizedResourceScope:
        return cls(
            resource_type=resource_type,
            ids=frozenset(str(resource_id) for resource_id in ids),
            is_wildcard=False,
            provider_name=provider_name,
            status=AuthStatus.ALLOW,
        )

    @classmethod
    def empty(cls, resource_type: str, *, provider_name: str = "") -> AuthorizedResourceScope:
        return cls.concrete(resource_type, frozenset(), provider_name=provider_name)

    @classmethod
    def error(
        cls,
        resource_type: str,
        *,
        provider_name: str,
        reason: str,
        error_type: str = "",
    ) -> AuthorizedResourceScope:
        return cls(
            resource_type=resource_type,
            ids=frozenset(),
            is_wildcard=False,
            provider_name=provider_name,
            status=AuthStatus.ERROR,
            reason=reason,
            error_type=error_type,
        )

    @property
    def ok(self) -> bool:
        return self.status is not AuthStatus.ERROR
