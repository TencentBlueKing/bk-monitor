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
import copy
import logging
import typing
from collections import defaultdict
from typing import Any, Dict, List

from django.conf import settings
from django.utils.translation import ugettext as _
from pypinyin import lazy_pinyin
from rest_framework import serializers

from api.cmdb.define import _split_member_list
from bkm_space.api import SpaceApi
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.utils.ip import exploded_ip, is_v6
from constants.cmdb import TargetNodeType
from core.drf_resource import CacheResource, api
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError

from . import client
from .define import Business, Host, Module, Process, ServiceInstance, Set, TopoTree

logger = logging.getLogger(__name__)


def split_inner_host(bk_host_innerip_str):
    bk_host_innerip = _split_member_list(bk_host_innerip_str)
    if not bk_host_innerip:
        return ""
    return bk_host_innerip[0]


@using_cache(CacheType.CC_CACHE_ALWAYS, is_cache_func=lambda res: res)
def get_host_dict_by_biz(bk_biz_id, fields):
    """
    按业务查询主机（未实例化）
    :param bk_biz_id: 业务ID
    :type bk_biz_id: int
    :param fields: 查询字段
    :type fields: list
    :return: 主机列表
    :rtype: list
    """
    records = batch_request(client.list_biz_hosts_topo, {"bk_biz_id": bk_biz_id, "fields": fields})

    hosts = []
    for record in records:
        host = _host_from_raw(record, bk_biz_id)
        if host is not None:
            hosts.append(host)
    return hosts


def _host_from_raw(record, bk_biz_id):
    host = record["host"]

    host["bk_host_innerip"] = split_inner_host(host["bk_host_innerip"])
    host["bk_host_innerip_v6"] = split_inner_host(host.get("bk_host_innerip_v6", ""))
    if not host["bk_host_innerip"] and not host["bk_host_innerip_v6"]:
        return None
    host["ip"] = host["bk_host_innerip"]
    topo = record["topo"]

    set_ids = []
    module_ids = []
    for set_info in topo:
        set_ids.append(set_info["bk_set_id"])
        for module_info in set_info["module"]:
            module_ids.append(module_info["bk_module_id"])

    host["bk_set_ids"] = set_ids
    host["bk_module_ids"] = module_ids

    host["operator"] = _split_member_list(host.get("operator", ""))
    host["bk_bak_operator"] = _split_member_list(host.get("bk_bak_operator", ""))
    host["bk_biz_id"] = bk_biz_id
    host["bk_state"] = host.get("srv_status") or host.get("bk_state") or ""
    return host


def _host_full_cloud(host, clouds=None):
    # 获取云区域信息
    if clouds is None:
        clouds = api.cmdb.search_cloud_area()
    cloud_id_to_name = {cloud["bk_cloud_id"]: cloud["bk_cloud_name"] for cloud in clouds}
    host["bk_cloud_name"] = cloud_id_to_name.get(host["bk_cloud_id"], "")
    return host


def sort_topo_tree_by_pinyin(topo_trees):
    """
    利用深度优先遍历。将拓扑结构按拼音排序
    """
    if not topo_trees:
        return topo_trees
    topo_trees.sort(key=lambda topo: lazy_pinyin(topo["bk_inst_name"])[0])
    for topo_tree in topo_trees:
        sort_topo_tree_by_pinyin(topo_tree["child"])

    return topo_trees


