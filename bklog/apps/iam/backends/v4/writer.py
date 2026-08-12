from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.iam.backends.v4.client import V4Client
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

        frozen_expired_at = expired_at
        if not frozen_expired_at:
            grant_config = AuthorizationGrantConfig.from_settings()
            frozen_expired_at = int((timezone.now() + timedelta(days=grant_config.v4_expire_days)).timestamp())
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
