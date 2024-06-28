# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from ipaddress import IPv6Address, ip_address

from opentelemetry.semconv.trace import SpanAttributes

from api.cmdb.client import list_biz_hosts
from apm_web.constants import HostAddressType
from apm_web.models import CMDBServiceRelation
from bkmonitor.commons.tools import batch_request
from constants.apm import OtlpKey
from core.drf_resource import api


class HostHandler:
    class SourceType:
        """主机来源类型"""

        CMDB_RELATION = "cmdb_relation"
        TOPO = "topo"

    PAGE_LIMIT = 100

    @classmethod
    def list_application_hosts(cls, bk_biz_id, app_name, service_name):
        """
        获取应用的主机列表
        主机来源:
        1. 通过CMDB服务模版关联
        2. 通过topo发现
        """
        # step1: 从主机发现取出主机
        discover_host_instances = api.apm_api.query_host_instance(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        )

        apm_host_instances = []
        non_host_id_instances = []
        for i in discover_host_instances:
            if not i["bk_host_id"]:
                # 兼容旧拓扑数据没有host_id情况
                non_host_id_instances.append(i)
            else:
                apm_host_instances.append(
                    {
                        "bk_host_innerip": i["ip"],
                        "bk_cloud_id": str(i["bk_cloud_id"]),
                        "bk_host_id": str(i["bk_host_id"]),
                        "source_type": cls.SourceType.TOPO,
                    }
                )

        real_host_instances = cls.get_host_id_by_ip(bk_biz_id, non_host_id_instances)
        for item in real_host_instances:
            apm_host_instances.append(
                {
                    "bk_host_innerip": item["ip"],
                    "bk_cloud_id": str(item["bk_cloud_id"]),
                    "bk_host_id": str(item["bk_host_id"]),
                    "source_type": cls.SourceType.TOPO,
                }
            )

        # step2: 从关联cmdb取出主机
        relation = CMDBServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        cmdb_host_instances = []
        if relation:
            response = batch_request(
                api.cmdb.find_host_by_service_template,
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_service_template_ids": [relation.first().template_id],
                    "fields": ["bk_host_innerip", "bk_cloud_id", "bk_host_id", "bk_host_innerip_v6"],
                },
            )
            if response:
                for item in response:
                    if item["bk_host_innerip"]:
                        ip = item["bk_host_innerip"].split(",")[0]
                        cmdb_host_instances.append(
                            {
                                "bk_host_innerip": ip,
                                "bk_cloud_id": str(item["bk_cloud_id"]),
                                "bk_host_id": str(item["bk_host_id"]),
                                "source_type": cls.SourceType.CMDB_RELATION,
                            }
                        )
                    elif item.get("bk_host_innerip_v6"):
                        ip = item["bk_host_innerip_v6"].split(",")[0]
                        cmdb_host_instances.append(
                            {
                                "bk_host_innerip": ip,
                                "bk_cloud_id": str(item["bk_cloud_id"]),
                                "bk_host_id": str(item["bk_host_id"]),
                                "source_type": cls.SourceType.CMDB_RELATION,
                            }
                        )

        return apm_host_instances + cmdb_host_instances

    @classmethod
    def find_host_in_span(cls, bk_biz_id, app_name, span_id):
        """从span中寻找主机"""

        span = api.apm_api.query_span_detail(bk_biz_id=bk_biz_id, app_name=app_name, span_id=span_id)

        if not span:
            return None

        # 1. 从resource中寻找
        ip = span[OtlpKey.RESOURCE].get(SpanAttributes.NET_HOST_IP)
        if not ip:
            return None

        try:
            if isinstance(ip_address(ip), IPv6Address):
                rule = [{"field": "bk_host_innerip_v6", "operator": "equal", "value": ip}]
                address_type = HostAddressType.IPV6
            else:
                rule = [{"field": "bk_host_innerip", "operator": "equal", "value": ip}]
                address_type = HostAddressType.IPV4
        except ValueError:
            raise ValueError(f"从 resource 中找到了 IP: {ip}，但是不是合法的 IP 地址，请检查后重新上报")

        params = {
            "page": {"start": 0, "limit": 1},
            "fields": ["bk_cloud_id", "bk_host_innerip", "bk_host_id"],
            "bk_biz_id": bk_biz_id,
            "host_property_filter": {
                "condition": "AND",
                "rules": rule,
            },
        }
        response = list_biz_hosts(params)

        if response.get("count"):
            info = response["info"][0]

            return {
                "address_type": address_type,
                "bk_cloud_id": info["bk_cloud_id"],
                "bk_host_id": str(info["bk_host_id"]),
                "bk_host_innerip": info["bk_host_innerip"],
            }

        return None

    @classmethod
    def get_host_id_by_ip(cls, bk_biz_id, instances):
        # 旧数据只有ipv4

        params = {
            "page": {"start": 0, "limit": cls.PAGE_LIMIT},
            "fields": ["bk_cloud_id", "bk_host_innerip", "bk_host_id"],
            "bk_biz_id": bk_biz_id,
            "host_property_filter": {
                "condition": "AND",
                "rules": [{"field": "bk_host_innerip", "operator": "in", "value": [i["ip"] for i in instances]}],
            },
        }

        result = list_biz_hosts(params)
        if not result or result.get("count") <= 0:
            return []

        ip_mapping = {(i["bk_cloud_id"], i["bk_host_innerip"]): i for i in result["info"]}
        count = result["count"] // cls.PAGE_LIMIT
        for i in range(1, count):
            params["page"]["start"] = i * cls.PAGE_LIMIT
            temp_result = list_biz_hosts(params)
            ip_mapping.update({i["bk_host_innerip"]: i for i in temp_result["info"]})

        res = []
        for i in instances:
            if (i["bk_cloud_id"], i["ip"]) in ip_mapping:
                res.append(
                    {
                        **i,
                        "bk_host_id": ip_mapping[(i["bk_cloud_id"], i["ip"])]["bk_host_id"],
                    }
                )

        return res
