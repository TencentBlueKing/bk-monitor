from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings

from apps.iam.backends.v4.gateway import resolve_v4_gateway_url

# IAM V4 开放 API 路径默认值；特殊环境可通过 Django settings 覆盖。
DEFAULT_AUTH_PATH = "api/v1/open/rbac/authorization/systems/{system_id}/auth/"
DEFAULT_AUTH_BY_RESOURCES_PATH = "api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/"
DEFAULT_APPLY_URL_PATH = "api/v1/open/application/permission-apply-urls/"
DEFAULT_BATCH_CHUNK_SIZE = 100
MAX_BATCH_CHUNK_SIZE = 100

logger = logging.getLogger("iam.v4.config")


def normalize_batch_chunk_size(value: int | str | None) -> int:
    """按 IAM V4 当前批量接口约束归一化资源分片大小。"""
    try:
        configured = int(value) if value is not None else DEFAULT_BATCH_CHUNK_SIZE
    except (TypeError, ValueError):
        logger.warning(
            "invalid BK_IAM_V4_BATCH_CHUNK_SIZE=%r, falling back to %s",
            value,
            DEFAULT_BATCH_CHUNK_SIZE,
        )
        return DEFAULT_BATCH_CHUNK_SIZE

    if configured <= 0:
        logger.warning(
            "invalid BK_IAM_V4_BATCH_CHUNK_SIZE=%s, falling back to %s",
            configured,
            DEFAULT_BATCH_CHUNK_SIZE,
        )
        return DEFAULT_BATCH_CHUNK_SIZE

    if configured > MAX_BATCH_CHUNK_SIZE:
        logger.warning(
            "BK_IAM_V4_BATCH_CHUNK_SIZE=%s exceeds IAM V4 contract limit %s, using %s",
            configured,
            MAX_BATCH_CHUNK_SIZE,
            MAX_BATCH_CHUNK_SIZE,
        )
        return MAX_BATCH_CHUNK_SIZE

    return configured


@dataclass(frozen=True, slots=True)
class V4Options:
    app_code: str
    app_secret: str
    gateway_url: str
    system_id: str
    timeout_seconds: float
    batch_chunk_size: int
    auth_path: str
    auth_by_resources_path: str
    apply_url_path: str

    @classmethod
    def from_settings(cls, *, bk_tenant_id: str = "") -> V4Options:
        del bk_tenant_id  # 租户信息通过每次请求的请求头传递，不放入选项
        system_id = settings.BK_IAM_SYSTEM_ID
        return cls(
            app_code=settings.APP_CODE,
            app_secret=settings.SECRET_KEY,
            gateway_url=resolve_v4_gateway_url(),
            system_id=system_id,
            timeout_seconds=float(getattr(settings, "BK_IAM_V4_TIMEOUT", 10)),
            batch_chunk_size=normalize_batch_chunk_size(
                getattr(settings, "BK_IAM_V4_BATCH_CHUNK_SIZE", DEFAULT_BATCH_CHUNK_SIZE)
            ),
            auth_path=getattr(settings, "BK_IAM_V4_AUTH_PATH", DEFAULT_AUTH_PATH),
            auth_by_resources_path=getattr(
                settings,
                "BK_IAM_V4_AUTH_BY_RESOURCES_PATH",
                DEFAULT_AUTH_BY_RESOURCES_PATH,
            ),
            apply_url_path=getattr(settings, "BK_IAM_V4_APPLY_URL_PATH", DEFAULT_APPLY_URL_PATH),
        )
