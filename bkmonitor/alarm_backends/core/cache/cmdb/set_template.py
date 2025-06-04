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

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.storage.redis import Cache
from constants.common import DEFAULT_TENANT_ID


class SetTemplateManager:
    """
    CMDB 集群模板缓存
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{CacheManager.CACHE_KEY_PREFIX}.cmdb.set_template"
        return f"{bk_tenant_id}.{CacheManager.CACHE_KEY_PREFIX}.cmdb.set_template"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, ids: list[int]) -> dict[int, list[int]]:
        """
        批量获取集群模板
        :param bk_tenant_id: 租户ID
        :param ids: 集群模板ID列表
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hmget(cache_key, [str(id) for id in ids])
        return {id: json.loads(r, ensure_ascii=False) if r else [] for id, r in zip(ids, result)}

    @classmethod
    def get(cls, *, bk_tenant_id: str, id: int) -> list[int]:
        """
        获取单个集群模板
        :param bk_tenant_id: 租户ID
        :param id: 集群模板ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hget(cache_key, str(id))
        return json.loads(result, ensure_ascii=False) if result else []