def _get_topo_tree(bk_biz_id):
    """
    获取业务拓扑树（未实例化）
    :param bk_biz_id: 业务ID
    :type bk_biz_id: int
    :return: 拓扑树
    :rtype: Dict
    """
    response_data = client.search_biz_inst_topo(bk_biz_id=bk_biz_id)
    if response_data:
        response_data = response_data[0]
    else:
        response_biz_data = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
        if response_biz_data:
            biz_data = response_biz_data[0]
            bk_inst_name = biz_data.bk_biz_name
        else:
            bk_inst_name = _("未知")

        response_data = {
            "host_count": 0,
            "default": 0,
            "bk_obj_name": _("业务"),
            "bk_obj_id": "biz",
            "service_instance_count": 0,
            "child": [],
            "service_template_id": 0,
            "bk_inst_id": bk_biz_id,
            "bk_inst_name": bk_inst_name,
        }

    # 添加空闲集群/模块
    internal_module = client.get_biz_internal_module(
        bk_biz_id=bk_biz_id, bk_supplier_account=settings.BK_SUPPLIER_ACCOUNT
    )
    if internal_module:
        # 仅支持cmdb空间获取该信息
        if not internal_module["module"]:
            internal_module["module"] = []

        internal_module = dict(
            bk_obj_id="set",
            bk_obj_name=_("集群"),
            bk_inst_id=internal_module["bk_set_id"],
            bk_inst_name=internal_module["bk_set_name"],
            child=[
                dict(
                    bk_obj_id="module",
                    bk_obj_name=_("模块"),
                    bk_inst_id=m["bk_module_id"],
                    bk_inst_name=m["bk_module_name"],
                    child=[],
                )
                for m in internal_module["module"] or []
            ],
        )

        response_data["child"] = [internal_module] + response_data["child"]
    return sort_topo_tree_by_pinyin([response_data])[0]


@using_cache(CacheType.CC_CACHE_ALWAYS, is_cache_func=lambda res: res)
def get_service_instance_by_biz(bk_biz_id):
    """
    获取业务下所有服务实例
    :param bk_biz_id: 业务ID
    :type bk_biz_id: int
    :return: 服务实例列表
    :rtype: list
    """
    return batch_request(client.list_service_instance_detail, {"bk_biz_id": bk_biz_id})


def _trans_topo_node_to_module_ids(bk_biz_id: int, topo_nodes: Dict[str, typing.Iterable[int]]) -> typing.Set[int]:
    """
    将待查询的拓扑节点转为模块ID
    :param topo_nodes: 拓扑节点
    [
        "module": [1, 2],
        "set": [3, 4]
    ]
    :return: 模块ID列表
    :rtype: List[int]
    """

    # 取出模块ID
    module_ids = {int(module_id) for module_id in topo_nodes.pop("module", [])}

    # 如果没有待查询节点，则直接返回
    if not topo_nodes:
        return module_ids

    # 查询拓扑树
    topo_tree: Dict = _get_topo_tree(bk_biz_id)

    # 调整待查询拓扑节点结构，合并相同类型的节点
    for bk_obj_id in topo_nodes:
        topo_nodes[bk_obj_id] = {int(topo_node_id) for topo_node_id in topo_nodes[bk_obj_id]}

    # 广度优先遍历拓扑树，找到节点下所有的模块ID
    queue: List[Dict] = topo_tree["child"]
    while queue:
        node = queue.pop()

        # 如果该节点需要被查询，则标记其子节点
        if node.get("mark") or node["bk_inst_id"] in topo_nodes.get(node["bk_obj_id"], []):
            node["mark"] = True
            for child in node["child"]:
                child["mark"] = True

        if node["bk_obj_id"] == "module" and node.get("mark"):
            module_ids.add(node["bk_inst_id"])
        elif node["child"]:
            queue.extend(node["child"])

    return module_ids


class HostRequestSerializer(serializers.Serializer):
    """
    主机查询公共参数
    """

    fields = serializers.ListField(label="查询字段", default=Host.Fields, allow_empty=True)

    def to_internal_value(self, data):
        params = super(HostRequestSerializer, self).to_internal_value(data)
        params["fields"] = list(set(list(params["fields"]) + settings.HOST_DYNAMIC_FIELDS))
        return params


