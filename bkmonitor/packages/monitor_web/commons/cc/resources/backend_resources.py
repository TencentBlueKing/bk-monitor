"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import logging
from collections import defaultdict

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework.serializers import ValidationError

from api.cmdb.define import Host
from bkmonitor.strategy.new_strategy import Item
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.country import COUNTRIES, ISP_LIST
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.contrib.cache import CacheResource
from monitor_web.commons.cc.utils import ServiceCategorySearcher, topo_tree_tools
from monitor_web.commons.cc.utils.cmdb import CmdbUtil

logger = logging.getLogger(__name__)


class CountryListResource(Resource):
    """
    获取国家地区城市列表
    """

    def perform_request(self, validated_request_data):
        return COUNTRIES


class ISPListResource(Resource):
    """
    获取运营商列表
    """

    def perform_request(self, validated_request_data):
        return ISP_LIST


class HostRegionISPInfoResource(Resource):
    """
    主机地区和运营商信息
    """

    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        bk_state_name = serializers.CharField(required=False, allow_blank=True)
        bk_province_name = serializers.CharField(required=False, allow_blank=True)
        bk_isp_name = serializers.CharField(required=False, allow_blank=True)

    class ResponseSerializer(serializers.Serializer):
        """
        主机列表及Agent状态
        """

        plat_id = serializers.IntegerField(required=True)
        plat_name = serializers.CharField(required=True, allow_blank=True)
        ip = serializers.CharField(required=True, allow_blank=True)
        bk_host_id = serializers.IntegerField(required=False)
        agent_status = serializers.IntegerField(required=True)
        city = serializers.CharField(required=True, allow_blank=True)
        outer_ip = serializers.CharField(required=True, allow_blank=True)
        country = serializers.CharField(required=True, allow_blank=True, allow_null=True)
        carrieroperator = serializers.CharField(required=True, allow_blank=True, allow_null=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        state_name = params.get("bk_state_name", "")
        province_name = params.get("bk_province_name", "")
        isp_name = params.get("bk_isp_name", "")

        # 按业务模块过滤
        hosts: list[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)

        # 如果省份提供了，则优先使用省份查询
        region_key = province_name or state_name

        # 按地区及运营商过滤
        filtered_hosts = []
        for host in hosts:
            if region_key and region_key not in [host.bk_province_name, host.bk_state_name]:
                continue
            if isp_name and isp_name != host.bk_isp_name:
                continue
            filtered_hosts.append(host)

        # 获取主机的Agent状态
        agent_status: dict[int, int] = resource.cc.get_agent_status(bk_biz_id, filtered_hosts)

        return [
            {
                "plat_id": str(host.bk_cloud_id),
                "plat_name": host.bk_cloud_name,
                "ip": host.bk_host_innerip,
                "bk_host_id": host.bk_host_id,
                "agent_status": agent_status[host.bk_host_id],
                "city": host.bk_province_name,
                "outer_ip": host.bk_host_outerip,
                "country": host.bk_state_name,
                "carrieroperator": host.bk_isp_name,
            }
            for host in filtered_hosts
        ]


class CCTopoTreeResource(CacheResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        instance_type = serializers.ChoiceField(required=False, choices=["host", "service"], label="对象类型")

    many_response_data = True

    def perform_request(self, data):
        bk_biz_id = data["bk_biz_id"]
        result = resource.cc.topo_tree(bk_biz_id)
        if not result:
            return []

        # 判断是否需要查出模块下的主机或实例
        if not data.get("instance_type"):
            return result

        def get_module_dict(topo, module_dict=None):
            if module_dict is None:
                module_dict = {}
            if isinstance(topo, dict):
                child = topo.get("child")
                if isinstance(child, list) and len(child) == 0:
                    module_dict[topo["bk_inst_id"]] = child
                else:
                    get_module_dict(child, module_dict)

            if isinstance(topo, list):
                for item in topo:
                    get_module_dict(item, module_dict)

        module_dict = {}
        # 遍历topo拿到child为空的节点
        get_module_dict(result, module_dict)
        if data["instance_type"] == "host":
            host_list = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
            for host in host_list:
                host_dict = {
                    "bk_host_id": host.bk_host_id,
                    "display_name": host.display_name,
                    "ip": host.bk_host_innerip,
                    "bk_host_innerip": host.bk_host_innerip,
                    "bk_host_innerip_v6": host.bk_host_innerip_v6,
                    "bk_cloud_id": host.bk_cloud_id,
                    "bk_host_name": host.bk_host_name,
                    "os_type": host.bk_os_type_name,
                }
                for module_id in host.bk_module_ids:
                    # 将host添加到对应的模块下
                    if module_id in module_dict:
                        module_dict[module_id].append(host_dict)
                        continue
                    module_dict[module_id] = [host_dict]
        elif data["instance_type"] == "service":
            # 获取所有服务实例，处理它们和主机之间的关系
            service_list = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id)
            for service in service_list:
                service_info = {
                    "service_instance_id": service.service_instance_id,
                    "name": service.name,
                    "bk_module_id": service.bk_module_id,
                    "bk_host_id": service.bk_host_id,
                }
                module_dict[service.bk_module_id].append(service_info)
        return result


class GetHostInstanceByIpResource(CacheResource):
    """
    获取主机状态
    """

    cache_type = CacheType.HOST

    class RequestSerializer(serializers.Serializer):
        class IpSlz(serializers.Serializer):
            ip = serializers.CharField(required=False, label="主机IP")
            bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
            bk_host_id = serializers.IntegerField(required=False, label="主机ID")

            def validate(self, attrs):
                if not attrs.get("ip") and not attrs.get("bk_host_id"):
                    raise serializers.ValidationError(_("ip和bk_host_id不能同时为空"))
                return attrs

        ip_list = IpSlz(required=True, many=True)
        bk_biz_id = serializers.IntegerField(required=True)
        with_external_ips = serializers.BooleanField(required=False, default=False)

    def perform_request(self, data):
        ip_list = data["ip_list"]
        if not ip_list:
            return []

        if ip_list[0].get("bk_host_id"):
            host_list = api.cmdb.get_host_by_id(
                bk_biz_id=data["bk_biz_id"], bk_host_ids=[ip["bk_host_id"] for ip in ip_list]
            )
        else:
            host_list = api.cmdb.get_host_by_ip(ips=ip_list, bk_biz_id=data["bk_biz_id"], search_outer_ip=True)

        # 组合不同业务主机的agent状态
        try:
            agent_status_dict = resource.cc.get_agent_status(data["bk_biz_id"], host_list)
        except Exception as e:
            logger.warning(f"get_agent_status error: {e}")
            agent_status_dict = {}

        agent_status_display = {
            -1: "abnormal",  # 异常(未知)
            0: "normal",  # 正常(Agent正常)
            2: "not_exist",  # Agent未安装
        }

        all_ips = {ip["ip"] for ip in ip_list if "ip" in ip}
        internal_ips = []
        outer_ips = []
        result = []

        # 处理CMDB存在的IP
        for host in host_list:
            is_innerip = False
            is_outerip = False
            agent_status = agent_status_dict.get(host.bk_host_id, -1)
            item = {
                "bk_host_id": host.bk_host_id,
                "display_name": host.display_name,
                "bk_cloud_id": host.bk_cloud_id,
                "bk_cloud_name": host.bk_cloud_name,
                "agent_status": agent_status_display.get(agent_status),
                "bk_os_type": settings.OS_TYPE_NAME_DICT.get(int(host.bk_os_type)) if host.bk_os_type else "",
                "bk_supplier_id": host.bk_supplier_account,
                "is_external_ip": False,
                "is_innerip": is_innerip,
                "is_outerip": is_outerip,
            }
            if host.bk_host_innerip in all_ips:
                first_item = copy.deepcopy(item)
                first_item["is_innerip"] = True
                first_item["ip"] = host.bk_host_innerip
                internal_ips.append(host.bk_host_innerip)
                result.append(first_item)
            elif host.bk_host_outerip in all_ips:
                second_item = copy.deepcopy(item)
                second_item["is_outerip"] = True
                second_item["ip"] = host.bk_host_outerip
                outer_ips.append(host.bk_host_outerip)
                result.append(second_item)
            else:
                item["is_innerip"] = True
                item["ip"] = host.bk_host_innerip
                result.append(item)
        # 处理不存在于CMDB的IP
        external_ips = list(all_ips - set(internal_ips) - set(outer_ips))
        for ip in external_ips:
            if data["with_external_ips"]:
                result.append(
                    {
                        "bk_host_id": 0,
                        "ip": ip,
                        "bk_cloud_id": "",
                        "bk_cloud_name": "",
                        "agent_status": "",
                        "bk_os_type": "",
                        "bk_supplier_id": "",
                        "is_external_ip": True,
                        "is_innerip": False,
                        "is_outerip": False,
                    }
                )
        return result


class GetHostInstanceByNodeResource(CacheResource):
    """
    获取节点下主机状态
    """

    cache_type = CacheType.HOST

    def __init__(self):
        super().__init__()
        self.node_list = []
        self.bk_biz_id = None
        # 用于查询模块和服务分类之间的关系
        self.need_search_module_ids = set()

    class RequestSerializer(serializers.Serializer):
        class NodeSlz(serializers.Serializer):
            bk_obj_id = serializers.CharField(required=True, label="节点类型")
            bk_inst_id = serializers.IntegerField(required=True, label="实例ID")
            bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
            bk_inst_name = serializers.CharField(required=False, label="节点名称")
            SERVICE_TEMPLATE = serializers.IntegerField(required=False, label="所属服务模板ID")
            SET_TEMPLATE = serializers.IntegerField(required=False, label="所属集群模板ID")

        node_list = NodeSlz(required=True, many=True)
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        with_count = serializers.BooleanField(required=False, label="是否需要主机/实例的统计信息", default=True)
        with_service_category = serializers.BooleanField(required=False, label="是否需要主机信息", default=True)

    def get_instance_count(self):
        # 查询业务下的主机
        host_list = api.cmdb.get_host_by_topo_node(bk_biz_id=self.bk_biz_id)

        # 查询主机的agent状态
        agent_status_dict = resource.cc.get_agent_status(self.bk_biz_id, host_list)

        # 每个节点下的主机
        node_host = defaultdict(set)
        node_agent_error_count = defaultdict(set)
        for host in host_list:
            # 每台主机所属的模块数量不会太多
            for bk_module_id in host.bk_module_ids:
                node_host[bk_module_id].add(host.bk_host_id)

                # agent状态
                if agent_status_dict.get(host.bk_host_id, -1) != 0:
                    node_agent_error_count[bk_module_id].add(host.bk_host_id)

        for node in self.node_list:
            all_host = set()
            agent_error_count = set()
            # 遍历所需节点，拿到所需节点的主机
            for bk_module_id in node["module_ids"]:
                if node_host.get(bk_module_id):
                    all_host.update(node_host[bk_module_id])
                    if node_agent_error_count.get(bk_module_id):
                        agent_error_count = agent_error_count | node_agent_error_count[bk_module_id]

            node["all_host"] = list(all_host)
            node["count"] = len(all_host)
            node["agent_error_count"] = len(agent_error_count)

        del node_host
        del node_agent_error_count

    def perform_request(self, validated_request_data):
        # 查询拓扑数和节点映射
        self.bk_biz_id = validated_request_data["bk_biz_id"]
        self.node_list = validated_request_data["node_list"]
        topo_tree = resource.cc.topo_tree(self.bk_biz_id)
        node_mapping = topo_tree_tools.get_node_mapping(topo_tree)

        # 获取节点的全路径
        for node in self.node_list:
            inst_key = topo_tree_tools.get_inst_key(node)
            # 补充节点名字
            if not node.get("bk_inst_name"):
                node["bk_inst_name"] = node_mapping.get(inst_key, {}).get("bk_inst_name")
            node["node_path"] = topo_tree_tools.get_node_path(inst_key, node_mapping)
            # 统计模块信息，为查询主机和服务分类使用
            node["module_ids"] = topo_tree_tools.get_module_by_node(node_mapping.get(inst_key))
            self.need_search_module_ids = self.need_search_module_ids | node["module_ids"]

        # 统计主机信息
        if validated_request_data["with_count"]:
            self.get_instance_count()

        if validated_request_data["with_service_category"]:
            # 查询服务分类
            service_category_searcher = ServiceCategorySearcher()
            service_category_ids = set()
            module_service_category_info = {}
            module_service_template_info = {}
            modules = api.cmdb.get_module(
                bk_biz_id=int(self.bk_biz_id), bk_module_ids=list(self.need_search_module_ids)
            )
            for module in modules:
                service_category_ids.add(module.service_category_id)
                module_service_category_info[module.bk_module_id] = (
                    self.bk_biz_id,
                    module.service_category_id,
                )
                module_service_template_info[module.bk_module_id] = module.service_template_id

            for node in self.node_list:
                module_ids = node["module_ids"]
                config_service_categorys = {
                    module_service_category_info[module_id]
                    for module_id in module_ids
                    if module_id in module_service_category_info
                }
                node["labels"] = [
                    service_category_searcher.search(*category)
                    for category in config_service_categorys
                    if service_category_searcher.search(*category)
                ]
                if node["bk_obj_id"] == "module":
                    node[TargetNodeType.SERVICE_TEMPLATE] = module_service_template_info.get(node["bk_inst_id"])

        # 删除不需要的键
        for node in self.node_list:
            node.pop("module_ids")

        return self.node_list


class GetServiceInstanceByNodeResource(GetHostInstanceByNodeResource):
    """
    获取节点服务实例状态
    """

    def get_instance_count(self):
        # 查询业务下的主机
        host_list = api.cmdb.get_host_by_topo_node(bk_biz_id=self.bk_biz_id)

        # 主机host_id到主机的映射
        host_id_mapping = {}
        for host in host_list:
            host_id_mapping[host.bk_host_id] = host

        # 获取业务下的所有实例
        service_list = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=self.bk_biz_id)

        # 找到需要查询agent状态的服务实例
        need_search_host_ids = {
            service.bk_host_id for service in service_list if service.bk_module_id in self.need_search_module_ids
        }

        # 查询主机的agent状态
        agent_status_dict = resource.cc.get_agent_status(
            self.bk_biz_id, [host for host in host_list if host.bk_host_id in need_search_host_ids]
        )

        # 每个节点下的实例
        node_host = defaultdict(set)
        node_service = defaultdict(set)
        node_agent_error_count = defaultdict(set)
        for service in service_list:
            # 查找实例关联的主机
            host = host_id_mapping.get(service.bk_host_id)
            if host is None:
                continue
            node_service[service.bk_module_id].add(service.service_instance_id)
            node_host[service.bk_module_id].add(host.bk_host_id)
            # agent状态
            if agent_status_dict.get(host.bk_host_id, -1) != 0:
                node_agent_error_count[service.bk_module_id].add(host.bk_host_id)

        # 统计每个节点的实例数，异常数
        for node in self.node_list:
            agent_error_count = set()
            all_host = set()
            all_service = set()
            for bk_module_id in node["module_ids"]:
                if node_host.get(bk_module_id):
                    all_host.update(node_host[bk_module_id])
                    all_service = all_service | node_service[bk_module_id]
                    if node_agent_error_count.get(bk_module_id):
                        agent_error_count = agent_error_count | node_agent_error_count[bk_module_id]

            node["all_host"] = list(all_host)
            node["count"] = len(all_service)
            node["agent_error_count"] = len(agent_error_count)

        del node_service
        del node_host
        del node_agent_error_count


