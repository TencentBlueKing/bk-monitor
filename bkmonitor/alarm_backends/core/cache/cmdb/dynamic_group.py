"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager
from alarm_backends.core.storage.redis import Cache
from constants.common import DEFAULT_TENANT_ID


class DynamicGroupManager:
    """
    CMDB 模块缓存
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.dynamic_group"
        return f"{bk_tenant_id}.{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.dynamic_group"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, dynamic_group_ids: list[str]) -> dict[str, dict | None]:
        """
        批量获取动态组
        :param bk_tenant_id: 租户ID
        :param dynamic_group_ids: 动态组ID列表
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hmget(cache_key, [str(dynamic_group_id) for dynamic_group_id in dynamic_group_ids])
        return {
            dynamic_group_id: json.loads(result, ensure_ascii=False) if result else None
            for dynamic_group_id, result in zip(dynamic_group_ids, result)
        }

    @classmethod
    def get(cls, *, bk_tenant_id: str, dynamic_group_id: str) -> dict | None:
        """
        获取单个动态组
        :param bk_tenant_id: 租户ID
        :param dynamic_group_id: 动态组ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hget(cache_key, str(dynamic_group_id))
        return json.loads(result, ensure_ascii=False) if result else None