class GetHostByTopoNode(CacheResource):
    """
    根据拓扑节点批量查询主机
    """

    class RequestSerializer(HostRequestSerializer):
        class TopoNode(serializers.Serializer):
            bk_obj_id = serializers.CharField(label="模型ID", required=True)
            bk_inst_ids = serializers.ListField(label="实例ID列表", child=serializers.IntegerField(), default=dict)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        topo_nodes = serializers.DictField(label="拓扑节点", child=serializers.ListField(), required=False)

    def perform_request(self, params):
        hosts = get_host_dict_by_biz(params["bk_biz_id"], params["fields"])

        if params.get("topo_nodes", {}):
            # 将查询节点转换为模块ID
            module_ids = _trans_topo_node_to_module_ids(params["bk_biz_id"], params["topo_nodes"])

            # 按模块ID过滤主机
            hosts = [host for host in hosts if set(host["bk_module_ids"]) & module_ids]

        # 获取云区域信息
        clouds = api.cmdb.search_cloud_area()

        for host in hosts:
            _host_full_cloud(host, clouds)
        return [Host(host) for host in hosts]


class GetHostByIP(CacheResource):
    class RequestSerializer(HostRequestSerializer):
        class HostSerializer(serializers.Serializer):
            ip = serializers.CharField()
            bk_cloud_id = serializers.IntegerField(required=False)

        ips = HostSerializer(many=True)
        bk_biz_id = serializers.IntegerField(label="业务ID")
        search_outer_ip = serializers.BooleanField(label="是否搜索外网IP", required=False, default=False)

    @staticmethod
    def process_params(params):
        cloud_dict = defaultdict(list)
        for host in params["ips"]:
            cloud_dict[host.get("bk_cloud_id", -1)].append(host["ip"])

        # 添加主机搜索条件
        conditions = []
        for bk_cloud_id, ips in cloud_dict.items():
            ipv6_ips = []
            ipv4_ips = []
            for ip in ips:
                if is_v6(ip):
                    ipv6_ips.append(ip)
                else:
                    ipv4_ips.append(ip)

            ipv4_condition = {
                "condition": "AND",
                "rules": [{"field": "bk_host_innerip", "operator": "in", "value": ipv4_ips}],
            }
            ipv6_condition = {
                "condition": "AND",
                "rules": [{"field": "bk_host_innerip_v6", "operator": "in", "value": ipv6_ips}],
            }
            if bk_cloud_id != -1:
                ipv4_condition["rules"].append({"field": "bk_cloud_id", "operator": "equal", "value": bk_cloud_id})
                ipv6_condition["rules"].append({"field": "bk_cloud_id", "operator": "equal", "value": bk_cloud_id})

            if params.get("search_outer_ip", False):
                if ipv4_ips:
                    conditions.append(
                        {
                            "condition": "AND",
                            "rules": [{"field": "bk_host_outerip", "operator": "in", "value": ipv4_ips}],
                        }
                    )
                if ipv6_ips:
                    conditions.append(
                        {
                            "condition": "AND",
                            "rules": [{"field": "bk_host_outerip_v6", "operator": "in", "value": ipv6_ips}],
                        }
                    )
            if ipv4_ips:
                conditions.append(ipv4_condition)
            if ipv6_ips:
                conditions.append(ipv6_condition)

        if len(conditions) == 1:
            conditions = conditions[0]
        else:
            conditions = {"condition": "OR", "rules": conditions}

        return {"bk_biz_id": params["bk_biz_id"], "host_property_filter": conditions, "fields": params["fields"]}

    def perform_request(self, params):
        if not params["ips"]:
            return []

        # 获取云区域信息
        clouds = api.cmdb.search_cloud_area()

        # 获取主机信息
        params = self.process_params(params)
        records = batch_request(client.list_biz_hosts_topo, params)

        hosts = []
        for record in records:
            host = _host_from_raw(record, params["bk_biz_id"])
            if host is None:
                continue
            host = _host_full_cloud(host, clouds)
            hosts.append(Host(host))

        return hosts


