"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from abc import ABC, abstractmethod
from typing import Any

from django.conf import settings

from alarm_backends.core.cache.key import PUBLIC_KEY_PREFIX
from alarm_backends.core.storage.redis import Cache
from constants.common import DEFAULT_TENANT_ID


class CMDBCacheManager(ABC):
    cache = Cache("cache-cmdb")
    cache_type: str
    CACHE_TIMEOUT = 60 * 60 * 24 * 7

    @staticmethod
    def _get_cache_key_prefix(bk_tenant_id: str) -> str:
        """
        获取缓存key前缀（兼容非多租户环境）
        :param bk_tenant_id: 租户ID
        :return: 缓存key前缀
        """
        if not settings.ENABLE_MULTI_TENANT_MODE or bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{PUBLIC_KEY_PREFIX}.cache.cmdb"
        return f"{bk_tenant_id}.{PUBLIC_KEY_PREFIX}.cache.cmdb"

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        """
        获取缓存key
        :param bk_tenant_id: 租户ID
        :return: 缓存key
        """
        return f"{cls._get_cache_key_prefix(bk_tenant_id)}.{cls.cache_type}"

    @classmethod
    @abstractmethod
    def get(cls, *args, **kwargs) -> Any:
        """
        获取缓存
        :param bk_tenant_id: 租户ID
        :param kwargs: 其他参数
        :return: 缓存
        """
        raise NotImplementedError
