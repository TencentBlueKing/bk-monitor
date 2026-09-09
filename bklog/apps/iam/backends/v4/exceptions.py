from __future__ import annotations


class V4ClientError(Exception):
    """IAM V4 客户端异常的基类。"""

    error_type: str = "V4ClientError"

    def __init__(self, reason: str, *, status_code: int | None = None) -> None:
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


class V4TimeoutError(V4ClientError):
    error_type = "TimeoutError"


class V4RateLimitError(V4ClientError):
    error_type = "RateLimitError"


class V4ResponseError(V4ClientError):
    error_type = "InvalidResponse"


class V4TransportError(V4ClientError):
    error_type = "TransportError"