class GetHostById(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_host_ids = serializers.ListField(child=serializers.IntegerField(), required=True)
        bk_biz_id = serializers.IntegerField(label="业务ID")
        fields = serializers.ListField(label="查询字段", allow_empty=True, default=Host.Fields)

    def perform_request(self, params):
        # 按主机ID查询
        request_params = {
            "bk_biz_id": params["bk_biz_id"],
            "host_property_filter": {
                "condition": "AND",
                "rules": [{"field": "bk_host_id", "operator": "in", "value": params["bk_host_ids"]}],
            },
            "fields": params["fields"],
        }
        records = batch_request(client.list_biz_hosts_topo, request_params)

        # 获取云区域信息
        clouds = api.cmdb.search_cloud_area()

        hosts = []
        for record in records:
            host = _host_from_raw(record, params["bk_biz_id"])
            if host is None:
                continue
            host = _host_full_cloud(host, clouds)
            hosts.append(Host(host))

        return hosts


class GetTopoTreeResource(Resource):
    """
    查询拓扑树接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        return TopoTree(_get_topo_tree(params["bk_biz_id"]))


class GetBusiness(Resource):
    """
    查询业务详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(label="业务ID列表", child=serializers.IntegerField(), required=False, default=[])
        all = serializers.BooleanField(default=False, help_text="return all space list in Business")

        def validate(self, attrs):
            for bk_biz_id in attrs["bk_biz_ids"]:
                if bk_biz_id < 0:
                    attrs["all"] = True
                    break
            return attrs

    def perform_request(self, validated_request_data):
        # 查询全部业务
        response_data = client.search_business()["info"]
        if validated_request_data["all"]:
            # 额外空间列表
            space_list = SpaceApi.list_spaces()
            others = [s.__dict__ for s in space_list if s.bk_biz_id < 0]
            response_data += others
        # 按业务ID过滤出需要的业务信息
        if "bk_biz_ids" in validated_request_data:
            bk_biz_ids = set(validated_request_data["bk_biz_ids"])
            if bk_biz_ids:
                response_data = [topo for topo in response_data if topo["bk_biz_id"] in bk_biz_ids]

        # 查出业务中的用户字段，转换为列表
        member_fields = {
            attr["bk_property_id"]
            for attr in client.search_object_attribute(bk_obj_id="biz")
            if attr["bk_property_type"] == "objuser"
        }

        for item in response_data:
            for field in member_fields:
                item[field] = _split_member_list(item.get(field, ""))

        business_list = [Business(**biz) for biz in self.filter_biz(response_data)]
        return business_list

    @classmethod
    def filter_biz(cls, bk_biz_list):
        # 使用 set in 效率更高
        biz_blacklist = set(map(int, settings.DISABLE_BIZ_ID))
        if not biz_blacklist:
            return bk_biz_list
        return [biz for biz in bk_biz_list if biz["bk_biz_id"] not in biz_blacklist]


class GetModule(Resource):
    """
    查询模块详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_module_ids = serializers.ListField(label="模块ID列表", child=serializers.IntegerField(), required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID")
        service_template_ids = serializers.ListField(label="服务模板ID列表", required=False)

    def perform_request(self, params):
        # 查询业务下所有模块
        response_data = batch_request(client.search_module, {"bk_biz_id": params["bk_biz_id"]})

        # 按服务模版ID过滤
        if "service_template_ids" in params:
            service_template_ids = set(params["service_template_ids"])
            response_data = [topo for topo in response_data if topo.get("service_template_id") in service_template_ids]

        # 按模块ID过滤出需要的模块
        if "bk_module_ids" in params:
            bk_module_ids = set(params["bk_module_ids"])
            response_data = [topo for topo in response_data if topo["bk_module_id"] in bk_module_ids]

        for topo in response_data:
            topo["operator"] = _split_member_list(topo.get("operator", ""))
            topo["bk_bak_operator"] = _split_member_list(topo.get("bk_bak_operator", ""))

        return [Module(**topo) for topo in response_data]


class GetSet(Resource):
    """
    查询集群详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_set_ids = serializers.ListField(label="集群ID列表", child=serializers.IntegerField(), required=False)
        set_template_ids = serializers.ListField(label="集群模板ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        response_data = batch_request(client.search_set, {"bk_biz_id": params["bk_biz_id"]})

        # 按集群模块ID过滤
        if "set_template_ids" in params:
            set_template_ids = set(params["set_template_ids"])
            response_data = [topo for topo in response_data if topo["set_template_id"] in set_template_ids]

        # 按集群ID过滤
        if "bk_set_ids" in params:
            bk_set_ids = set(params["bk_set_ids"])
            response_data = [topo for topo in response_data if topo["bk_set_id"] in bk_set_ids]

        return [Set(**topo) for topo in response_data]


class GetServiceInstanceByTopoNode(Resource):
    """
    根据拓扑节点获取服务实例
    """

    class RequestSerializer(serializers.Serializer):
        class TopoNode(serializers.Serializer):
            bk_obj_id = serializers.CharField(label="模型ID", required=True)
            bk_inst_ids = serializers.ListField(label="实例ID列表", child=serializers.IntegerField(), default=dict)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        topo_nodes = serializers.DictField(label="拓扑节点", child=serializers.ListField(), required=False)

    def perform_request(self, params):
        service_instances = get_service_instance_by_biz(params["bk_biz_id"])

        if params.get("topo_nodes", {}):
            # 将查询节点转换为模块ID
            module_ids = _trans_topo_node_to_module_ids(params["bk_biz_id"], params["topo_nodes"])
            service_instances = [instance for instance in service_instances if instance["bk_module_id"] in module_ids]

        for instance in service_instances:
            instance["service_instance_id"] = instance["id"]
        return [ServiceInstance(**instance) for instance in service_instances]


class GetServiceInstanceByID(Resource):
    """
    根据服务实例ID获取服务实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        service_instance_ids = serializers.ListField(label="服务实例列表", child=serializers.IntegerField())

    def perform_request(self, validated_request_data):
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "with_name": True,
            "service_instance_ids": validated_request_data["service_instance_ids"],
        }
        service_instances = batch_request(client.list_service_instance_detail, params, limit=500)
        for instance in service_instances:
            instance["service_instance_id"] = instance["id"]
        return [ServiceInstance(**instance) for instance in service_instances]


class GetProcess(Resource):
    """
    根据服务实例ID获取服务实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        bk_host_id = serializers.IntegerField(label="主机ID", required=False, allow_null=True)
        include_multiple_bind_info = serializers.BooleanField(required=False, label="是否返回多个绑定信息", default=False)

    def perform_request(self, validated_request_data):
        include_multiple_bind_info = validated_request_data["include_multiple_bind_info"]
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
        }
        if validated_request_data.get("bk_host_id"):
            params["bk_host_id"] = validated_request_data["bk_host_id"]
            response_data = batch_request(client.list_service_instance_detail, params, limit=500)
        else:
            response_data = get_service_instance_by_biz(validated_request_data["bk_biz_id"])

        processes = []
        for service_instances in response_data:
            process_instances = service_instances["process_instances"] or []
            for process_instance in process_instances:
                process_params = {}
                # process info
                process_params.update(process_instance["process"])
                process_params.update(process_instance["relation"])

                bind_info = process_params.get("bind_info", [])
                if not process_params.get("bind_info"):
                    processes.append(Process(**process_params))
                else:
                    # 支持一个进程绑定多个服务
                    for bind_info_item in bind_info:
                        process_params_copy = copy.deepcopy(process_params)
                        process_params_copy.update(
                            {
                                "bind_ip": bind_info_item.get("ip", ""),
                                "port": bind_info_item.get("port", ""),
                                "bk_enable_port": bind_info_item.get("enable", True),
                                "protocol": bind_info_item.get("protocol", ""),
                            }
                        )
                        if not process_params_copy.get("bk_enable_port", True):
                            # 进程监控开关存在且状态为关闭，则不在监控平台展示和监控端口
                            process_params_copy["port"] = ""

                        processes.append(Process(**process_params_copy))
                        if not include_multiple_bind_info:
                            break
        return processes


class GetObjectAttribute(Resource):
    """
    查询对象属性
    """

    class RequestSerializer(serializers.Serializer):
        bk_obj_id = serializers.CharField(label="模型ID")

    def perform_request(self, validated_request_data):
        params = {"bk_obj_id": validated_request_data["bk_obj_id"]}
        return client.search_object_attribute(params)


class GetBluekingBiz(Resource):
    """
    查询对象属性
    """

    def perform_request(self, validated_request_data):
        try:
            bk_biz_name = getattr(settings, "BLUEKING_NAME", "蓝鲸") or "蓝鲸"
            result = client.search_business(
                dict(
                    fields=["bk_biz_id", "bk_biz_name"],
                    condition={"bk_biz_name": bk_biz_name},
                )  # noqa
            )
        except BKAPIError as e:
            logger.info("GetBluekingBiz failed: {}", e.message)
            return 2

        if result["info"]:
            for biz_info in result["info"]:
                if biz_info["bk_biz_name"] == bk_biz_name:
                    return biz_info["bk_biz_id"]

        return 2


class SearchServiceCategory(Resource):
    """
    查询服务分类列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        return client.list_service_category(**validated_request_data)["info"]


class SearchCloudArea(CacheResource):
    """
    查询云区域信息
    """

    cache_type = CacheType.CC_CACHE_ALWAYS

    def perform_request(self, params):
        return batch_request(client.search_cloud_area, params, limit=200)


class GetDynamicQuery(CacheResource):
    r"""
    查询业务下 服务模板\集群模板 列表
    """

    cache_type = CacheType.CC_BACKEND

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dynamic_type = serializers.ChoiceField(
            choices=[TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE], label="动态类型", required=True
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        dynamic_type = validated_request_data["dynamic_type"]

        # 获取动态查询的列表
        params = dict(bk_biz_id=bk_biz_id)
        response_data = []
        if dynamic_type == TargetNodeType.SERVICE_TEMPLATE:
            response_data = batch_request(client.list_service_template, params, limit=200)
        elif dynamic_type == TargetNodeType.SET_TEMPLATE:
            response_data = batch_request(client.list_set_template, params, limit=200)

        # 获取业务名称
        response_biz_data = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
        if response_biz_data:
            biz_data = response_biz_data[0]
            bk_inst_name = biz_data.bk_biz_name
        else:
            bk_inst_name = _("未知")

        # 结果保存变量
        result = {"bk_biz_id": bk_biz_id, "bk_biz_name": bk_inst_name, "children": []}

        # 获取id和名称
        for dynamic_query in response_data:
            result["children"].append(dict(id=dynamic_query["id"], name=dynamic_query["name"]))

        return result


class GetHostByTemplate(Resource):
    """
    获取模板下的主机
    """

    class RequestSerializer(HostRequestSerializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        bk_obj_id = serializers.ChoiceField(
            required=True, choices=[TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE], label="查询对象"
        )
        template_ids = serializers.ListField(label="模板ID", required=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bk_obj_id = params["bk_obj_id"]
        template_ids = params["template_ids"]

        # 按模板查询节点
        if bk_obj_id == TargetNodeType.SERVICE_TEMPLATE:
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, service_template_ids=template_ids)
            topo_nodes = {"module": [m.bk_module_id for m in modules]}
        elif bk_obj_id == TargetNodeType.SET_TEMPLATE:
            sets = api.cmdb.get_set(bk_biz_id=bk_biz_id, set_template_ids=template_ids)
            topo_nodes = {"set": [s.bk_set_id for s in sets]}
        else:
            topo_nodes = []

        return api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id, topo_nodes=topo_nodes, fields=params["fields"])


class GetServiceInstanceByTemplate(Resource):
    """
    获取模板下的服务实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        bk_obj_id = serializers.ChoiceField(
            required=True, choices=[TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE], label="查询对象"
        )
        template_ids = serializers.ListField(label="模板ID", required=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bk_obj_id = params["bk_obj_id"]
        template_ids = params["template_ids"]

        # 按模板查询节点
        if bk_obj_id == TargetNodeType.SERVICE_TEMPLATE:
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, service_template_ids=template_ids)
            topo_nodes = {"module": [m.bk_module_id for m in modules]}
        elif bk_obj_id == TargetNodeType.SET_TEMPLATE:
            sets = api.cmdb.get_set(bk_biz_id=bk_biz_id, set_template_ids=template_ids)
            topo_nodes = {"set": [s.bk_set_id for s in sets]}
        else:
            topo_nodes = []

        return api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id, topo_nodes=topo_nodes)


