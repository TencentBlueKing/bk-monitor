from __future__ import annotations

# ---------------------------------------------------------------------------
# 鉴权模式 vs 双栈拓扑
#
# AuthMode 是运维可改的鉴权模式取值（环境变量优先，否则 Feature Toggle），对外仍是协议名 + union。
# DualStackSpec 只描述「这一对里谁旧谁新」，不要在 ModeRouter 里写死 V3/V4。
#
# 换代不是只改 DEFAULT_DUAL_STACK：要同时改枚举成员、默认拓扑和 Bundle 注入。
# 退出的协议名会离开 valid_mode_values，库里旧 Toggle（例如 mode=v3）将 fail-closed。
#
# union 不是第三套协议，只是同时跑 legacy 与 current。
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from enum import Enum


class AuthMode(str, Enum):
    """运行时鉴权模式。值会进环境变量、Feature Toggle、指标 label 和 AuthDecision.mode。"""

    V3 = "v3"
    V4 = "v4"
    UNION = "union"


@dataclass(frozen=True, slots=True)
class DualStackSpec:
    """迁移期双栈拓扑：legacy 是仍在服役的旧协议，current 是正在切入的新协议。

    Feature Toggle 对外仍是协议名 + union；本结构只描述「这一对里谁旧谁新」。
    从 V4 迁到 V5 时，要同时给 ``AuthMode`` 加成员、改 ``DEFAULT_DUAL_STACK``、
    给 current 注入新 Bundle。ModeRouter / MigrationPolicy / DualWrite 不用再抄版本字面量，
    但退出的协议名会变成非法配置，不是「历史字面量继续合法」。

    Args:
        legacy: 旧协议对应的 AuthMode，默认 v3。不能是 union。
        current: 新协议对应的 AuthMode，默认 v4。不能与 legacy 相同。
    """

    legacy: AuthMode = AuthMode.V3
    current: AuthMode = AuthMode.V4

    def __post_init__(self) -> None:
        if self.legacy is AuthMode.UNION or self.current is AuthMode.UNION:
            raise ValueError("union is a composition mode, not a protocol stack")
        if self.legacy is self.current:
            raise ValueError("legacy and current must be different auth modes")

    def modes_for(self, mode: AuthMode) -> tuple[AuthMode, ...]:
        """单栈只跑自身；union 按 (legacy, current) 顺序同时跑两侧。

        顺序要稳定：观测、pair_executor 左右路、空间范围合并都依赖这个顺序。
        """

        if mode is AuthMode.UNION:
            return (self.legacy, self.current)
        return (mode,)

    def application_candidates(self, mode: AuthMode) -> tuple[AuthMode, ...]:
        """无权限申请的选边顺序。

        current / union 固定生成新协议申请单，缺少能力时不能回退 legacy。
        legacy 单栈只用自身，避免 V3 模式误发 V4 单。
        """

        if mode is AuthMode.UNION or mode is self.current:
            return (self.current,)
        return (mode,)

    @property
    def fallback_mode(self) -> AuthMode:
        """环境变量未设置且 Toggle 缺失、读库失败、feature_config 未写 mode 时的安全默认。

        回退 legacy：旧栈仍在服役，比默认切到正在切入的 current 更安全。
        """

        return self.legacy

    @property
    def valid_mode_values(self) -> frozenset[str]:
        """环境变量和 Feature Toggle 允许的取值：当前拓扑两侧协议 + union。

        枚举里加 V5 不会自动合法；必须改 ``DEFAULT_DUAL_STACK`` 或注入新 spec。
        spec 也不能发明尚未登记的枚举成员。拓扑切走后，退出的协议名会变成非法配置。
        """

        return frozenset({self.legacy.value, self.current.value, AuthMode.UNION.value})


DEFAULT_DUAL_STACK = DualStackSpec()
