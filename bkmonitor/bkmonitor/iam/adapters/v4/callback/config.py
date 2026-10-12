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

from dataclasses import replace

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from iam_engine.v4.config import load_v4_paths, resolve_callback_app_credentials

from ....iam_v4.config import V4Credentials, V4Options


def get_v4_callback_config() -> V4Options:
    """复用 V4 目录配置，不依赖 Provider 的启用状态或运行期实例。"""
    try:
        options = settings.IAM_FRAMEWORK["PROVIDER_CATALOG"]["v4"]["options"]
        config = V4Options.from_dict(options)
        app_code, app_secret = resolve_callback_app_credentials(
            (str(config.credentials.app_code), str(config.credentials.app_secret))
        )
        # 固化本次凭据快照，让 SaaS 凭据变化能够使 callback token 缓存失效。
        return replace(
            config,
            credentials=V4Credentials(app_code, app_secret),
            extra={**config.extra, "api_paths": load_v4_paths(settings)},
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ImproperlyConfigured("Invalid IAM V4 callback configuration") from exc
