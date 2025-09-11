"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    ServiceInstanceManager,
    TopoManager,
)
from alarm_backends.core.cache.cmdb.dynamic_group import DynamicGroupManager
from api.cmdb.define import ServiceInstance
from bkmonitor.utils.shield import BaseShieldDisplayManager
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id


class DisplayManager(BaseShieldDisplayManager):
    def get_business_name(self, bk_biz_id):
        business = BusinessManager.get(bk_biz_id)
        return business.bk_biz_name if business else str(bk_biz_id)

    def get_dynamic_group_name_list(self, bk_biz_id: int, dynamic_group_list: list[dict]) -> list:
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        dynamic_group_ids = [dynamic_group["dynamic_group_id"] for dynamic_group in dynamic_group_list]
        dynamic_groups = DynamicGroupManager.mget(bk_tenant_id=bk_tenant_id, dynamic_group_ids=dynamic_group_ids)
        return [
            dynamic_groups[dynamic_group_id]["name"] if dynamic_groups.get(dynamic_group_id) else dynamic_group_id
            for dynamic_group_id in dynamic_group_ids
        ]

    def get_node_path_list(self, bk_biz_id, bk_topo_node_list: list[dict]):
        """
        获取拓扑节点路径列表
        :param bk_biz_id: 业务ID
        :param bk_topo_node_list: 拓扑节点列表
        :return: 拓扑节点路径列表
        """
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        keys: list[tuple[str, int]] = []
        for node in bk_topo_node_list:
            keys.append((node["bk_obj_id"], int(node["bk_inst_id"])))
        node_infos = TopoManager.mget(bk_tenant_id=bk_tenant_id, topo_nodes=keys)
        result = []
        for bk_obj_id, bk_inst_id in keys:
            node_info = node_infos.get((bk_obj_id, bk_inst_id))
            if node_info:
                result.append([node_info.bk_obj_name, node_info.bk_inst_name])
            else:
                result.append([bk_obj_id, str(bk_inst_id)])
        return result

    def get_service_name_list(self, bk_biz_id: int, service_instance_id_list: list[int]) -> list[str]:
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        instances: dict[int, ServiceInstance] = ServiceInstanceManager.mget(
            bk_tenant_id=bk_tenant_id, service_instance_ids=service_instance_id_list
        )
        result: list[str] = []
        for instance_id in service_instance_id_list:
            instance = instances.get(instance_id)
            if not instance or instance.name is None:
                result.append(str(instance_id))
            else:
                result.append(instance.name)
        return result
