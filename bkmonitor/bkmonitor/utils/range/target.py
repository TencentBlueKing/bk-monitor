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
import logging
from typing import Dict, List, Set

logger = logging.getLogger("service")


class TargetCondition:
    """
    监控目标条件匹配
    """

    def __init__(self, target: List[List[Dict]]):
        self.conditions_list = self.load_target_condition(target)

    @staticmethod
    def load_target_condition(target: List[List[Dict]]):
        """
        加载监控目标条件
        """
        if not target:
            return []

        conditions_list = []
        for target_condition in target:
            conditions = []
            for condition in target_condition:
                field = condition["field"].lower()
                method = condition["method"].lower()
                values = condition["value"]

                target_keys = set()
                if field in ["ip", "bk_target_ip"]:
                    for value in values:
                        bk_host_id = value.get("bk_host_id")
                        if bk_host_id:
                            target_keys.add(str(bk_host_id))

                        ip = value.get("bk_target_ip", value.get("ip"))
                        if not ip:
                            continue
                        bk_cloud_id = value.get("bk_target_cloud_id", value.get("bk_cloud_id", 0))
                        target_keys.add(f"{ip}|{bk_cloud_id}")
                elif field in ["service_instance_id", "bk_target_service_instance_id"]:
                    for value in values:
                        service_instance_id = value.get(
                            "bk_target_service_instance_id", value.get("service_instance_id")
                        )
                        if not service_instance_id:
                            continue
                        target_keys.add(str(service_instance_id))
                elif field.split("_", 1)[1] == "topo_node":
                    for value in values:
                        bk_obj_id = value.get("bk_obj_id")
                        bk_inst_id = value.get("bk_inst_id")

                        if not bk_obj_id or not bk_inst_id:
                            continue

                        target_keys.add(f"{bk_obj_id}|{bk_inst_id}")

                if not target_keys:
                    continue

                conditions.append({"field": field, "method": method, "target_keys": target_keys})

            if conditions:
                conditions_list.append(conditions)
        return conditions_list

    def is_match(self, data: Dict):
        """
        判断数据是否匹配监控目标
        """
        for conditions in self.conditions_list:
            for condition in conditions:
                field = condition["field"]
                method = condition["method"]
                values: Set = condition["target_keys"]

                target_keys = set()
                if field in ["ip", "bk_target_ip"]:
                    bk_host_id = data.get("bk_host_id")
                    if bk_host_id:
                        target_keys.add(str(bk_host_id))

                    ip = data.get("bk_target_ip", data.get("ip"))
                    if ip:
                        bk_cloud_id = data.get("bk_target_cloud_id", data.get("bk_cloud_id", 0))
                        target_keys.add(f"{ip}|{bk_cloud_id}")
                    if not target_keys:
                        continue
                elif field in ["service_instance_id", "bk_target_service_instance_id"]:
                    service_instance_id = data.get("bk_target_service_instance_id", data.get("service_instance_id"))
                    if not service_instance_id:
                        continue
                    target_keys.add(str(service_instance_id))
                elif field.split("_", 1)[1] == "topo_node":
                    target_keys = set()
                    if "bk_topo_node" in data:
                        topo_nodes = data["bk_topo_node"]
                    elif "bk_obj_id" in data and "bk_inst_id" in data:
                        topo_nodes = [f'{data["bk_obj_id"]}|{data["bk_inst_id"]}']
                    else:
                        # 这里topo_node是基于主机信息full出来的，如果数据中不存在topo信息，则表示主机信息无效
                        # 可能原因：
                        #   1. 机器在cmdb已移除，但依然上报数据，此时该机器数据无效
                        #   2. 策略配置的数据字段不足以获取topo信息，但监控目标又是基于topo信息的匹配
                        # 此时数据均以无效处理
                        break

                    if not topo_nodes:
                        logger.info(f"data target topo_node is empty, {data}")
                        break

                    target_keys.update(topo_nodes)
                if method == "eq":
                    is_match = values & target_keys
                else:
                    is_match = not (values & target_keys)

                # 有一个条件不满足，则跳过
                if not is_match:
                    break
            else:
                # 所有条件都满足，则返回True
                return True
        return False
