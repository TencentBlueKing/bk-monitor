from abc import ABC, abstractmethod
from typing import ClassVar

from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult


class PermissionProvider(ABC):
    """权限后端需要实现的通用契约。"""

    name: ClassVar[str]

    @abstractmethod
    def is_allowed(self, request: AuthRequest) -> AuthResult:
        """返回允许、拒绝或 Provider 错误，不合并不同结果状态。"""

    @abstractmethod
    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        """为每个请求的动作和资源返回一个 Provider 结果。"""