class GetServiceCategory(Resource):
    # 获取服务分类列表
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        base_result = api.cmdb.search_service_category(bk_biz_id=validated_request_data["bk_biz_id"])
        return_data = []
        children_dict = {}
        for result in base_result:
            if not result.get("bk_parent_id"):
                return_data.append({"id": result.get("id"), "name": result.get("name"), "children": []})
            else:
                children_dict[result.get("bk_parent_id")] = []

        for result in base_result:
            if result.get("bk_parent_id") in children_dict:
                children_dict[result["bk_parent_id"]].append({"id": result.get("id"), "name": result.get("name")})

        for data in return_data:
            data["children"] = children_dict.get(data["id"], [])

        return return_data


class GetMainlineObjectTopo(Resource):
    """
    获取主线模型
    """

    def generate_topo(self, bk_obj_name, bk_obj_id):
        """
        生成相应的模型拓扑
        :param bk_obj_name: 拓扑目标名称
        :param bk_obj_id: 拓扑目标ID
        :return: 拓扑format
        """
        return {
            "bk_pre_obj_name": "",
            "bk_obj_name": bk_obj_name,
            "bk_next_obj": "",
            "bk_next_name": "",
            "bk_obj_id": bk_obj_id,
            "bk_supplier_account": "0",
            "bk_pre_obj_id": "",
        }

    def perform_request(self, params):
        object_topo = api.cmdb.get_mainline_object_topo()
        object_topo.append(self.generate_topo(_("集群模板"), "SET_TEMPLATE"))
        object_topo.append(self.generate_topo(_("服务模板"), "SERVICE_TEMPLATE"))
        return object_topo