class GetMainlineObjectTopo(Resource):
    """
    获取主线模型的业务拓扑
    """

    def perform_request(self, params):
        return client.get_mainline_object_topo()


class FindHostByServiceTemplate(Resource):
    """
    获取服务模板下的主机
    """

    def perform_request(self, validated_request_data):
        return client.find_host_by_service_template(**validated_request_data)


def raw_hosts(cc_biz_id):
    """Do not use me，Please use `hosts` func"""

    hosts = get_host_dict_by_biz(cc_biz_id, Host.Fields)
    # 获取云区域信息
    clouds = api.cmdb.search_cloud_area()
    for host in hosts:
        _host_full_cloud(host, clouds)

    full_host_topo_inst(cc_biz_id, hosts)
    return hosts


# 获取主机所有拓扑信息
# to be legacy
def full_host_topo_inst(bk_biz_id, host_list):
    topo_tree_dict = to_dict(api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id))
    if not topo_tree_dict:
        return

    queue = [copy.deepcopy(topo_tree_dict)]
    inst_obj_dict = {}
    topo_link_dict = {}

    while queue:
        node = queue.pop()
        inst_obj_dict["{}|{}".format(node["bk_obj_id"], node["bk_inst_id"])] = node
        if not node.get("topo_link"):
            node["topo_link"] = ["{}|{}".format(node["bk_obj_id"], node["bk_inst_id"])]
            node["topo_link_display"] = [node["bk_inst_name"]]
        topo_link_dict["{}|{}".format(node["bk_obj_id"], node["bk_inst_id"])] = node["topo_link"]
        for child in node["child"]:
            child["topo_link"] = node["topo_link"] + ["{}|{}".format(child["bk_obj_id"], child["bk_inst_id"])]
            child["topo_link_display"] = node["topo_link_display"] + [child["bk_inst_name"]]

        queue = queue + node["child"]
        del node["child"]

    for host in host_list:
        module_list = ["module|%s" % x for x in host["bk_module_ids"]]
        topo_dict = {"module": [], "set": []}
        for module_key in module_list:
            for inst_key in topo_link_dict.get(module_key, []):
                bk_obj_id, _ = inst_key.split("|")
                if bk_obj_id not in topo_dict:
                    topo_dict[bk_obj_id] = []
                if inst_key not in ["{}|{}".format(x["bk_obj_id"], x["bk_inst_id"]) for x in topo_dict[bk_obj_id]]:
                    topo_dict[bk_obj_id].append(inst_obj_dict[inst_key])
        for bk_obj_id in topo_dict:
            host[bk_obj_id] = topo_dict[bk_obj_id]


