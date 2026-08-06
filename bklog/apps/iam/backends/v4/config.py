from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.iam.backends.v4.gateway import resolve_v4_gateway_url


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
            batch_chunk_size=int(getattr(settings, "BK_IAM_V4_BATCH_CHUNK_SIZE", 100)),
            auth_path=getattr(
                settings,
                "BK_IAM_V4_AUTH_PATH",
                "api/v1/open/rbac/authorization/systems/{system_id}/auth/",
            ),
            auth_by_resources_path=getattr(
                settings,
                "BK_IAM_V4_AUTH_BY_RESOURCES_PATH",
                "api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/",
            ),
            apply_url_path=getattr(
                settings,
                "BK_IAM_V4_APPLY_URL_PATH",
                "api/v1/open/application/permission-apply-urls/",
            ),
        )
