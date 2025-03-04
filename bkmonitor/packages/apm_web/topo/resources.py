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
import datetime

from apm_web.topo.constants import GraphViewType, SourceType, TopoLinkType
from apm_web.topo.handle.bar_query import BarQuery, LinkHelper
from apm_web.topo.handle.graph_query import GraphQuery
from apm_web.topo.handle.relation.define import SourceSystem
from apm_web.topo.handle.relation.detail import NodeRelationDetailHandler
from apm_web.topo.handle.relation.entrance import EndpointListEntrance, RelationEntrance
from apm_web.topo.serializers import (
    DataTypeBarQueryRequestSerializer,
    EndpointNameSerializer,
    GraphDiffSerializer,
    NodeEndpointTopSerializer,
    NodeRelationDetailSerializer,
    NodeRelationSerializer,
    TopoQueryRequestSerializer,
)
from apm_web.utils import fill_series, get_bar_interval_number
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
        response = BarQuery(
            endpoint_name=validated_request_data.pop("endpoint_name", None),
            **validated_request_data,
        ).execute()

        return {
            "metrics": response.get("metrics"),
            "series": fill_series(
                response.get("series", []),
                validated_request_data["start_time"],
                validated_request_data["end_time"],
                interval=get_bar_interval_number(
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                ),
            ),
        }


class TopoViewResource(Resource):
    """[拓扑图]获取节点拓扑图"""

    RequestSerializer = TopoQueryRequestSerializer

    def perform_request(self, validated_data):
        params = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "service_name": validated_data.get("service_name"),
            "data_type": validated_data.get("data_type"),
        }

        # 时间范围 与 数据时间
        start_time = validated_data["start_time"]
        end_time = validated_data["end_time"]
        metric_start_time = validated_data["metric_start_time"]
        metric_end_time = validated_data["metric_end_time"]

        # graph 转换器
        converter = GraphQuery.create_converter(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            validated_data["export_type"],
            service_name=validated_data.get("service_name"),
            runtime={"start_time": start_time, "end_time": end_time},
        )

        graph = GraphQuery(**{**params, "start_time": start_time, "end_time": end_time}).execute(
            edge_data_type=validated_data["edge_data_type"],
            converter=converter,
        )
        if (metric_start_time == start_time) and (metric_end_time == end_time):
            # 数据时间和拓扑图时间一致 直接返回
            return graph >> converter

        # 数据时间和拓扑图时间不一致 需要基于拓扑图时间的 graph 进行对比合并
        other_graph = GraphQuery(**{**params, "start_time": metric_start_time, "end_time": metric_end_time}).execute(
            edge_data_type=validated_data["edge_data_type"],
            converter=converter,
        )

        return (graph | other_graph) >> converter


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
            if validated_request_data.get("endpoint_name"):
                return LinkHelper.get_endpoint_alert_link(
                    **params,
                    service_name=validated_request_data["service_name"],
                    endpoint_name=validated_request_data["endpoint_name"],
                )
            else:
                return LinkHelper.get_service_alert_link(**params, service_name=validated_request_data["service_name"])

        elif validated_request_data["link_type"] == TopoLinkType.TOPO_SOURCE.value:
            # 根据资源类型获取不同的跳转链接
            source_type = validated_request_data["source_type"]
            if source_type == SourceType.SERVICE.value:
                return LinkHelper.get_service_monitor_link(
                    validated_request_data["source_info"]["bcs_cluster_id"],
                    validated_request_data["source_info"]["namespace"],
                    validated_request_data["source_info"]["service"],
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                )
            elif source_type == SourceType.POD.value:
                return LinkHelper.get_pod_monitor_link(
                    validated_request_data["source_info"]["bcs_cluster_id"],
                    validated_request_data["source_info"]["namespace"],
                    validated_request_data["source_info"]["pod"],
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                )
            elif source_type == SourceType.SYSTEM.value:
                bk_host_id = SourceSystem.get_bk_host_id(
                    validated_request_data["bk_biz_id"],
                    validated_request_data["source_info"]["bk_target_ip"],
                )
                return LinkHelper.get_host_monitor_link(
                    bk_host_id,
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                )
            elif source_type == SourceType.APM_SERVICE_INSTANCE.value:
                return LinkHelper.get_service_instance_instance_tab_link(
                    validated_request_data["bk_biz_id"],
                    validated_request_data["app_name"],
                    validated_request_data["source_info"]["apm_service_name"],
                    validated_request_data["source_info"]["apm_service_instance_name"],
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                )
            elif source_type == SourceType.APM_SERVICE.value:
                return LinkHelper.get_service_overview_tab_link(
                    validated_request_data["bk_biz_id"],
                    validated_request_data["app_name"],
                    validated_request_data["source_info"]["apm_service_name"],
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                )

        raise ValueError(f"不支持获取: {validated_request_data['source_type']}类型的链接")


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


class GraphDiffResource(Resource):
    """[拓扑图]拓扑图对比"""

    RequestSerializer = GraphDiffSerializer

    def perform_request(self, validated_data):
        base_time = validated_data.pop("base_time")
        diff_time = validated_data.pop("diff_time")

        converter = GraphQuery.create_converter(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            export_type=GraphViewType.TOPO_DIFF.value,
            service_name=validated_data.get("service_name"),
            runtime={"option_kind": validated_data["option_kind"]},
        )

        base_graph_query = GraphQuery(
            **{
                **validated_data,
                **self.enlarge_time(base_time),
            }
        )
        base_graph = base_graph_query.create_graph(
            extra_plugins=converter.extra_pre_plugins(base_graph_query.common_params())
        )

        diff_graph_query = GraphQuery(
            **{
                **validated_data,
                **self.enlarge_time(diff_time),
            }
        )
        diff_graph = diff_graph_query.create_graph(
            extra_plugins=converter.extra_pre_plugins(diff_graph_query.common_params())
        )

        return (base_graph & diff_graph) >> converter

    def enlarge_time(self, timestamp):
        """将时间戳转为时间范围 (间隔一分钟)"""
        start = datetime.datetime.fromtimestamp(timestamp)
        end = start + datetime.timedelta(minutes=1)

        return {"start_time": int(start.timestamp()), "end_time": int(end.timestamp())}
