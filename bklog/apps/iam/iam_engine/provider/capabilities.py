from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Protocol

from apps.iam.iam_engine.core.types import AuthorizedResourceScope


class GrantFailureKind(str, Enum):
    """授权目标对失败结果的分类，决定失败后是否值得重试。"""

    UNKNOWN = "unknown"
    RETRY_WAIT = "retry_wait"
    FAILED_FINAL = "failed_final"


@dataclass(frozen=True, slots=True)
class PreparedAuthorizationGrant:
    """可在重试任务中原样重放的目标侧授权请求。"""

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


class AuthorizedScopeProvider(Protocol):
    """查询主体在某个动作下被授权的顶层资源范围。"""

    # 无法只凭 IAM 返回值给出完整范围、必须由调用方提供候选 ID 的 Provider 置为 True。
    # 调用方据此决定是否要在查询 IAM 之前先加载全量候选。
    requires_candidate_ids: ClassVar[bool]

    def list_authorized_resources(
        self,
        *,
        action_id: str,
        resource_type: str = "space",
        subject: dict[str, str] | None = None,
        candidate_ids: frozenset[str] | None = None,
    ) -> AuthorizedResourceScope: ...


class AuthorizationWriter(Protocol):
    """向单个 IAM 权限提供方写入资源创建者授权。

    同步目标直接调用 ``grant_resource_creator_actions``；需要延后执行的目标先用
    ``prepare_resource_creator_actions`` 冻结请求，再由目标侧的重试任务重放。
    """

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any: ...

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant: ...

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any: ...
