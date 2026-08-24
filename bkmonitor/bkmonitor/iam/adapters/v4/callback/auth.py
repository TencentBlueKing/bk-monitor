"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from ....iam_v4.client import V4Client
from .config import V4CallbackConfig, get_v4_callback_config

logger = logging.getLogger(__name__)

_TOKEN_CACHE_TTL = 300
_TOKEN_PROVIDER_LOCK = threading.Lock()
_token_provider: V4SystemTokenProvider | None = None


class SystemTokenProvider(Protocol):
    """为 callback HTTP 鉴权提供 IAM 系统 token。"""

    def get_system_token(self) -> str:
        """返回当前可用的 IAM 系统 token。"""


class AuthTokenClient(Protocol):
    """V4Client 的 callback 鉴权所需最小接口。"""

    def get_auth_token(self) -> str:
        """向 IAM 获取系统 auth token。"""


def _build_v4_client(config: V4CallbackConfig) -> V4Client:
    return V4Client(
        base_url=config.base_url,
        system_id=config.system_id,
        app_code=config.credentials.app_code,
        app_secret=config.credentials.app_secret,
        timeout=config.timeout,
        bk_tenant_id=config.bk_tenant_id,
    )


class V4SystemTokenProvider:
    """使用 callback 自己的 IAM 配置获取并缓存系统 auth token。"""

    def __init__(
        self,
        config: V4CallbackConfig,
        client_factory: Callable[[V4CallbackConfig], AuthTokenClient] = _build_v4_client,
    ) -> None:
        self.config = config
        self._client_factory = client_factory
        self._client: AuthTokenClient | None = None
        self._cached_token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    def get_system_token(self) -> str:
        with self._lock:
            now = time.monotonic()
            if self._cached_token is not None and now < self._expires_at:
                return self._cached_token
            if self._client is None:
                self._client = self._client_factory(self.config)
            self._cached_token = self._client.get_auth_token()
            self._expires_at = now + _TOKEN_CACHE_TTL
            return self._cached_token


def get_callback_token_provider() -> V4SystemTokenProvider:
    """返回与当前 callback 配置一致的进程级 token provider。"""
    global _token_provider

    config = get_v4_callback_config()
    with _TOKEN_PROVIDER_LOCK:
        if _token_provider is None or _token_provider.config != config:
            _token_provider = V4SystemTokenProvider(config)
        return _token_provider


class IamCallbackAuthentication(BaseAuthentication):
    """IAM callback Basic Auth 校验，token 来源由项目注入。"""

    def __init__(self, token_provider: SystemTokenProvider) -> None:
        self._token_provider = token_provider

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Basic "):
            raise AuthenticationFailed("Missing or invalid Authorization header")

        try:
            decoded = base64.b64decode(auth_header[6:], validate=True).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception as exc:
            raise AuthenticationFailed("Invalid Basic Auth encoding") from exc

        if username != "bk_iam":
            raise AuthenticationFailed("Invalid callback username")

        if password != self._token_provider.get_system_token():
            logger.warning("[iam_v4:callback:auth] token mismatch")
            raise AuthenticationFailed("Invalid callback token")

        return (None, None)


class MonitorIamCallbackAuthentication(IamCallbackAuthentication):
    """监控项目绑定独立 callback 配置后的认证实现。"""

    def __init__(self) -> None:
        super().__init__(get_callback_token_provider())
