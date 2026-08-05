from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


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
