from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

# ---------------------------------------------------------------------------
# 可选能力协议
#
# 不是每个 Provider 都要实现全部槽位。申请、范围查询、写入拆开，
# 由操作所需能力和模式决定装配目标；所选目标缺少能力时明确失败，不切换协议。
# ---------------------------------------------------------------------------

from iam_engine.core.types import AuthorizedResourceScope


@dataclass(frozen=True, slots=True)
class PreparedAuthorizationGrant:
    """一次同步授权的目标侧请求与有效期。"""

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
    """向单个 IAM 权限提供方写入授权。

    ``grant_resource_creator_actions`` 同步完成请求构造与一次写入。
    Writer 可通过 ``prepare_resource_creator_actions`` / ``grant_prepared`` 组织内部请求。

    ``grant_space_access`` 是独立能力：空间不是新建实例，两代协议的授权入口完全不同
    （legacy 调权限中心实例授权 API，current 授最小空间访问角色），因此不走创建者授权的
    冻结 / 重试编排，失败由调用方按主体汇总上报。
    """

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any: ...

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant: ...

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any: ...

    def grant_space_access(self, *, space_id: str, subject_id: str, space_name: str = "") -> Any: ...
