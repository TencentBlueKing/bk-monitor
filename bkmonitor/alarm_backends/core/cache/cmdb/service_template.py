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

from .base import CMDBCacheManager


class ServiceTemplateManager(CMDBCacheManager):
    """
    CMDB 服务模板缓存
    """

    cache_type = "service_template"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, ids: list[int]) -> dict[int, list[int]]:
        """
        批量获取服务模板下的模块ID列表
        :param bk_tenant_id: 租户ID
        :param ids: 服务模板ID列表
        """
        if not ids:
            return {id: [] for id in ids}

        cache_key = cls.get_cache_key(bk_tenant_id)
        id_list: list[str] = list(str(id) for id in ids)
        result: list[str | None] = cast(list[str | None], cls.cache.hmget(cache_key, id_list))
        return {id: json.loads(r) if r else [] for id, r in zip(ids, result)}

    @classmethod
    def get(cls, *, bk_tenant_id: str, id: int, **kwargs) -> list[int]:
        """
        获取单个服务模板下的模块ID列表
        :param bk_tenant_id: 租户ID
        :param id: 服务模板ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, str(id)))
        return json.loads(result) if result else []
