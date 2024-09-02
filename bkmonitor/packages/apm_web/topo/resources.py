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
from apm_web.topo.constants import TopoLinkType
from apm_web.topo.handle.bar_query import BarQuery, LinkHelper
from apm_web.topo.handle.graph_query import GraphQuery
from apm_web.topo.handle.relation.detail import NodeRelationDetailHandler
from apm_web.topo.handle.relation.entrance import EndpointListEntrance, RelationEntrance
from apm_web.topo.serializers import (
    DataTypeBarQueryRequestSerializer,
    EndpointNameSerializer,
    NodeEndpointTopSerializer,
    NodeRelationDetailSerializer,
    NodeRelationSerializer,
    TopoQueryRequestSerializer,
)
from core.drf_resource import Resource


class DataTypeBarQueryResource(Resource):
    """
    获取不同数据视角下的柱状图
    支持以下数据视角:
    1. 告警事件
    2. Apdex
    3. 主调/被调/总错误率
    """

    RequestSerializer = DataTypeBarQueryRequestSerializer

    def perform_request(self, validated_request_data):
        extra_params = {"endpoint_name": validated_request_data.pop("endpoint_name", None)}
        return BarQuery(**validated_request_data, extra_params=extra_params).execute()


class TopoViewResource(Resource):
    """[拓扑图]获取节点拓扑图"""

    RequestSerializer = TopoQueryRequestSerializer

    def perform_request(self, validated_request_data):
        export_type = validated_request_data.pop("export_type")
        edge_data_type = validated_request_data.pop("edge_data_type")
        return GraphQuery(**validated_request_data).execute(export_type, edge_data_type)


class TopoLinkResource(Resource):
    """[拓扑图]跳转链接获取"""

    RequestSerializer = EndpointNameSerializer

    def perform_request(self, validated_request_data):
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "start_time": validated_request_data["start_time"],
            "end_time": validated_request_data["end_time"],
        }
        if validated_request_data["link_type"] == TopoLinkType.ALERT.value:
            # 获取 服务 or 接口的告警中心跳转链接
            if validated_request_data.get("service_name"):
                if validated_request_data.get("endpoint_name"):
                    return LinkHelper.get_endpoint_alert_link(
                        **params,
                        service_name=validated_request_data["service_name"],
                        endpoint_name=validated_request_data["endpoint_name"],
                    )
                else:
                    return LinkHelper.get_service_alert_link(
                        **params, service_name=validated_request_data["service_name"]
                    )

            raise ValueError(f"[获取链接]缺少链接类型为: {validated_request_data['link_type']} 的参数")

        raise ValueError(f"不支持获取: {validated_request_data['link_type']}类型的链接")


class NodeEndpointsTopResource(Resource):
    """[拓扑图]服务节点接口列表"""

    RequestSerializer = NodeEndpointTopSerializer

    def perform_request(self, validated_request_data):
        return EndpointListEntrance.list_top(**validated_request_data)


class NodeRelationDetailResource(Resource):
    """[资源拓扑]单个节点资源详情信息"""

    RequestSerializer = NodeRelationDetailSerializer

    def perform_request(self, validated_request_data):
        return NodeRelationDetailHandler.get_detail(**validated_request_data)


class NodeRelationResource(Resource):
    """[资源拓扑]节点资源拓扑信息"""

    RequestSerializer = NodeRelationSerializer

    def perform_request(self, validated_request_data):
        entrance = RelationEntrance(
            validated_request_data.pop("path_type"), validated_request_data.pop("paths", None), **validated_request_data
        )
        return entrance.export(entrance.relation_tree, export_type="layer")
