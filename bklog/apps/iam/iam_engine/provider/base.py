from abc import ABC, abstractmethod
from typing import ClassVar

from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult


class PermissionProvider(ABC):
    """Common contract implemented by permission backends."""

    name: ClassVar[str]

    @abstractmethod
    def is_allowed(self, request: AuthRequest) -> AuthResult:
        """Return allow, deny, or provider error without collapsing states."""

    @abstractmethod
    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        """Return one provider result for every requested action and resource."""
