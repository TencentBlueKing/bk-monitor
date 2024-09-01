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

from apm_web.topo.handle.bar_query import BarQuery
from apm_web.topo.handle.graph_query import GraphQuery
from apm_web.topo.handle.relation.detail import NodeRelationDetailHandler
from apm_web.topo.handle.relation.entrance import RelationEntrance
from apm_web.topo.serializers import (
    DataTypeBarQueryRequestSerializer,
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
        return BarQuery(**validated_request_data).execute()


class TopoViewResource(Resource):
    """获取节点拓扑图"""

    RequestSerializer = TopoQueryRequestSerializer

    def perform_request(self, validated_request_data):
        export_type = validated_request_data.pop("export_type")
        edge_data_type = validated_request_data.pop("edge_data_type")
        return GraphQuery(**validated_request_data).execute(export_type, edge_data_type)


class NodeRelationResource(Resource):
    """节点资源拓扑信息"""

    RequestSerializer = NodeRelationSerializer

    def perform_request(self, validated_request_data):
        entrance = RelationEntrance(
            validated_request_data.pop("path_type"), validated_request_data.pop("paths", None), **validated_request_data
        )
        return entrance.export(entrance.relation_tree, export_type="layer")


class NodeRelationDetailResource(Resource):
    """单个节点资源详情信息"""

    RequestSerializer = NodeRelationDetailSerializer

    def perform_request(self, validated_request_data):
        return NodeRelationDetailHandler.get_detail(**validated_request_data)
