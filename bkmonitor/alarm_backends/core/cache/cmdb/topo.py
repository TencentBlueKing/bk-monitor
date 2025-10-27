"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from api.cmdb.define import TopoNode, TopoTree
from core.drf_resource import api


class TopoManager(RefreshByBizMixin, CMDBCacheManager):
    """
    拓扑节点缓存
    """

    ObjectClass = TopoNode
    type = "topo"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.topo"

    @classmethod
    def key_to_internal_value(cls, bk_obj_id, bk_inst_id):
        return f"{bk_obj_id}|{bk_inst_id}"

    @classmethod
    def get(cls, bk_obj_id, bk_inst_id):
        """
        :param bk_obj_id: 对象ID
        :param bk_inst_id: 实例ID
        """
        return super().get(bk_obj_id, bk_inst_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)

        data = {}
        for node in topo_tree.get_all_nodes_with_relation().values():
            key = cls.key_to_internal_value(node.bk_obj_id, node.bk_inst_id)

            parents: list[str] = []
            parent: TopoTree = node._parent
            while parent:
                parents.append(f"{parent.bk_obj_id}|{parent.bk_inst_id}")
                parent = parent._parent

            data[key] = TopoNode(**node.__dict__)
            data[key].parents = parents
        return data
