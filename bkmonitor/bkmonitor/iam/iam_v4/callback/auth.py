"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# IamCallbackAuthentication — 回调接口 HTTP Basic Auth 鉴权
#
# IAM 回调使用 Basic Auth：username = "bk_iam"，password = 系统 auth_token。
# token 通过 V4Client.get_auth_token() 获取，缓存 5 分钟。
# ---------------------------------------------------------------------------

from __future__ import annotations

import base64
import logging
import time

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from django.conf import settings

from ..client import V4Client

logger = logging.getLogger(__name__)

# 模块级缓存
_CACHED_TOKEN: str | None = None
_CACHED_TOKEN_EXPIRE_AT: float = 0
_TOKEN_CACHE_TTL: int = 300  # 5 min


def _get_client() -> V4Client:
    """创建 V4Client（回调场景从 Django settings 读取配置）。"""
    return V4Client(
        base_url=getattr(settings, "BK_IAM_V4_API_BASE_URL", ""),
        system_id=getattr(settings, "BK_IAM_V4_SYSTEM_ID", ""),
        app_code=getattr(settings, "BK_IAM_APP_CODE", ""),
        app_secret=getattr(settings, "BK_IAM_APP_SECRET", ""),
        timeout=int(getattr(settings, "BK_IAM_V4_API_TIMEOUT", 30)),
    )


def _get_system_token() -> str:
    global _CACHED_TOKEN, _CACHED_TOKEN_EXPIRE_AT
    now = time.time()
    if _CACHED_TOKEN is not None and now < _CACHED_TOKEN_EXPIRE_AT:
        return _CACHED_TOKEN
    client = _get_client()
    _CACHED_TOKEN = client.get_auth_token()
    _CACHED_TOKEN_EXPIRE_AT = now + _TOKEN_CACHE_TTL
    return _CACHED_TOKEN


class IamCallbackAuthentication(BaseAuthentication):
    """IAM 回调接口鉴权：HTTP Basic Auth (bk_iam / system_token)。"""

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Basic "):
            raise AuthenticationFailed("Missing or invalid Authorization header")

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            raise AuthenticationFailed("Invalid Basic Auth encoding")

        if username != "bk_iam":
            raise AuthenticationFailed("Invalid callback username")

        expected_token = _get_system_token()
        if password != expected_token:
            logger.warning("[iam_v4:callback:auth] token mismatch")
            raise AuthenticationFailed("Invalid callback token")

        # 回调不关联具体 Django User
        return (None, None)
