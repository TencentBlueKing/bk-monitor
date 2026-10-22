from __future__ import annotations

from django.conf import settings
from iam_engine.settings import resolve_iam_gateway_url


def resolve_v4_gateway_url() -> str:
    """Resolve bkiam independently of V3, including settings-time overrides."""

    return resolve_iam_gateway_url(
        getattr(settings, "BK_COMPONENT_API_URL", None),
        getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", ""),
        version="v4",
    )