class GetHostWithoutBiz(Resource):
    class RequestSerializer(HostRequestSerializer):
        ips = serializers.ListField(label="IP组", required=False)
        bk_host_ids = serializers.ListField(label="主机ID组", required=False)
        ip = serializers.CharField(label="IP关键字", required=False)
        bk_cloud_ids = serializers.ListField(label="云区域ID组", required=False)
        limit = serializers.IntegerField(label="每页限制条数", max_value=500, default=500)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)

    @classmethod
    def convert_host(cls, host: Dict[str, Any], **kwargs):
        return Host(host, **kwargs)

    def perform_request(self, params):
        # 如果查询条件存在但是为空，直接返回空数据
        if params.get("ips") == [] or params.get("bk_host_ids") == [] or params.get("ip") == "":
            return {"count": 0, "hosts": []}

        request_params = {
            "page": {"start": 0, "limit": params["limit"]},
            "fields": params["fields"],
        }
        filter_rules = []
        if params.get("ip"):
            if is_v6(params["ip"]):
                params["ip"] = exploded_ip(params["ip"])
                filter_rules.append({"field": "bk_host_innerip_v6", "operator": "contains", "value": params["ip"]})
            else:
                filter_rules.append({"field": "bk_host_innerip", "operator": "contains", "value": params["ip"]})
        if params.get("ips"):
            ipv4_list = []
            ipv6_list = []
            for ip in params["ips"]:
                if is_v6(ip):
                    ipv6_list.append(exploded_ip(ip))
                else:
                    ipv4_list.append(ip)
            if ipv4_list:
                filter_rules.append({"field": "bk_host_innerip", "operator": "in", "value": ipv4_list})
            if ipv6_list:
                filter_rules.append({"field": "bk_host_innerip_v6", "operator": "in", "value": ipv6_list})
        if params.get("bk_host_ids"):
            if params["bk_host_ids"]:
                filter_rules.append({"field": "bk_host_id", "operator": "in", "value": params["bk_host_ids"]})
            else:
                return {"count": 0, "hosts": []}

        if params.get("bk_cloud_ids"):
            filter_rules.append({"field": "bk_cloud_id", "operator": "in", "value": params["bk_cloud_ids"]})

        if filter_rules:
            request_params["host_property_filter"] = {"condition": "AND", "rules": filter_rules}

        if params.get("bk_biz_id"):
            request_params["bk_biz_id"] = params["bk_biz_id"]
            search_result = client.list_biz_hosts_topo(request_params)
            hosts = [
                self.convert_host(host["host"], bk_biz_id=request_params["bk_biz_id"], topo=host["topo"])
                for host in search_result["info"]
            ]
        else:
            search_result = client.list_hosts_without_biz(request_params)
            if search_result["info"]:
                relations = client.find_host_biz_relation(
                    bk_host_id=[host["bk_host_id"] for host in search_result["info"]]
                )
            else:
                relations = []
            biz_mapping = {r["bk_host_id"]: r["bk_biz_id"] for r in relations}
            hosts = []
            for host in search_result["info"]:
                if host["bk_host_id"] in biz_mapping:
                    host["bk_biz_id"] = biz_mapping[host["bk_host_id"]]
                    hosts.append(self.convert_host(host))

        return {
            "count": search_result["count"],
            "hosts": hosts,
        }


