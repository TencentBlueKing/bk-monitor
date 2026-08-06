from __future__ import annotations

from enum import Enum


class AuthMode(str, Enum):
    V3 = "v3"
    V4 = "v4"
    UNION = "union"

    @classmethod
    def safe_coerce(cls, value: AuthMode | str, *, default: AuthMode | None = None) -> AuthMode:
        """尽力将任意值转换为合法鉴权模式；非法值安全回退到 default（默认 V3），不抛出 ValueError。

        用于处理已经越过 FeatureToggle 校验、但仍可能是非法值的场景（例如 AuthDecision.mode
        在非法模式下被写入原始非法字符串），确保鉴权模式解析永远不会向上抛出未捕获异常。
        """

        fallback = default if default is not None else cls.V3
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            return fallback
