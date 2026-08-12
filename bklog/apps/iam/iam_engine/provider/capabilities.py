from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class AuthorizationGrantState(str, Enum):
    """授权意图在通用状态机中的稳定状态值。"""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    UNKNOWN = "unknown"
    FAILED_FINAL = "failed_final"


class AuthorizationGrantTarget(str, Enum):
    """授权双写支持的目标版本。"""

    V3 = "v3"
    V4 = "v4"


class GrantFailureKind(str, Enum):
    """授权目标对失败结果的状态机分类。"""

    UNKNOWN = AuthorizationGrantState.UNKNOWN.value
    RETRY_WAIT = AuthorizationGrantState.RETRY_WAIT.value
    FAILED_FINAL = AuthorizationGrantState.FAILED_FINAL.value


@dataclass(frozen=True, slots=True)
class PreparedAuthorizationGrant:
    """可持久化并在补偿任务中原样重放的目标侧授权请求。"""

    payload: Mapping[str, Any] | list[Mapping[str, Any]]
    role_id: str = ""
    expired_at: int | None = None


class PermissionApplicationProvider(Protocol):
    """为单个 IAM 权限提供方生成无权限申请数据。"""

    def get_apply_data(
        self,
        actions: list[Any],
        resources: list[Any] | None = None,
    ) -> tuple[dict[str, Any], str]: ...


class AuthorizationWriter(Protocol):
    """向单个 IAM 权限提供方写入资源创建者授权。"""

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any: ...

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant: ...

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any: ...

    def classify_failure(self, error: Exception) -> GrantFailureKind: ...
