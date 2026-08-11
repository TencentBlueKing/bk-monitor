from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings

from apps.iam.backends.v4.gateway import resolve_v4_gateway_url

# IAM V4 开放 API 路径默认值；特殊环境可通过 Django settings 覆盖。
DEFAULT_AUTH_PATH = "api/v1/open/rbac/authorization/systems/{system_id}/auth/"
DEFAULT_AUTH_BY_RESOURCES_PATH = "api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/"
DEFAULT_AUTHORIZED_RESOURCES_PATH = "api/v1/open/rbac/authorization/systems/{system_id}/relation/authorized-resources/"
DEFAULT_APPLY_URL_PATH = "api/v1/open/application/permission-apply-urls/"
DEFAULT_AUTH_TOKEN_PATH = "api/v1/open/rbac/model/systems/{system_id}/auth-token/"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_ADD_AUTHORIZATION_PATH = "api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/"
DEFAULT_BATCH_CHUNK_SIZE = 100
MAX_BATCH_CHUNK_SIZE = 100
DEFAULT_BATCH_MAX_WORKERS = 4
MAX_BATCH_MAX_WORKERS = 8
DEFAULT_AUTH_TOKEN_CACHE_SECONDS = 300

logger = logging.getLogger("iam.v4.config")


def normalize_timeout_seconds(value: float | str | None) -> float:
    """归一化 IAM V4 请求超时，非法值回退到默认配置。"""
    try:
        configured = float(value) if value is not None else DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        logger.warning(
            "invalid BK_IAM_V4_TIMEOUT=%r, falling back to %s",
            value,
            DEFAULT_TIMEOUT_SECONDS,
        )
        return DEFAULT_TIMEOUT_SECONDS

    if configured <= 0:
        logger.warning(
            "invalid BK_IAM_V4_TIMEOUT=%s, falling back to %s",
            configured,
            DEFAULT_TIMEOUT_SECONDS,
        )
        return DEFAULT_TIMEOUT_SECONDS
    return configured


def normalize_auth_token_cache_seconds(value: int | str | None) -> int:
    """归一化资源回调 auth_token 缓存时长；0 表示关闭缓存。"""
    try:
        configured = int(value) if value is not None else DEFAULT_AUTH_TOKEN_CACHE_SECONDS
    except (TypeError, ValueError):
        logger.warning(
            "invalid BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS=%r, falling back to %s",
            value,
            DEFAULT_AUTH_TOKEN_CACHE_SECONDS,
        )
        return DEFAULT_AUTH_TOKEN_CACHE_SECONDS

    if configured < 0:
        logger.warning(
            "invalid BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS=%s, falling back to %s",
            configured,
            DEFAULT_AUTH_TOKEN_CACHE_SECONDS,
        )
        return DEFAULT_AUTH_TOKEN_CACHE_SECONDS
    return configured


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


def normalize_batch_max_workers(value: int | str | None) -> int:
    """归一化 V4 批量鉴权 chunk 并发度；<=1 表示串行。"""
    try:
        configured = int(value) if value is not None else DEFAULT_BATCH_MAX_WORKERS
    except (TypeError, ValueError):
        logger.warning(
            "invalid BK_IAM_V4_BATCH_MAX_WORKERS=%r, falling back to %s",
            value,
            DEFAULT_BATCH_MAX_WORKERS,
        )
        return DEFAULT_BATCH_MAX_WORKERS

    if configured < 1:
        logger.warning(
            "invalid BK_IAM_V4_BATCH_MAX_WORKERS=%s, falling back to %s",
            configured,
            DEFAULT_BATCH_MAX_WORKERS,
        )
        return DEFAULT_BATCH_MAX_WORKERS

    if configured > MAX_BATCH_MAX_WORKERS:
        logger.warning(
            "BK_IAM_V4_BATCH_MAX_WORKERS=%s exceeds limit %s, using %s",
            configured,
            MAX_BATCH_MAX_WORKERS,
            MAX_BATCH_MAX_WORKERS,
        )
        return MAX_BATCH_MAX_WORKERS

    return configured


