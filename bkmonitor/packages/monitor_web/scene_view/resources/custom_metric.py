"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from collections import defaultdict
from typing import Dict, List

from django.db import models
from rest_framework import serializers

from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api
from monitor_web.models import CustomTSField, CustomTSTable

logger = logging.getLogger("monitor_web")


class GetCustomTsMetricGroups(Resource):
    """
    获取自定义时序指标分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        time_series_group_id = serializers.IntegerField(label="自定义指标ID")

    def perform_request(self, params: Dict) -> List[Dict]:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True), pk=params["time_series_group_id"]
        )

        fields = table.get_and_sync_fields()
        metrics = [field for field in fields if field.type == CustomTSField.MetricType.METRIC]

        # 维度描述
        dimension_descriptions = {}
        # 公共维度
        common_dimensions = []
        for field in fields:
            if field.type == CustomTSField.MetricType.DIMENSION:
                dimension_descriptions[field.name] = field.description
                if field.config.get("common", False):
                    common_dimensions.append(
                        {
                            "name": field.name,
                            "alias": field.description,
                        }
                    )

        # 指标分组
        metric_groups = defaultdict(list)
        for metric in metrics:
            for group in metric.config.get("label", []):
                metric_groups[group].append(
                    {
                        "metric_name": metric.name,
                        "alias": metric.description,
                        "dimensions": [
                            {"name": dimension, "alias": dimension_descriptions.get(dimension, dimension)}
                            for dimension in metric.config.get("dimensions", [])
                        ],
                    }
                )

        return {
            "common_dimensions": common_dimensions,
            "metric_groups": [{"name": group, "metrics": metric_groups[group]} for group in metric_groups],
        }


class GetCustomTsDimensionValues(Resource):
    """
    获取自定义时序维度值
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        time_series_group_id = serializers.IntegerField(label="自定义指标ID")
        dimension = serializers.CharField(label="维度")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        metrics = serializers.ListField(label="指标", child=serializers.CharField(), allow_empty=False)

    def perform_request(self, params: Dict) -> List[Dict]:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True), pk=params["time_series_group_id"]
        )
        match = f'{{__name__=~"bkmonitor:{table.table_id.replace(".", ":")}:({"|".join(params["metrics"])})"}}'

        params = {
            "match": [match],
            "label": params["dimension"],
            "bk_biz_ids": [params["bk_biz_id"]],
            "start_time": params["start_time"],
            "end_time": params["end_time"],
        }
        logger.info(params)
        result = api.unify_query.get_promql_label_values(params)
        values = result.get("values", {}).get(params["dimension"], [])
        return [{"name": value, "alias": value} for value in values]


