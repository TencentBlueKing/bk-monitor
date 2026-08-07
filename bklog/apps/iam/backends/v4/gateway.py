from __future__ import annotations

from django.conf import settings


def resolve_v4_gateway_url() -> str:
    """解析 IAM V4（bkiam）网关根地址；仅接受显式配置，不做推导或 V3 回退。"""

    explicit = str(getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", "") or "").strip()
    return _normalize_gateway_root(explicit) if explicit else ""


def _normalize_gateway_root(url: str) -> str:
    return url.rstrip("/") + "/"
