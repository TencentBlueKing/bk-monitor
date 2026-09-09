from __future__ import annotations


class InvalidAuthModeError(Exception):
    """鉴权模式配置非法，调用方应拒绝鉴权。

    这不是「回退 legacy 继续放行」的信号。ModeRouter / 空间过滤必须 fail-closed；
    只有生成申请数据这种旁路才可以用 AuthMode.safe_coerce 兜底，避免 403 变成 500。

    Attributes:
        mode_value: 环境变量、Toggle 或决策里带出来的原始字符串，可能根本不是 v3/v4/union。
        reason: 给日志和指标用的人类可读原因，不要回传给前端。
    """

    def __init__(self, mode_value: str, reason: str) -> None:
        self.mode_value = mode_value
        self.reason = reason
        super().__init__(reason)
