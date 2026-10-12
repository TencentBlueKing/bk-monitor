from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.codec import BKLOG_ROOT_RESOURCE_TYPE_ID
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import (
    V4ClientError,
    V4RateLimitError,
    V4ResponseError,
    V4TimeoutError,
    V4TransportError,
)
from apps.iam.grant_config import AuthorizationGrantConfig
from apps.iam.iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant


# 日志平台 IAM V4 权限矩阵（iWiki 4029400600，2026-08-12 核对）确认了三类子资源的
# space_operator 分支；05 需求决定创建后自动授予对应分支，且只绑定新建实例，不扩大到空间范围。
CREATOR_ROLE_BY_RESOURCE_TYPE = {
    "collection": "space_operator",
    "indices": "space_operator",
    "es_source": "space_operator",
}

# 创建者授权只绑定新建实例、不带空间祖先，因此拿到子资源权限的人仍然没有 view_business，
# 而日志平台的检索入口一律先校验业务访问。空间访问必须用只含 view_business 的最小角色单独授予
# （iWiki 4029400600 第 7 节的 space_access），不能换成 space_viewer：
# 后者的 indices / collection 分支会把整个空间的检索与采集查看一起授出去。
SPACE_ACCESS_ROLE_ID = "space_access"


class UnsupportedV4GrantResource(ValueError):
    """资源类型没有确定的 IAM V4 角色映射。"""


class V4AuthorizationWriter:
    """将资源创建者授权转换为 IAM V4 单实例角色授权。"""

    def __init__(self, client: V4Client, *, operator: str) -> None:
        self.client = client
        self.operator = operator

    @classmethod
    def from_settings(cls, *, username: str, bk_tenant_id: str) -> V4AuthorizationWriter:
        return cls(
            V4Client(V4Options.from_settings(), username=username, bk_tenant_id=bk_tenant_id),
            operator=username,
        )

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant:
        resource_type = str(application.get("type") or "")
        role_id = CREATOR_ROLE_BY_RESOURCE_TYPE.get(resource_type)
        if role_id is None:
            raise UnsupportedV4GrantResource(f"unsupported IAM V4 creator grant resource type: {resource_type}")

        frozen_expired_at = self._resolve_expired_at(expired_at)
        item = {
            "subject": {"type": "user", "id": str(application["creator"])},
            "role_id": role_id,
            "related_resource_type_id": resource_type,
            # 这里只授权新建实例本身，不能带空间祖先，否则语义会扩大到空间范围。
            "resources": [{"type": resource_type, "id": str(application["id"])}],
            "expired_at": frozen_expired_at,
        }
        return PreparedAuthorizationGrant(payload=[item], role_id=role_id, expired_at=frozen_expired_at)

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> None:
        self.client.add_authorization(items=list(grant.payload), operator=self.operator)

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> None:
        self.grant_prepared(self.prepare_resource_creator_actions(application))

    def grant_space_access(self, *, space_id: str, subject_id: str, space_name: str = "") -> None:
        """为主体授予最小空间访问角色。

        space_name 只有 V3 的实例授权接口需要，V4 按资源 ID 授权，这里忽略。
        有效期与创建者授权取同一配置，避免业务访问比资源权限先到期、owner 又被挡在业务外。
        """
        del space_name

        item = {
            "subject": {"type": "user", "id": str(subject_id)},
            "role_id": SPACE_ACCESS_ROLE_ID,
            "related_resource_type_id": BKLOG_ROOT_RESOURCE_TYPE_ID,
            # 负数空间 ID 由 client 按 codec 编码成 neg_<id>，这里保持本地原值
            "resources": [{"type": BKLOG_ROOT_RESOURCE_TYPE_ID, "id": str(space_id)}],
            "expired_at": self._resolve_expired_at(),
        }
        self.client.add_authorization(items=[item], operator=self.operator)

    @staticmethod
    def _resolve_expired_at(expired_at: int | None = None) -> int:
        """授权有效期的唯一出处：显式传入优先，否则按配置从当前时间顺延。"""
        if expired_at:
            return expired_at

        grant_config = AuthorizationGrantConfig.from_settings()
        return int((timezone.now() + timedelta(days=grant_config.v4_expire_days)).timestamp())

    @staticmethod
    def classify_failure(error: Exception) -> GrantFailureKind:
        if isinstance(error, V4TimeoutError | V4TransportError):
            # add_authorization 的生产契约没有幂等键；05 需求决定 UNKNOWN 可按冻结请求重试，
            # 重复授予同一主体、角色和资源可接受，但不得重新计算 expired_at。
            return GrantFailureKind.UNKNOWN
        if isinstance(error, V4RateLimitError):
            return GrantFailureKind.RETRY_WAIT
        if isinstance(error, V4ResponseError | ValueError):
            return GrantFailureKind.FAILED_FINAL
        if isinstance(error, V4ClientError):
            status_code = error.status_code or 0
            if status_code >= 500:
                return GrantFailureKind.RETRY_WAIT
            if 400 <= status_code < 500:
                return GrantFailureKind.FAILED_FINAL
        return GrantFailureKind.RETRY_WAIT