def resolve_callback_app_credentials() -> tuple[str, str]:
    """V4 资源回调验签使用的 APP 凭证；未单独配置时与全局 APP 一致。"""
    app_code = str(getattr(settings, "BK_IAM_V4_CALLBACK_APP_CODE", "") or "").strip()
    app_secret = str(getattr(settings, "BK_IAM_V4_CALLBACK_APP_SECRET", "") or "").strip()
    if app_code and app_secret:
        return app_code, app_secret
    if app_code or app_secret:
        logger.warning(
            "BK_IAM_V4_CALLBACK_APP_CODE and BK_IAM_V4_CALLBACK_APP_SECRET must be configured together; "
            "falling back to global credentials"
        )
    return settings.APP_CODE, settings.SECRET_KEY


def resolve_effective_v4_system_id() -> str:
    """有效 V4 system ID：BK_IAM_V4_SYSTEM_ID 为空时回退 BK_IAM_SYSTEM_ID。"""
    v4_system_id = str(getattr(settings, "BK_IAM_V4_SYSTEM_ID", "") or "").strip()
    return v4_system_id or settings.BK_IAM_SYSTEM_ID


@dataclass(frozen=True, slots=True)
class V4Options:
    app_code: str
    app_secret: str
    gateway_url: str
    system_id: str
    timeout_seconds: float
    batch_chunk_size: int
    batch_max_workers: int
    auth_path: str
    auth_by_resources_path: str
    authorized_resources_path: str
    apply_url_path: str
    auth_token_path: str = DEFAULT_AUTH_TOKEN_PATH
    auth_token_cache_seconds: int = DEFAULT_AUTH_TOKEN_CACHE_SECONDS
    add_authorization_path: str = DEFAULT_ADD_AUTHORIZATION_PATH

    @classmethod
    def from_settings(cls, *, bk_tenant_id: str = "", for_resource_callback: bool = False) -> V4Options:
        del bk_tenant_id  # 租户信息通过每次请求的请求头传递，不放入选项
        system_id = resolve_effective_v4_system_id()
        if for_resource_callback:
            app_code, app_secret = resolve_callback_app_credentials()
        else:
            app_code, app_secret = settings.APP_CODE, settings.SECRET_KEY
        return cls(
            app_code=app_code,
            app_secret=app_secret,
            gateway_url=resolve_v4_gateway_url(),
            system_id=system_id,
            timeout_seconds=normalize_timeout_seconds(getattr(settings, "BK_IAM_V4_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
            batch_chunk_size=normalize_batch_chunk_size(
                getattr(settings, "BK_IAM_V4_BATCH_CHUNK_SIZE", DEFAULT_BATCH_CHUNK_SIZE)
            ),
            batch_max_workers=normalize_batch_max_workers(
                getattr(settings, "BK_IAM_V4_BATCH_MAX_WORKERS", DEFAULT_BATCH_MAX_WORKERS)
            ),
            auth_path=getattr(settings, "BK_IAM_V4_AUTH_PATH", DEFAULT_AUTH_PATH),
            auth_by_resources_path=getattr(
                settings,
                "BK_IAM_V4_AUTH_BY_RESOURCES_PATH",
                DEFAULT_AUTH_BY_RESOURCES_PATH,
            ),
            authorized_resources_path=getattr(
                settings,
                "BK_IAM_V4_AUTHORIZED_RESOURCES_PATH",
                DEFAULT_AUTHORIZED_RESOURCES_PATH,
            ),
            apply_url_path=getattr(settings, "BK_IAM_V4_APPLY_URL_PATH", DEFAULT_APPLY_URL_PATH),
            auth_token_path=getattr(settings, "BK_IAM_V4_AUTH_TOKEN_PATH", DEFAULT_AUTH_TOKEN_PATH),
            auth_token_cache_seconds=normalize_auth_token_cache_seconds(
                getattr(
                    settings,
                    "BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS",
                    DEFAULT_AUTH_TOKEN_CACHE_SECONDS,
                )
            ),
            add_authorization_path=getattr(
                settings,
                "BK_IAM_V4_ADD_AUTHORIZATION_PATH",
                DEFAULT_ADD_AUTHORIZATION_PATH,
            ),
        )
