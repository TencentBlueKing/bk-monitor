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


from itertools import chain

from alarm_backends.core.cache.cmdb import HostManager, ServiceInstanceManager
from alarm_backends.service.access.base import Fuller
from constants.data_source import DataSourceLabel, DataTypeLabel


class TopoNodeFuller(Fuller):
    @classmethod
    def is_service_target(cls, scenario):
        """
        判断是否是"服务"层
        """
        return scenario in ("component", "service_module", "service_process")

    @classmethod
    def is_host_target(cls, scenario):
        """
        判断是否为"主机"层
        """
        return scenario in ("os", "host_process")

    def full(self, record):
        """
        维度补充(当策略目标是CMDB节点时，需要在数据的维度中补充CMDB节点的信息)

        1. 如果数据来源"服务"层，则补充"实例"所属的CMDB节点信息，以及主机信息，否则进入下一步
        2. 如果数据来源"主机"层，则补充"主机"所属的CMDB节点信息
        """
        dimensions = record.dimensions

        for item in record.items:
            if (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT) in item.data_source_types:
                # 如果是自愈事件，标准字段为 ip, bk_cloud_id 因此需要先进行转换
                if "ip" in dimensions:
                    dimensions["bk_target_ip"] = dimensions["ip"]
                if "bk_cloud_id" in dimensions:
                    dimensions["bk_target_cloud_id"] = dimensions["bk_cloud_id"]
                if "bk_service_instance_id" in dimensions:
                    dimensions["bk_target_service_instance_id"] = dimensions["bk_service_instance_id"]
                break

        # 按主机ID补全维度
        bk_host_id = dimensions.get("bk_host_id")
        if bk_host_id:
            host = HostManager.get_by_id(bk_host_id)
            if host:
                dimensions["bk_target_ip"] = host.ip
                dimensions["bk_target_cloud_id"] = str(host.bk_cloud_id)

        # 按服务实例补全维度
        service_instance_id = dimensions.get("bk_target_service_instance_id") or dimensions.get("service_instance_id")
        if service_instance_id:
            service_instance = ServiceInstanceManager.get(service_instance_id)
            if service_instance:
                bk_topo_node = []
                if service_instance.topo_link:
                    bk_topo_node = list({node.id for node in chain(*list(service_instance.topo_link.values()))})
                dimensions["bk_target_ip"] = service_instance.ip
                dimensions["bk_target_cloud_id"] = service_instance.bk_cloud_id
                dimensions["bk_topo_node"] = bk_topo_node
                return

        # 主机补全维度
        bk_target_ip = dimensions.get("bk_target_ip") or dimensions.get("ip")
        if bk_target_ip is None:
            return

        bk_target_cloud_id = dimensions.get("bk_target_cloud_id", "0") or dimensions.get("bk_cloud_id", "0")
        host = HostManager.get(bk_target_ip, bk_target_cloud_id, using_mem=True)
        if not host:
            return

        bk_topo_node = []
        if host.topo_link:
            bk_topo_node = list({node.id for node in chain(*list(host.topo_link.values()))})
        dimensions["bk_topo_node"] = bk_topo_node
        if "bk_host_id" not in dimensions:
            # 主机对象获取到后，必定补上bk_host_id。 后续模块基于bk_host_id即可确认唯一主机
            dimensions["bk_host_id"] = host.bk_host_id
