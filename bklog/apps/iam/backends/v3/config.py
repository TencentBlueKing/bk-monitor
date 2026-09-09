from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True, slots=True)
class V3Options:
    """IAM V3 客户端的接入参数。"""

    app_code: str
    app_secret: str
    gateway_url: str
    system_id: str

    @classmethod
    def from_settings(cls) -> V3Options:
        return cls(
            app_code=settings.APP_CODE,
            app_secret=settings.SECRET_KEY,
            gateway_url=settings.BK_IAM_APIGATEWAY_URL,
            system_id=settings.BK_IAM_SYSTEM_ID,
        )
