"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import cast

from api.cmdb.define import Set

from .base import CMDBCacheManager


class SetManager(CMDBCacheManager):
    """
    CMDB 集群缓存
    """

    cache_type = "set"

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
        result: list[str | None] = cast(
            list[str | None], cls.cache.hmget(cache_key, [str(bk_set_id) for bk_set_id in bk_set_ids])
        )
        return {bk_set_id: Set(**json.loads(r)) for bk_set_id, r in zip(bk_set_ids, result) if r}

    @classmethod
    def get(cls, *, bk_tenant_id: str, bk_set_id: int, **kwargs) -> Set | None:
        """
        获取单个集群
        :param bk_tenant_id: 租户ID
        :param bk_set_id: 集群ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, str(bk_set_id)))
        return Set(**json.loads(result)) if result else None