class GetTemplateResource(Resource):
    """
    查询模板列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_obj_id = serializers.ChoiceField(
            required=True, choices=[TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE], label="查询对象"
        )
        bk_inst_type = serializers.ChoiceField(
            required=True, choices=[TargetObjectType.HOST, TargetObjectType.SERVICE], label="目标对象类型"
        )
        with_count = serializers.BooleanField(required=False, default=False, label="需要带节点数量和实例数量返回")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bk_obj_id = validated_request_data["bk_obj_id"]
        bk_inst_type = validated_request_data["bk_inst_type"]
        with_count = validated_request_data["with_count"]

        templates = api.cmdb.get_dynamic_query(dict(bk_biz_id=bk_biz_id, dynamic_type=bk_obj_id))
        for template in templates.get("children", []):
            template["bk_inst_id"] = template.pop("id")
            template["bk_inst_name"] = template.pop("name")
            template["bk_obj_id"] = bk_obj_id

        # 需要带节点数量和实例数量返回
        if with_count:
            nodes = resource.commons.get_nodes_by_template(
                dict(
                    bk_biz_id=bk_biz_id,
                    bk_obj_id=bk_obj_id,
                    bk_inst_type=bk_inst_type,
                    bk_inst_ids=[template["bk_inst_id"] for template in templates.get("children", [])],
                )
            )
            template_instances = {}
            template_nodes = {}
            for node in nodes:
                template_id = node.get(bk_obj_id)
                if template_id not in template_nodes:
                    template_nodes[template_id] = 0
                template_nodes[template_id] += 1

                if template_id not in template_instances:
                    template_instances[template_id] = 0
                template_instances[template_id] += node["count"]

            for template in templates.get("children", []):
                template["bk_biz_id"] = bk_biz_id
                template["nodes_count"] = template_nodes.get(template["bk_inst_id"], 0)
                template["instances_count"] = template_instances.get(template["bk_inst_id"], 0)
        return templates


class GetNodesByTemplate(CacheResource):
    """
    获取服务模板、集群模板下相应的节点
    """

    cache_type = CacheType.HOST

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_obj_id = serializers.ChoiceField(
            required=True, choices=[TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE], label="查询对象"
        )
        bk_inst_ids = serializers.ListField(required=True, label="相应的模板ID")
        bk_inst_type = serializers.ChoiceField(
            required=True, choices=[TargetObjectType.HOST, TargetObjectType.SERVICE], label="查询对象下实例的类型"
        )

    def perform_request(self, data):
        bk_inst_ids = data["bk_inst_ids"]
        bk_obj_id = data["bk_obj_id"]
        bk_biz_id = data["bk_biz_id"]
        bk_inst_type = data["bk_inst_type"]
        bk_nodes = []
        result = []

        # 如果是需要获得相应动态模板下的主机
        # 获取最底层节点的实例
        template_id_field = ""
        if bk_obj_id == TargetNodeType.SET_TEMPLATE:
            template_id_field = "set_template_id"
            bk_nodes = api.cmdb.get_set(bk_biz_id=bk_biz_id, set_template_ids=bk_inst_ids)
        elif bk_obj_id == TargetNodeType.SERVICE_TEMPLATE:
            template_id_field = "service_template_id"
            bk_nodes = api.cmdb.get_module(bk_biz_id=bk_biz_id, service_template_ids=bk_inst_ids)

        args = {
            "bk_biz_id": bk_biz_id,
            "node_list": [
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_inst_id": node.bk_inst_id,
                    "bk_inst_name": node.bk_inst_name,
                    "bk_obj_id": node.bk_obj_id,
                    bk_obj_id: getattr(node, template_id_field, ""),
                }
                for node in bk_nodes
            ],
        }
        if bk_inst_type == TargetObjectType.HOST:
            result = resource.commons.get_host_instance_by_node(args)

        if bk_inst_type == TargetObjectType.SERVICE:
            result = resource.commons.get_service_instance_by_node(args)
        return result


class GetBusinessTargetDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        target = serializers.ListField(
            allow_empty=True, child=serializers.ListField(child=Item.Serializer.TargetSerializer()), default=list
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        target = validated_request_data["target"]

        return CmdbUtil.get_target_detail(bk_biz_id, target)


class GetDynamicGroupInstanceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dynamic_group_ids = serializers.ListField(label="动态分组ID", child=serializers.CharField())

    def perform_request(self, params):
        dynamic_groups = api.cmdb.search_dynamic_group(
            bk_biz_id=params["bk_biz_id"],
            bk_obj_id="host",
            dynamic_group_ids=params["dynamic_group_ids"],
            with_count=True,
            with_instance_id=True,
        )

        result = []
        for dynamic_group in dynamic_groups:
            result.append(
                {
                    "name": dynamic_group["name"],
                    "dynamic_group_id": dynamic_group["id"],
                    "count": dynamic_group["count"],
                    "all_host": dynamic_group["instance_ids"],
                }
            )
        return result


class GetTopoListResource(Resource):
    """获取模块、集群节点ID列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(label="业务ID列表", child=serializers.IntegerField())
        bk_obj_id = serializers.CharField(label="对象ID")
        condition = serializers.JSONField(label="查询条件", required=False, default=dict)
        OBJ_ID_CHOOSE = ("module", "set")

        def validate(self, attrs):
            if attrs["bk_obj_id"] not in ["module", "set"]:
                raise ValidationError(f"bk_obj_id must be one of {self.OBJ_ID_CHOOSE}")
            return attrs

    def perform_request(self, validated_request_data):
        bk_biz_ids = set(validated_request_data["bk_biz_ids"])
        bk_biz_ids = set(b.bk_biz_id for b in api.cmdb.get_business() if b.bk_biz_id in bk_biz_ids)
        bk_obj_id = validated_request_data["bk_obj_id"]
        condition: dict = validated_request_data.get("condition")
        fun_map = {"module": self.get_modules, "set": self.get_sets}

        return fun_map[bk_obj_id](bk_biz_ids, condition)

    def get_modules(self, bk_biz_ids: list[int], condition: dict):
        module_list = []
        fields = ["bk_module_id", "bk_module_name", "bk_biz_id"]
        params = self._get_query_params(bk_biz_ids, fields, condition)
        for modules in api.cmdb.get_module.bulk_request(params, ignore_exceptions=True):
            for m in modules:
                module_list.append(self._get_attr_value(m, fields))
        return module_list

    def get_sets(self, bk_biz_ids: list[int], condition: dict):
        set_list = []
        fields = ["bk_set_id", "bk_set_name", "bk_biz_id"]
        params = self._get_query_params(bk_biz_ids, fields, condition)
        for sets in api.cmdb.get_set.bulk_request(params, ignore_exceptions=True):
            for s in sets:
                set_list.append(self._get_attr_value(s, fields))
        return set_list

    def _get_query_params(self, bk_biz_ids: list[int], fields: list[str], condition: dict):
        query_params = []
        for biz_id in bk_biz_ids:
            param = {"bk_biz_id": biz_id, "fields": fields}
            if condition:
                param["condition"] = condition
            query_params.append(param)
        return query_params

    def _get_attr_value(self, obj, attr_names: list):
        res = {}
        for attr in attr_names:
            if hasattr(obj, attr):
                res[attr] = getattr(obj, attr)
            else:
                res[attr] = obj._extra_attr.get(attr)
        return res
