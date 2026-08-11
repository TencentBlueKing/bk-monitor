from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PreparedAuthorizationGrant:
    """可持久化并在补偿任务中原样重放的目标侧授权请求。"""

    payload: Mapping[str, Any] | list[Mapping[str, Any]]
    role_id: str = ""
    expired_at: int | None = None


class PermissionApplicationProvider(Protocol):
    """为单个 IAM Provider 生成无权限申请数据。"""

    def get_apply_data(
        self,
        actions: list[Any],
        resources: list[Any] | None = None,
    ) -> tuple[dict[str, Any], str]: ...


class AuthorizationWriter(Protocol):
    """向单个 IAM Provider 写入资源创建者授权。"""

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any: ...

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant: ...

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any: ...
