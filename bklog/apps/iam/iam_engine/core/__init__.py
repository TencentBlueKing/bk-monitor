"""运行时值对象与鉴权配置。

本包只放「一次请求里流动的数据」，不放 V3/V4 协议细节。

- ``config.AuthMode``：运行时鉴权模式对外取值（v3 / v4 / union）
- ``config.DualStackSpec``：迁移期谁是旧栈、谁是新栈
- ``requests``：引擎入参（谁、什么动作、哪些资源）
- ``types``：Provider 三态结果与 Router 最终决策
"""

from apps.iam.iam_engine.core.config import DEFAULT_DUAL_STACK, AuthMode, DualStackSpec
from apps.iam.iam_engine.core.types import AuthDecision, AuthResult, AuthStatus

__all__ = [
    "AuthDecision",
    "AuthMode",
    "AuthResult",
    "AuthStatus",
    "DEFAULT_DUAL_STACK",
    "DualStackSpec",
]
