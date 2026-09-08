"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import lazy


def get_saas_setting(name: str) -> str:
    """在使用 IAM 客户端时读取 SaaS 身份，避免启动时捕获空的动态配置。"""
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    value = getattr(settings, name, "")
    if not value:
        # manage.py migrate 不安装 DynamicSettings；此时仍从已有 GlobalConfig 读取 SaaS 身份。
        from bkmonitor.models.config import GlobalConfig

        value = GlobalConfig.get(name, "", raise_exception=True)
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured(f"IAM requires configured {name}")
    return value


saas_setting = lazy(get_saas_setting, str)
