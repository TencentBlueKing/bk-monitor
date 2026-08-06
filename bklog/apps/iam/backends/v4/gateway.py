from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("iam.v4.gateway")


def resolve_v4_gateway_url() -> str:
    """解析 IAM V4（bkiam）网关根地址；仅接受显式配置，不做推导或 V3 回退。"""

    explicit = str(getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", "") or "").strip()
    if explicit:
        return _normalize_gateway_root(explicit)

    logger.error(
        "BK_IAM_V4_APIGATEWAY_URL is not configured; set env BKAPP_IAM_V4_API_BASE_URL "
        "to the bkiam APIGateway root (e.g. https://bkiam.apigw.o.woa.com/stage/)"
    )
    return ""


def _normalize_gateway_root(url: str) -> str:
    return url.rstrip("/") + "/"
