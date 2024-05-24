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

from django.core.cache import cache
from django.utils.translation import ugettext as _

from bkmonitor.utils.common_utils import logger
from bkmonitor.utils.local import local
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.strategy import TargetFieldType
from core.drf_resource import api, resource
from monitor_web.commons.cc.utils import topo_tree_tools
from utils import business
from utils.time_status import TimeStats


class CmdbUtil(object):
    """
    用于获取节点的CMDB的通用类，提供服务分类搜索查询，主机数/实例数搜索查询，拓扑数/模块/节点查询等多种功能
    """

    CACHE_EXPIRES = 60 * 60  # todo 待CMDB的服务分类接入ESB后，打开celery任务，并把时间周期调小

    def __init__(self, bk_biz_id=None):
        # 使用该类时，建议传入bk_biz_id的初始化参数，可为int或list，若不传，则去查询所有业务下的缓存

        if isinstance(bk_biz_id, int):
            biz_ids = [bk_biz_id]
        elif isinstance(bk_biz_id, list):
            biz_ids = bk_biz_id
        else:
            biz_result = api.cmdb.get_business()
            # 过滤掉查询结果为0的情况
            biz_ids = [biz.bk_biz_id for biz in biz_result if biz.bk_biz_id]

        # 初始化业务数据信息
        self.biz_data = {}
        for biz_id in biz_ids:
            self.biz_data[biz_id] = self.get_cache_data(biz_id)
            if not self.biz_data[biz_id]:
                self.biz_data[biz_id] = self.refresh_biz_data(biz_id)

    @classmethod
    def get_cache_key(cls, bk_biz_id):
        return "web_cache:cc:bkmonitor:cc_util:biz:{}".format(bk_biz_id)

    @classmethod
    def get_cache_data(cls, bk_biz_id):
        cache_key = cls.get_cache_key(bk_biz_id)
        return cache.get(cache_key, None)

    @classmethod
    def refresh_biz_data(cls, bk_biz_id):
        logger.info("update cmdb util cache in biz {}".format(bk_biz_id))

        topo_tree = resource.cc.topo_tree(bk_biz_id)

        # 若业务没有拓扑树，则不去写缓存，直接返回
        if not topo_tree:
            return

        # 获取模块和服务分类的对应关系
        modules = api.cmdb.get_module(bk_biz_id=bk_biz_id)
        module_info = {}
        for module in modules:
            bk_module_id = module.bk_module_id
            module_info[bk_module_id] = {"service_category_id": module.service_category_id}

        # 获取所有的服务分类
        res_service_category = api.cmdb.search_service_category(bk_biz_id=bk_biz_id)
        service_categories_mapping = {}
        for category in res_service_category:
            category_id = category["id"]
            service_categories_mapping[category_id] = category

        host_list = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)

        # 获取主机的agent的状态
        agent_status_dict = resource.cc.get_agent_status(bk_biz_id, host_list)

        # 以host_id为key的所有主机的字典，包括ip，bkcloudid，bk_host_id,agent
        host_info = {}
        for host in host_list:
            agent_status = agent_status_dict.get(host.bk_host_id, -1)
            host_info[host.bk_host_id] = {
                "ip": host.bk_host_innerip,
                "bk_cloud_id": host.bk_cloud_id,
                "agent_status": agent_status,
                "module_ids": set(host.bk_module_ids),
            }

        # 获取业务下的所有实例
        service_list = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id)
        service_info = {}
        for service in service_list:
            host_status = host_info.get(service.bk_host_id, {}).get("agent_status", -1)
            service_info[service.service_instance_id] = {
                "bk_module_id": service.bk_module_id,
                "name": service.name,
                "host_status": host_status,
            }

        biz_data = {
            "host_info": host_info,  # 主机字典，键名为bk_host_id，
            "service_info": service_info,  # 服务实例字典，键名为service_instance_id
            "node_mapping": topo_tree_tools.get_node_mapping(topo_tree),  # 节点字典，键名为inst_key
            "module_info": module_info,  # 模块信息字典，包含服务分类信息，键名为module_id
            "topo_tree": topo_tree,  # 拓扑树
            "service_category_mapping": service_categories_mapping,  # 服务分类字典，键名为service_category_id
        }

        # 更新缓存
        cache.set(cls.get_cache_key(bk_biz_id), biz_data, cls.CACHE_EXPIRES)
        return biz_data

    @classmethod
    def refresh(cls):
        biz_result = business.get_all_activate_business()
        for biz_id in biz_result:
            local.username = business.maintainer(str(biz_id))
            cls.refresh_biz_data(biz_id)

    @staticmethod
    def _search_category(category_id, service_category_mapping):
        service_category = service_category_mapping.get(category_id)
        if not service_category:
            return None
        label = {"first": "", "second": ""}
        if service_category.get("bk_parent_id"):
            parent_info = service_category_mapping.get(service_category["bk_parent_id"], {})
            label["first"] = parent_info.get("name", "")
            label["second"] = service_category.get("name", "")
        else:
            label["first"] = service_category.get("name", "")

        return label

    @staticmethod
    def _get_contained_modules(node_list, node_mapping):
        contained_module_ids = set()
        for node in node_list:
            inst_key = topo_tree_tools.get_inst_key(node)
            if inst_key in node_mapping:
                module_ids = topo_tree_tools.get_module_by_node(node_mapping[inst_key])
                contained_module_ids = contained_module_ids | module_ids

        return contained_module_ids

    @staticmethod
    def _get_service_category(module_ids, module_info):
        """
        获取服务分类
        """
        service_category_ids = set()

        for module_id in module_ids:
            service_category_id = module_info.get(module_id, {}).get("service_category_id")
            if service_category_id:
                service_category_ids.add(service_category_id)

        return service_category_ids

    @staticmethod
    def _get_host_count(module_ids, host_info):
        """
        查询主机总数，异常数
        """
        total_count = 0
        error_count = 0

        for host in list(host_info.values()):
            if host["module_ids"] & module_ids:
                total_count += 1
                if host["agent_status"] != 0:
                    error_count += 1

        return {"total_count": total_count, "error_count": error_count}

    @staticmethod
    def _get_service_count(module_ids, service_info):
        total_count = 0
        error_count = 0

        for service in list(service_info.values()):
            if service["bk_module_id"] in module_ids:
                total_count += 1
                if service["host_status"] != 0:
                    error_count += 1

        return {"total_count": total_count, "error_count": error_count}

    def get_cc_info_by_node_list(self, bk_biz_id, node_list, node_type="HOST", condition=None):
        """
        获取配置中心的信息（主机数、异常数、服务分类等）
        """
        ts = TimeStats(_("获取CC信息"))

        biz_data = self.biz_data.get(bk_biz_id)

        if condition is None:
            condition = {}

        # 节点列表所包含的module_id的并集，用于搜索主机、实例和查询服务分类
        contained_module_ids = self._get_contained_modules(node_list, biz_data["node_mapping"])

        result = {}
        ts.split(_("获取服务分类"))
        if condition.get("service_category"):
            service_category_ids = self._get_service_category(contained_module_ids, biz_data["module_info"])
            service_category = []
            for category_id in service_category_ids:
                category_result = self._search_category(category_id, biz_data["service_category_mapping"])
                if category_result:
                    service_category.append(category_result)
            result.update({"service_category": service_category})

        ts.split(_("获取数目"))
        if condition.get("instance_count"):
            if node_type == "HOST":
                count_result = self._get_host_count(contained_module_ids, biz_data["host_info"])
            else:
                count_result = self._get_service_count(contained_module_ids, biz_data["service_info"])
            result.update(**count_result)

        ts.stop()
        # logger.info(ts.display())
        return result

    def get_category_list(self, bk_biz_id, node_list):
        """
        根据节点获取所有的服务分类id
        """
        biz_data = self.biz_data.get(bk_biz_id)
        if biz_data:
            contained_module_ids = self._get_contained_modules(node_list, biz_data["node_mapping"])

            # 根据节点下的module id 找到相关联的category id
            service_category_ids = self._get_service_category(contained_module_ids, biz_data["module_info"])
            return service_category_ids
        else:
            return []

    def get_category_id(self, bk_biz_id, target_category):
        """
        根据一、二级服务分类名称查询服务分类id
        """
        biz_data = self.biz_data.get(bk_biz_id)
        category_mapping = biz_data["service_category_mapping"]
        for key, category in list(category_mapping.items()):
            if category.get("bk_parent_id") and category["name"] == target_category[1]:
                parent_info = category_mapping.get(category["bk_parent_id"], {})
                parent_name = parent_info.get("name", "")
                if parent_name == target_category[0]:
                    return category["id"]
        else:
            return None

    def fuzzy_search_service_category(self, bk_biz_id, target_category):
        """
        模糊搜索服务分类
        """
        biz_data = self.biz_data.get(bk_biz_id)
        category_ids = set()
        service_category_mapping = biz_data["service_category_mapping"]
        for key, category in list(service_category_mapping.items()):
            if not category.get("bk_parent_id"):
                continue
            parent_info = service_category_mapping.get(category["bk_parent_id"], {})
            service_category = "{}-{}".format(parent_info.get("name", ""), category.get("name", ""))
            if target_category in service_category:
                category_ids.add(category["id"])
        return category_ids

    def get_node_path(self, bk_biz_id, node_list):
        """
        获取节点的路径
        """
        biz_data = self.biz_data.get(bk_biz_id)
        result = []
        for node in node_list:
            inst_key = topo_tree_tools.get_inst_key(node)

            node_link = biz_data["node_mapping"].get(inst_key, {}).get("node_link", [])
            node_link_list = [biz_data["node_mapping"].get(key, {}).get("bk_inst_name") for key in node_link]
            result.append(node_link_list)

        return result

    def get_service_name(self, bk_biz_id, service_ids):
        """
        获取实例的名称
        """
        biz_data = self.biz_data.get(bk_biz_id)
        return [
            biz_data["service_info"][service_id]["name"]
            for service_id in service_ids
            if biz_data["service_info"].get(service_id)
        ]

    @staticmethod
    def get_target_hosts(bk_biz_id, target):
        """
        获取target下的host列表
        :param bk_biz_id: 业务id
        :param target: target规则
        """
        hosts = []

        if not target:
            return []

        # 此处两层for循环是因为target是两层的
        for item in target:
            for condition in item:
                field = condition["field"].lower()
                values = condition["value"]

                # 处理如果是拓扑节点的情况
                if field == "host_topo_node":
                    topo_nodes = {}
                    for item in values:
                        bk_obj_id = item.get("bk_obj_id")
                        bk_inst_id = item.get("bk_inst_id")
                        if bk_obj_id and bk_inst_id:
                            topo_node = topo_nodes.setdefault(bk_obj_id, [])
                            topo_node.append(bk_inst_id)
                    hosts += api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id, topo_nodes=topo_nodes)

                # 处理纯ip的情况
                elif field == "ip":
                    hosts += api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=values)

                # 处理服务模板的情况
                elif field == "host_service_template":
                    set_template_ids = []
                    serviec_template_ids = []
                    for item in values:
                        bk_obj_id = item.get("bk_obj_id")
                        bk_inst_id = item.get("bk_inst_id")
                        if bk_obj_id == TargetNodeType.SET_TEMPLATE:
                            set_template_ids.append(bk_inst_id)
                        elif bk_obj_id == TargetNodeType.SERVICE_TEMPLATE:
                            serviec_template_ids.append(bk_inst_id)
                    if set_template_ids:
                        hosts += api.cmdb.get_host_by_template(
                            bk_biz_id=bk_biz_id,
                            bk_obj_id=TargetNodeType.SET_TEMPLATE,
                            template_ids=set_template_ids,
                        )
                    if serviec_template_ids:
                        hosts += api.cmdb.get_host_by_template(
                            bk_biz_id=bk_biz_id,
                            bk_obj_id=TargetNodeType.SERVICE_TEMPLATE,
                            template_ids=serviec_template_ids,
                        )
        return hosts

    @staticmethod
    def get_target_detail(bk_biz_id: int, target: List[List[Dict]]):
        """
        target : [
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ],
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ]
                ]
        target理论上支持多个列表以或关系存在，列表内部亦存在多个对象以且关系存在，
        由于目前产品形态只支持单对象的展示，因此若存在多对象，只取第一个对象返回给前端
        """
        target_type_map = {
            TargetFieldType.host_target_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_topo: TargetNodeType.TOPO,
            TargetFieldType.service_topo: TargetNodeType.TOPO,
            TargetFieldType.service_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.service_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.host_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_set_template: TargetNodeType.SET_TEMPLATE,
        }
        obj_type_map = {
            TargetFieldType.host_target_ip: TargetObjectType.HOST,
            TargetFieldType.host_ip: TargetObjectType.HOST,
            TargetFieldType.host_topo: TargetObjectType.HOST,
            TargetFieldType.service_topo: TargetObjectType.SERVICE,
            TargetFieldType.service_service_template: TargetObjectType.SERVICE,
            TargetFieldType.service_set_template: TargetObjectType.SERVICE,
            TargetFieldType.host_service_template: TargetObjectType.HOST,
            TargetFieldType.host_set_template: TargetObjectType.HOST,
        }
        info_func_map = {
            TargetFieldType.host_target_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.host_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.service_topo: resource.commons.get_service_instance_by_node,
            TargetFieldType.host_topo: resource.commons.get_host_instance_by_node,
            TargetFieldType.service_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.service_set_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_set_template: resource.commons.get_nodes_by_template,
        }

        # 判断target格式是否符合预期
        if not target or not target[0]:
            return None
        else:
            target = target[0][0]

        field = target.get("field")
        if not field or not target.get("value"):
            return None

        params = {"bk_biz_id": bk_biz_id}
        if field in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            params["ip_list"] = []
            for x in target["value"]:
                if x.get("bk_host_id"):
                    ip = {"bk_host_id": x["bk_host_id"]}
                elif x.get("bk_target_ip"):
                    ip = {"ip": x["bk_target_ip"], "bk_cloud_id": x["bk_target_cloud_id"]}
                else:
                    ip = {"ip": x["ip"], "bk_cloud_id": x["bk_cloud_id"]}
                params["ip_list"].append(ip)
            params["bk_biz_ids"] = [bk_biz_id]
        elif field in [
            TargetFieldType.host_set_template,
            TargetFieldType.host_service_template,
            TargetFieldType.service_set_template,
            TargetFieldType.service_service_template,
        ]:
            params["bk_obj_id"] = target_type_map[field]
            params["bk_inst_type"] = obj_type_map[field]
            params["bk_inst_ids"] = [inst["bk_inst_id"] for inst in target["value"]]
        else:
            node_list = target.get("value")
            for target_item in node_list:
                if "bk_biz_id" not in target_item:
                    target_item.update(bk_biz_id=bk_biz_id)
            params["node_list"] = node_list

        target_detail = info_func_map[field](params)

        # 统计实例数量
        if field in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            instance_count = len(target_detail)
        else:
            instances = set()
            for node in target_detail:
                instances.update(node.get("all_host", []))
            instance_count = len(instances)

        return {
            "node_type": target_type_map[field],
            "node_count": len(target["value"]),
            "instance_type": obj_type_map[field],
            "instance_count": instance_count,
            "target_detail": target_detail,
        }
