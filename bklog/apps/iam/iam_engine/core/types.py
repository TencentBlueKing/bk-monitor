from __future__ import annotations

# ---------------------------------------------------------------------------
# 运行时结果对象
#
# AuthResult 是单个 Provider 的原始输出，必须保留 ALLOW / DENY / ERROR 三态，
# 不能在方言层先压成 bool——union 需要区分「明确拒绝」和「依赖故障」。
# AuthDecision 才是 ModeRouter 合并后的最终决策，业务门面通常只读 allowed。
#
# 全部 frozen：一次决策在观测、申请回退、日志之间传递时不能被改写。
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from enum import Enum


class AuthStatus(str, Enum):
    """Provider 返回的原始鉴权结果，禁止在 Provider 内部再合并。"""

    ALLOW = "allow"
    DENY = "deny"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuthResult:
    """单个权限 Provider 返回的鉴权结果。

    ERROR 必须带 reason；error_type 只给指标/日志分类，不要拿去拼前端文案。
    allowed 只在 ALLOW 时为 True，DENY 与 ERROR 都是 False，避免调用方漏看 degraded。
    """

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
    """ModeRouter 合并后的最终决策。

    hit_provider_names 只包含明确 ALLOW 的一侧，供 union 分歧指标使用。
    degraded 表示至少一侧 ERROR；allowed 仍可能为 True（另一侧放行）。
    mode 可能是非法 Toggle 原值，观测时要先归一，不能直接当 Prometheus label。
    """

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
    """顶层资源范围查询结果，供「我的空间」列表使用。

    is_wildcard=True 时 ids 必须为空：表示覆盖全部本地候选，而不是「一个都没有」。
    空范围请用 empty()，错误请用 error()，不要把失败伪装成空拒绝。
    """

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
