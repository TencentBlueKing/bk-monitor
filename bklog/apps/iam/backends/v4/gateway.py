from __future__ import annotations

from django.conf import settings


def resolve_v4_gateway_url() -> str:
    """解析 IAM V4（bkiam）网关根地址，优先独立配置。"""

    explicit = str(getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", "") or "").strip()
    if explicit:
        return _normalize_gateway_root(explicit)

    component_api_url = str(getattr(settings, "BK_COMPONENT_API_URL", "") or "").strip()
    if component_api_url:
        return _normalize_gateway_root(f"{component_api_url.rstrip('/')}/api/bkiam/prod")

    legacy_url = str(getattr(settings, "BK_IAM_APIGATEWAY_URL", "") or "").strip()
    if legacy_url:
        return _normalize_gateway_root(legacy_url)

    return ""


def _normalize_gateway_root(url: str) -> str:
    return url.rstrip("/") + "/"