class GetHostWithoutBizV2(CacheResource, GetHostWithoutBiz):
    cache_type = CacheType.CC_BACKEND(timeout=60)

    @classmethod
    def convert_host(cls, host: Dict[str, Any], **kwargs):
        host.update(kwargs)
        return host

    def perform_request(self, params):
        host_page = super().perform_request(params)
        if not host_page["hosts"]:
            return host_page

        clouds = api.cmdb.search_cloud_area()
        for host in host_page["hosts"]:
            _host_full_cloud(host, clouds)
        return host_page


class SearchObjectAttribute(Resource):
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    bk_obj_id = serializers.CharField(label="模型ID", required=True)
    include_custom_attr = serializers.BooleanField(label="是否包含业务自定义属性", default=False)

    HostFields = set(list(Host.Fields) + settings.HOST_DYNAMIC_FIELDS)

    def perform_request(self, params):
        include_custom_attr = params.pop("include_custom_attr", False)
        attrs = client.search_object_attribute(params)
        response_attrs = []
        for attr in attrs:
            if attr["bk_biz_id"] != 0 and not include_custom_attr:
                # 是否包含业务自定义属性，不包含的忽略
                continue
            if params["bk_obj_id"] == "host" and attr["bk_property_id"] not in self.HostFields:
                # 主机属性缓存仅缓存了一部分，不存在的暂时先不支持
                continue
            response_attrs.append(attr)
        return response_attrs
