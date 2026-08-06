from __future__ import annotations


class InvalidAuthModeError(Exception):
    """鉴权模式配置非法，调用方应拒绝鉴权。"""

    def __init__(self, mode_value: str, reason: str) -> None:
        self.mode_value = mode_value
        self.reason = reason
        super().__init__(reason)
