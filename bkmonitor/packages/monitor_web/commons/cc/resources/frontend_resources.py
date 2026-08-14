# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.commons.tools import get_host_view_display_fields
from bkmonitor.share.api_auth_resource import ApiAuthResource
from core.drf_resource import Resource, api, resource
from core.errors.share import InvalidParamsError
from monitor_web.commons.cc.utils import foreach_topo_tree


class GetTopoTree(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        instance_type = serializers.ChoiceField(required=False, choices=["host", "service"], label="实例类型")
        remove_empty_nodes = serializers.BooleanField(required=False, default=False, label="是否删除空节点")
        bk_host_id = serializers.IntegerField(required=False, label="分享主机ID")
        bk_obj_id = serializers.CharField(required=False, label="分享拓扑对象ID")
        bk_inst_id = serializers.IntegerField(required=False, label="分享拓扑实例ID")

        def validate(self, attrs):
            if bool(attrs.get("bk_obj_id")) != (attrs.get("bk_inst_id") is not None):
                raise InvalidParamsError({"key": "bk_obj_id,bk_inst_id"})
            return attrs

    @classmethod
    def filter_scope_node(cls, node, params):
        if params.get("bk_host_id") is not None and str(node.get("bk_host_id")) == str(params["bk_host_id"]):
            return copy.deepcopy(node)
        if (
            params.get("bk_obj_id")
            and params.get("bk_inst_id") is not None
            and str(node.get("bk_obj_id")) == str(params["bk_obj_id"])
            and str(node.get("bk_inst_id")) == str(params["bk_inst_id"])
        ):
            return copy.deepcopy(node)

        children = []
        for child in node.get("child", []):
            scoped_child = cls.filter_scope_node(child, params)
            if scoped_child:
                children.append(scoped_child)
        if not children:
            return None

        scoped_node = copy.copy(node)
        scoped_node["child"] = children
        return scoped_node

    @staticmethod
    def handle_node(node, node_link, other_param):
        if node.get("child", None) is not None:
            node["children"] = node.pop("child")

        node["bk_biz_id"] = other_param["bk_biz_id"]
        other_param["index"] += 1
        node["id"] = str(other_param["index"])
        field, alias_field = get_host_view_display_fields(other_param["bk_biz_id"])

        if node.get("bk_host_id"):
            node["name"] = node.get(field, "display_name")
            node["alias_name"] = node.get(alias_field, "")
            node["id"] = str(node["bk_host_id"])
        elif node.get("bk_inst_name"):
            node["name"] = node["bk_inst_name"]
            node["id"] = f"{node['bk_obj_id']}|{node['bk_inst_id']}"
        elif node.get("service_instance_id"):
            node["id"] = node["service_instance_id"]
        else:
            node["name"] = _("无法识别节点")

    @staticmethod
    def remove_empty_nodes(node, node_link, ignore_obj):
        # 忽视处理的节点类型。主机数：忽略主机和模块，实例数：忽略实例和主机
        if not node.get("bk_obj_id") or node["bk_obj_id"] in ignore_obj:
            return True

        # 对其他节点，看它的子节点的child为空，如果为空，则从树里面移除
        childs = node.get("child", [])
        new_child = []
        for child in childs:
            if child.get("child"):
                new_child.append(child)

        node["child"] = new_child

    @staticmethod
    def get_node_mapping(topo_tree):
        # 获得节点的路径映射
        node_mapping = {}

        def mapping(node, node_link, node_mapping):
            node.update(node_link=node_link)
            node_mapping[node_link[-1]] = node

        foreach_topo_tree(topo_tree, mapping, node_mapping=node_mapping)
        return node_mapping

    def perform_request(self, validated_request_data):
        topo_tree = resource.commons.cc_topo_tree(validated_request_data)

        if validated_request_data.get("bk_host_id") is not None or validated_request_data.get("bk_obj_id"):
            topo_tree = self.filter_scope_node(topo_tree, validated_request_data)
            if not topo_tree:
                return []

        # 如果传了remove_empty_nodes参数，则过滤掉空节点
        if validated_request_data.get("remove_empty_nodes"):
            foreach_topo_tree(topo_tree, self.remove_empty_nodes, order="desc", ignore_obj=["module"])

        other_param = {"bk_biz_id": validated_request_data["bk_biz_id"], "index": 0}
        foreach_topo_tree(topo_tree, self.handle_node, order="desc", other_param=other_param)

        return [topo_tree]


class HostAgentStatusResource(Resource):
    """
    主机Agent状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        biz_id = validated_request_data["bk_biz_id"]

        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=biz_id)
        agent_status = resource.cc.get_agent_status(bk_biz_id=biz_id, hosts=hosts)
        agent_status_dict = {-1: _("未知"), 0: _("Agent正常"), 2: _("Agent未安装"), 3: _("无数据")}

        host_agent_status_list = []
        for host in hosts:
            host_agent_status_list.append(
                {
                    "bk_host_id": host.bk_host_id,
                    "ip": host.bk_host_innerip,
                    "bk_host_innerip": host.bk_host_innerip,
                    "bk_host_innerip_v6": host.bk_host_innerip_v6,
                    "bk_cloud_id": host.bk_cloud_id,
                    "bk_os_type": host.bk_os_type,
                    "bk_os_type_name": host.bk_os_type_name,
                    "bk_os_name": host.bk_os_name,
                    "bk_cloud_name": host.bk_cloud_name,
                    "display_name": host.display_name,
                    "agent_status": agent_status.get(host.bk_host_id, -1),
                    "agent_status_display": agent_status_dict[agent_status.get(host.bk_host_id, -1)],
                }
            )

        return host_agent_status_list
