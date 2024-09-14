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

from rest_framework import serializers

from apm_web.models import Application
from apm_web.topo.constants import (
    BarChartDataType,
    GraphViewType,
    RelationResourcePathType,
    SourceType,
    TopoEdgeDataType,
    TopoLinkType,
)


class TopoBaseRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    service_name = serializers.CharField(label="服务名称", required=False)

    def validate(self, attrs):
        app = Application.objects.filter(bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]).first()
        if not app:
            raise ValueError(f"应用: ({attrs['bk_biz_id']}){attrs['app_name']} 不存在")
        return attrs


class DataTypeBarQueryRequestSerializer(TopoBaseRequestSerializer):
    """拓扑柱状图请求参数"""

    data_type = serializers.ChoiceField(label="数据类型", choices=BarChartDataType.get_choices())
    # 告警事件参数: 策略 Id
    alert_strategy_id = serializers.IntegerField(label="策略 ID (告警模式下)", required=False)

    # endpoint_name 条件只支持获取 告警 / Apdex
    endpoint_name = serializers.CharField(label="接口名称", required=False)


class TopoQueryRequestSerializer(TopoBaseRequestSerializer):
    """拓扑视图请求参数"""

    data_type = serializers.ChoiceField(label="数据类型", choices=BarChartDataType.get_choices(), required=False)
    edge_data_type = serializers.ChoiceField(label="连接线数据类型", choices=TopoEdgeDataType.get_choices())
    export_type = serializers.ChoiceField(label="数据导出类型", choices=GraphViewType.get_choices())
    metric_start_time = serializers.IntegerField(label="数据开始时间")
    metric_end_time = serializers.IntegerField(label="数据结束时间")


class NodeRelationSerializer(serializers.Serializer):
    """资源拓扑图请求参数"""

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    path_type = serializers.ChoiceField(label="请求路径类型", choices=RelationResourcePathType.get_choices())
    paths = serializers.CharField(label="资源关联路径", required=False)

    @property
    def validated_data(self):
        res = super(NodeRelationSerializer, self).validated_data
        if res["path_type"] == RelationResourcePathType.SPECIFIC.value:
            if not res.get("paths"):
                raise ValueError(f"没有传递 path 参数")
            res["paths"] = res["paths"].split(",")
        return res


class NodeEndpointTopSerializer(serializers.Serializer):
    """服务接口 Top 列表请求参数"""

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    node_name = serializers.CharField(label="服务名称")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    data_type = serializers.ChoiceField(label="数据类型", choices=BarChartDataType.get_choices())
    size = serializers.IntegerField(label="查询数量", default=5, required=False)

    @property
    def validated_data(self):
        res = super(NodeEndpointTopSerializer, self).validated_data
        # 兼容前端参数名称 node_name == service_name
        res["service_name"] = res.pop("node_name")

        return res


class NodeRelationDetailSerializer(serializers.Serializer):
    """节点资源详情请求参数"""

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    source_type = serializers.ChoiceField(label="资源类型", choices=SourceType.get_choices())
    source_info = serializers.DictField(label="资源信息")


class EndpointNameSerializer(TopoBaseRequestSerializer):
    link_type = serializers.ChoiceField(label="需要获取的链接类型", choices=TopoLinkType.get_choices())
    # endpoint_name 链接: alert
    endpoint_name = serializers.CharField(label="接口名称", required=False)

    # 资源拓扑图的链接获取
    source_type = serializers.ChoiceField(label="资源类型", choices=SourceType.get_choices(), required=False)
    source_info = serializers.DictField(label="资源信息", required=False)

    def validate(self, attrs):
        res = super(EndpointNameSerializer, self).validate(attrs)
        if attrs["link_type"] == TopoLinkType.ALERT.value:
            if attrs.get("endpoint_name") and not attrs.get("service_name"):
                raise ValueError(f"[获取链接]获取告警中心链接需要 endpoint_name 参数")

        elif attrs["link_type"] == TopoLinkType.TOPO_SOURCE.value:
            if not attrs.get("source_type") or not attrs.get("source_info"):
                raise ValueError(f"[获取链接]获取资源拓扑链接需要 source_type / source_info 参数")

        return res


class GraphDiffSerializer(serializers.Serializer):

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称", required=False)
    base_time = serializers.IntegerField(label="参照时间")
    diff_time = serializers.IntegerField(label="对比时间")
    option_kind = serializers.CharField(label="选项主调/被调")
