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

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# V4 callback 项目的独立 IAM 客户端配置。


def _required_string(raw: dict[str, Any], field: str, *, context: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


@dataclass(frozen=True)
class V4CallbackCredentials:
    """callback 查询 IAM 系统 auth token 使用的客户端凭据。"""

    app_code: str
    app_secret: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V4CallbackCredentials:
        if not isinstance(raw, dict):
            raise ValueError("IAM_V4_CALLBACK.credentials must be a dict")
        return cls(
            app_code=_required_string(raw, "app_code", context="IAM_V4_CALLBACK.credentials"),
            app_secret=_required_string(raw, "app_secret", context="IAM_V4_CALLBACK.credentials"),
        )


@dataclass(frozen=True)
class V4CallbackConfig:
    """callback 项目连接 IAM 的配置，不读取 IAM_FRAMEWORK Provider options。"""

    base_url: str
    system_id: str
    credentials: V4CallbackCredentials
    timeout: int = 30
    bk_tenant_id: str = "system"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V4CallbackConfig:
        if not isinstance(raw, dict):
            raise ValueError("IAM_V4_CALLBACK must be a dict")

        credentials = V4CallbackCredentials.from_dict(raw.get("credentials", {}))
        try:
            timeout = int(raw.get("timeout", 30))
        except (TypeError, ValueError) as exc:
            raise ValueError("IAM_V4_CALLBACK.timeout must be an integer") from exc
        if timeout <= 0:
            raise ValueError("IAM_V4_CALLBACK.timeout must be greater than zero")

        return cls(
            base_url=_required_string(raw, "base_url", context="IAM_V4_CALLBACK"),
            system_id=_required_string(raw, "system_id", context="IAM_V4_CALLBACK"),
            credentials=credentials,
            timeout=timeout,
            bk_tenant_id=str(raw.get("bk_tenant_id", "system")),
        )


def get_v4_callback_config() -> V4CallbackConfig:
    """从 callback 项目自己的 Django setting 构造配置。"""
    try:
        return V4CallbackConfig.from_dict(getattr(settings, "IAM_V4_CALLBACK", {}))
    except ValueError as exc:
        raise ImproperlyConfigured(f"Invalid IAM_V4_CALLBACK configuration: {exc}") from exc