class GetCustomTsGraphConfig(Resource):
    """
    获取自定义时序图表配置
    """

    class RequestSerializer(serializers.Serializer):
        class CompareSerializer(serializers.Serializer):
            type = serializers.ChoiceField(choices=["time", "metric"], label="对比模式", required=False)
            offsets = serializers.ListField(label="时间对比偏移量", default=list)

        class LimitSerializer(serializers.Serializer):
            function = serializers.ChoiceField(choices=["top", "bottom"], label="限制函数", default="")
            limit = serializers.IntegerField(label="限制数量", default=0)

        class GroupBySerializer(serializers.Serializer):
            field = serializers.CharField(label="聚合维度")
            split = serializers.BooleanField(label="是否拆分", default=False)

        class ConditionSerializer(serializers.Serializer):
            key = serializers.CharField(label="指标")
            method = serializers.ChoiceField(choices=["eq", "neq", "gt", "gte", "lt", "lte"], label="方法")
            value = serializers.ListField(label="值")
            condition = serializers.ChoiceField(choices=["and", "or"], label="条件", default="and")

        bk_biz_id = serializers.IntegerField(label="业务")
        time_series_group_id = serializers.IntegerField(label="自定义时序ID")
        metrics = serializers.ListField(label="查询的指标", allow_empty=False)
        condition = ConditionSerializer(label="过滤条件", many=True, allow_empty=True, default=list)
        group_by = GroupBySerializer(label="聚合维度", many=True, allow_empty=True, default=list)
        filter_dict = serializers.DictField(label="过滤条件", default=dict)
        limit = LimitSerializer(label="限制返回的series数量", allow_null=True, default=None)
        compare = CompareSerializer(label="对比配置", default=None)

    class ResponseSerializer(serializers.Serializer):
        class GroupSerializer(serializers.Serializer):
            name = serializers.CharField(label="分组名称", allow_blank=True)

            class PanelSerializer(serializers.Serializer):
                title = serializers.CharField(label="图表标题")
                sub_title = serializers.CharField(label="子标题", allow_blank=True)

                class TargetSerializer(serializers.Serializer):
                    expression = serializers.CharField(label="表达式")
                    alias = serializers.CharField(label="别名", allow_blank=True)
                    query_configs = serializers.ListField(label="查询配置")

                targets = TargetSerializer(label="目标", many=True)

            panels = PanelSerializer(label="图表配置", many=True)

        groups = GroupSerializer(label="分组", many=True)

    @classmethod
    def create_query_config(
        self,
        table: CustomTSTable,
        metric: CustomTSField,
        group_by: list[dict],
        condition: list[dict],
        filter_dict: dict,
        limit: dict,
    ) -> dict:
        if limit and limit.get("limit", 0) > 0:
            functions = [{"id": "top", "params": [{"id": "n", "value": limit.get("limit", 10)}]}]
        else:
            functions = []

        group_by_fields = {x["field"] for x in group_by}

        query_config = {
            "metrics": [{"field": metric.name, "method": metric.config.get("aggregate_method", "AVG"), "alias": "a"}],
            "interval": "auto",
            "table": table.table_id,
            "data_label": table.data_label,
            "data_source_label": DataSourceLabel.CUSTOM,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            # 只使用指标的维度
            "group_by": list(group_by_fields & set(metric.config.get("dimensions", []))),
            # TODO: 考虑也按指标的维度过滤
            "where": condition,
            "functions": functions,
            # 只使用指标的维度
            "filter_dict": {
                key: value for key, value in filter_dict.items() if key in metric.config.get("dimensions", [])
            },
        }

        return query_config

    @classmethod
    def no_compare(cls, table: CustomTSTable, metrics: List[CustomTSField], params: Dict) -> Dict:
        panels = []
        for metric in metrics:
            panels.append(
                {
                    "title": metric.description or metric.name,
                    "sub_title": f"custom:{table.data_label}:{metric.name}",
                    "targets": [
                        {
                            "function": {},
                            "expression": "a",
                            "alias": "",
                            "query_configs": [
                                cls.create_query_config(
                                    table=table,
                                    metric=metric,
                                    group_by=params.get("group_by", []),
                                    condition=params.get("condition", []),
                                    filter_dict=params.get("filter_dict", {}),
                                    limit=params.get("limit"),
                                )
                            ],
                        }
                    ],
                }
            )

        return [{"name": "", "panels": panels}]

    @classmethod
    def time_compare(cls, groups: List[Dict], params: Dict) -> List[Dict]:
        """
        时间对比
        """
        for group in groups:
            for panel in group.get("panels", []):
                for target in panel.get("targets", []):
                    target["function"]["time_compare"] = [params["compare"]["offsets"]]
        return groups

    @classmethod
    def metric_compare(cls, groups: List[Dict], params: Dict) -> List[Dict]:
        """
        TODO: 指标对比
        """
        # 维度查询

        return groups

    def perform_request(self, params: Dict) -> Dict:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True), pk=params["time_series_group_id"]
        )

        metrics = CustomTSField.objects.filter(
            time_series_group_id=params["time_series_group_id"],
            type=CustomTSField.MetricType.METRIC,
            name__in=params["metrics"],
        )
        # 指标顺序与请求参数一致
        metrics = sorted(list(metrics), key=lambda x: params["metrics"].index(x.name))

        groups = self.no_compare(table, metrics, params)
        if params.get("compare"):
            compare_config = params["compare"]
            if compare_config.get("type") == "time" and compare_config.get("offsets"):
                groups = self.time_compare(groups, params)
            elif compare_config.get("type") == "metric":
                groups = self.metric_compare(groups, params)

        return {"groups": groups}
