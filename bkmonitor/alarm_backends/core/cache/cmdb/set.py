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
from api.cmdb.define import Set
from constants.common import DEFAULT_TENANT_ID


class SetManager:
    """
    CMDB 集群缓存
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{CacheManager.CACHE_KEY_PREFIX}.cmdb.set"
        return f"{bk_tenant_id}.{CacheManager.CACHE_KEY_PREFIX}.cmdb.set"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, bk_set_ids: list[int]) -> dict[int, Set]:
        """
        批量获取集群
        :param bk_tenant_id: 租户ID
        :param bk_set_ids: 集群ID列表
        """
        if not bk_set_ids:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        result: list[str | None] = cls.cache.hmget(cache_key, [str(bk_set_id) for bk_set_id in bk_set_ids])
        return {bk_set_id: Set(**json.loads(r)) for bk_set_id, r in zip(bk_set_ids, result) if r}

    @classmethod
    def get(cls, *, bk_tenant_id: str, bk_set_id: int) -> Set | None:
        """
        获取单个集群
        :param bk_tenant_id: 租户ID
        :param bk_set_id: 集群ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hget(cache_key, str(bk_set_id))
        return Set(**json.loads(result)) if result else None
