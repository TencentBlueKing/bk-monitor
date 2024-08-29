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
    RelationResourcePath,
    TopoEdgeDataType,
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


class TopoQueryRequestSerializer(TopoBaseRequestSerializer):
    """拓扑视图请求参数"""

    data_type = serializers.ChoiceField(label="数据类型", choices=BarChartDataType.get_choices())
    edge_data_type = serializers.ChoiceField(label="连接线数据类型", choices=TopoEdgeDataType.get_choices())
    export_type = serializers.ChoiceField(label="数据导出类型", choices=GraphViewType.get_choices())


class NodeRelationSerializer(serializers.Serializer):
    """资源拓扑图请求参数"""

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    path = serializers.ChoiceField(label="路径", choices=RelationResourcePath.get_choices())
