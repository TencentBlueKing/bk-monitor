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
from collections.abc import Sequence
from typing import Any, cast

from .base import CMDBCacheManager


class DynamicGroupManager(CMDBCacheManager):
    """
    CMDB 模块缓存
    """

    cache_type = "dynamic_group"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, dynamic_group_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
        """
        批量获取动态组
        :param bk_tenant_id: 租户ID
        :param dynamic_group_ids: 动态组ID列表
        """
        dynamic_group_id_list: list[str] = list(str(dynamic_group_id) for dynamic_group_id in dynamic_group_ids)
        result: list[str | None] = cast(
            list[str | None], cls.cache.hmget(cls.get_cache_key(bk_tenant_id), dynamic_group_id_list)
        )
        return {dynamic_group_id: json.loads(r) for dynamic_group_id, r in zip(dynamic_group_ids, result) if r}

    @classmethod
    def get(cls, *, bk_tenant_id: str, dynamic_group_id: str, **kwargs) -> dict | None:
        """
        获取单个动态组
        :param bk_tenant_id: 租户ID
        :param dynamic_group_id: 动态组ID
        """
        result = cast(str | None, cls.cache.hget(cls.get_cache_key(bk_tenant_id), str(dynamic_group_id)))
        return json.loads(result) if result else None
