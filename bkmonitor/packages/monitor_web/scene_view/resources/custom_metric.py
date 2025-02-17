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
from django.db import models
from rest_framework import serializers

from core.drf_resource import Resource
from monitor_web.models import CustomTSTable


class GetCustomMetricTargetListResource(Resource):
    """
    获取自定义指标目标列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        id = serializers.IntegerField(label="自定义指标分组ID")

    def perform_request(self, params):
        config = CustomTSTable.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True), pk=params["id"]
        )
        targets = set(config.query_target(bk_biz_id=params["bk_biz_id"]))
        return [{"id": target, "name": target} for target in targets]


def GetCustomMetricGraphConfigResource(Resource):
    """
    获取自定义指标图表配置
    """

    class RequestSerializer(serializers.Serializer):
        class CompareSerializer(serializers.Serializer):
            type = serializers.ChoiceField(choices=["time", "metric"], label="对比模式")
            offset = serializers.CharField(label="时间对比偏移量", required=False)

        class LimitSerializer(serializers.Serializer):
            function = serializers.ChoiceField(choices=["top", "bottom"], label="限制函数")
            limit = serializers.IntegerField(label="限制数量")

        class GroupBySerializer(serializers.Serializer):
            field = serializers.CharField(label="聚合维度")
            split = serializers.BooleanField(label="是否拆分")

        class ConditionSerializer(serializers.Serializer):
            key = serializers.CharField(label="指标")
            method = serializers.ChoiceField(choices=["eq", "neq", "gt", "gte", "lt", "lte"], label="方法")
            value = serializers.ListField(label="值")
            condition = serializers.ChoiceField(choices=["and", "or"], label="条件", default="and")

        bk_biz_id = serializers.IntegerField(label="业务")
        time_series_group_id = serializers.IntegerField(label="自定义时序分组ID")
        show_metrics = serializers.ListField(label="展示的指标")
        condition = ConditionSerializer(label="指标过滤条件", many=True)
        group_by = GroupBySerializer(label="聚合维度", many=True)
        limit = LimitSerializer(label="限制返回的series数量")
        compare = CompareSerializer(label="对比配置")

    class ResponseSerializer(serializers.Serializer):
        """
        返回格式
        """

        class TargetSerializer(serializers.Serializer):
            expression = serializers.CharField(label="指标表达式")
            alias = serializers.CharField(label="指标别名", default="")
            query_configs = serializers.ListField(label="查询配置")

        type = serializers.ChoiceField(choices=["row", "time_series"], label="图表类型")
        title = serializers.CharField(label="图表标题")
        panels = serializers.ListField(label="图表配置", required=False)

        subTitle = serializers.CharField(label="子标题", default="")
        targets = TargetSerializer(label="目标", many=True)

    many_response_data = True

    def perform_request(self, params):
        """
        TODO: 生成自定义指标图表配置
        """
        return []


def GetCustomMetricInfoResource(Resource):
    """
    获取自定义指标信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        id = serializers.IntegerField(label="自定义指标分组ID")

    class ResponseSerializer(serializers.Serializer):
        class GroupSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                metric_id = serializers.CharField(label="指标名称")
                metric_name = serializers.CharField(label="指标别名")

            group_id = serializers.IntegerField(label="指标分组ID")
            group_name = serializers.CharField(label="指标分组名称")
            metrics = MetricSerializer(label="指标列表", many=True)

        metric_groups = GroupSerializer(label="指标分组", many=True)
        common_dimensions = serializers.ListField(label="常用维度")

    def perform_request(self, params):
        """
        TODO: 获取自定义指标分组信息
        """
        return {"metric_groups": [], "common_dimensions": []}
