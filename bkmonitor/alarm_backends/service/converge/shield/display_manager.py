# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Dict, List

from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    ServiceInstanceManager,
    TopoManager,
)
from alarm_backends.core.cache.cmdb.dynamic_group import DynamicGroupManager
from bkmonitor.utils.shield import BaseShieldDisplayManager


class DisplayManager(BaseShieldDisplayManager):
    def get_business_name(self, bk_biz_id):
        business = BusinessManager.get(bk_biz_id)
        return business.bk_biz_name if business else str(bk_biz_id)

    def get_dynamic_group_name_list(self, bk_biz_id: int, dynamic_group_list: List[Dict]) -> List:
        dynamic_group_ids = [dynamic_group["dynamic_group_id"] for dynamic_group in dynamic_group_list]
        dynamic_groups = DynamicGroupManager.multi_get(dynamic_group_ids)
        return [
            group.name if group else dynamic_group_id
            for dynamic_group_id, group in zip(dynamic_group_ids, dynamic_groups)
        ]

    def get_node_path_list(self, bk_biz_id, bk_topo_node_list):
        keys = []
        for node in bk_topo_node_list:
            keys.append(TopoManager.key_to_internal_value(bk_obj_id=node["bk_obj_id"], bk_inst_id=["bk_inst_id"]))
        node_infos = TopoManager.multi_get(keys)
        result = []
        for index, node_id_info in enumerate(bk_topo_node_list):
            node = node_infos[index]
            if node:
                result.append([node.bk_obj_name, node.bk_inst_name])
            else:
                result.append([node_id_info["bk_obj_id"], str(node_id_info["bk_inst_id"])])
        return result

    def get_service_name_list(self, bk_biz_id, service_instance_id_list):
        keys = []
        for instance_id in service_instance_id_list:
            keys.append(ServiceInstanceManager.key_to_internal_value(instance_id))
        instances = ServiceInstanceManager.multi_get(keys)

        result = []
        for index, instance_id in enumerate(service_instance_id_list):
            instance = instances[index]
            result.append(instance.name if instance else str(instance_id))
        return result
