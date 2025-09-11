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

from api.cmdb.define import TopoNode

from .base import CMDBCacheManager


class TopoManager(CMDBCacheManager):
    """
    拓扑节点缓存
    """

    cache_type = "topo"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, topo_nodes: list[tuple[str, int]]) -> dict[tuple[str, int], TopoNode]:
        """
        批量获取拓扑节点
        :param bk_tenant_id: 租户ID
        :param topo_nodes: 拓扑节点列表
        """
        if not topo_nodes:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        topo_keys: list[str] = [f"{bk_obj_id}|{bk_inst_id}" for bk_obj_id, bk_inst_id in topo_nodes]
        result: list[str | None] = cast(list[str | None], cls.cache.hmget(cache_key, topo_keys))
        return {
            (bk_obj_id, bk_inst_id): TopoNode(**json.loads(r))
            for (bk_obj_id, bk_inst_id), r in zip(topo_nodes, result)
            if r
        }

    @classmethod
    def get(cls, *, bk_tenant_id: str, bk_obj_id: str, bk_inst_id: int, **kwargs) -> TopoNode | None:
        """
        获取单个拓扑节点
        :param bk_tenant_id: 租户ID
        :param bk_obj_id: 对象ID
        :param bk_inst_id: 实例ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, f"{bk_obj_id}|{bk_inst_id}"))
        if not result:
            return None
        return TopoNode(**json.loads(result))
