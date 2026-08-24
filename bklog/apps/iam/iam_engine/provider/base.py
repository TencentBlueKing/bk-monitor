from abc import ABC, abstractmethod
from typing import ClassVar

from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult


class PermissionProvider(ABC):
    """单个 IAM 协议栈的鉴权契约。

    实现方只负责「问这一代权限中心」：编码方言、发请求、把响应映射成三态。
    不要在这里做 union 合并、申请选边或创建者双写——那些属于 ModeRouter / MigrationPolicy。

    is_allowed 失败必须返回 AuthResult.error，不要抛给 Router 变成未捕获异常；
    也不要把 ERROR 先压成 DENY，否则 union 无法区分策略拒绝和依赖故障。
    """

    name: ClassVar[str]

    @abstractmethod
    def is_allowed(self, request: AuthRequest) -> AuthResult:
        """返回允许、拒绝或 Provider 错误，不合并不同结果状态。"""

    @abstractmethod
    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        """为每个 (action_id, resource_id) 返回一条 Provider 结果，缺项由 Router 补 ERROR。"""
