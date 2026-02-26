"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import defaultdict

from django.db import models
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel, MetricType
from core.drf_resource import Resource, api, resource
from monitor_web.models import CustomTSField, CustomTSTable

logger = logging.getLogger("monitor_web")


class GetCustomMetricTargetListResource(Resource):
    """
    获取自定义指标目标列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")
        id = serializers.IntegerField(label="自定义指标分组ID")

    def perform_request(self, params):
        config = CustomTSTable.objects.get(
            models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True),
            pk=params["id"],
            bk_tenant_id=get_request_tenant_id(),
        )
        targets = set(config.query_target(bk_biz_id=params["bk_biz_id"]))
        return [{"id": target, "name": target} for target in targets]


class GetCustomTsMetricGroups(Resource):
    """
    获取自定义时序指标分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务")

        # 场景：集成 -> 自定义指标
        time_series_group_id = serializers.IntegerField(label="自定义指标ID", required=False)

        # 场景：APM -> 自定义指标
        apm_app_name = serializers.CharField(label="APM 应用名称", required=False, allow_null=True)
        apm_service_name = serializers.CharField(label="APM 服务名称", required=False, allow_null=True)

    def perform_request(self, params: dict) -> dict[str, list]:
        bk_biz_id = params["bk_biz_id"]
        if params.get("apm_app_name"):
            app_name = params.get("apm_app_name")
            service_name = params.get("apm_service_name")
            return self.get_custom_metric_groups_from_apm(bk_biz_id, app_name, service_name)
        else:
            time_series_group_id = params.get("time_series_group_id")
            return self.get_custom_metric_groups_from_global(bk_biz_id, time_series_group_id)

    @classmethod
    def get_custom_metric_groups_from_apm(cls, bk_biz_id: int, app_name: str, service_name: str) -> dict[str, list]:
        from apm_web.models import Application

        app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) not found")
            return {"common_dimensions": [], "metric_groups": []}

        if not app.time_series_group_id:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) metric data source is disabled")
            return {"common_dimensions": [], "metric_groups": []}

        return cls.get_custom_metric_groups_from_global(bk_biz_id, app.time_series_group_id)

    @classmethod
    def get_custom_metric_groups_from_global(cls, bk_biz_id: int, time_series_group_id: int) -> dict[str, list]:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=bk_biz_id) | models.Q(is_platform=True),
            pk=time_series_group_id,
            bk_tenant_id=get_request_tenant_id(),
        )

        fields = table.get_and_sync_fields()
        metrics = [field for field in fields if field.type == MetricType.METRIC]

        # 维度描述
        hidden_dimensions = set()
        dimension_descriptions = {}
        # 公共维度
        common_dimensions = []
        for field in fields:
            # 如果不是维度，则跳过
            if field.type != MetricType.DIMENSION:
                continue

            dimension_descriptions[field.name] = field.description

            # 如果维度隐藏，则不展示
            if field.config.get("hidden", False):
                hidden_dimensions.add(field.name)
                continue

            # 如果维度公共，则添加到公共维度
            if field.config.get("common", False):
                common_dimensions.append({"name": field.name, "alias": field.description})

        # 指标分组
        metric_groups = defaultdict(list)
        for metric in metrics:
            # 如果指标隐藏，则不展示
            if metric.disabled or metric.config.get("hidden", False):
                continue

            labels = metric.config.get("label", [])

            # 如果 label 为空，则使用未分组
            if not labels:
                labels = [_("未分组")]

            # 分组
            for group in labels:
                metric_groups[group].append(
                    {
                        "metric_name": metric.name,
                        "alias": metric.description,
                        "dimensions": [
                            {"name": dimension, "alias": dimension_descriptions.get(dimension, dimension)}
                            for dimension in metric.config.get("dimensions", [])
                            if dimension not in hidden_dimensions
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
        # 场景：集成 -> 自定义指标
        time_series_group_id = serializers.IntegerField(label="自定义指标ID", required=False)

        # 场景：APM -> 自定义指标
        apm_app_name = serializers.CharField(label="APM 应用名称", required=False, allow_null=True)
        apm_service_name = serializers.CharField(label="APM 服务名称", required=False, allow_null=True)

        dimension = serializers.CharField(label="维度")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        metrics = serializers.ListField(label="指标", child=serializers.CharField(), allow_empty=True)

    def perform_request(self, params: dict) -> list[dict]:
        # 如果指标为空，则返回空列表
        if not params["metrics"]:
            return []

        bk_biz_id = params["bk_biz_id"]
        if params.get("apm_app_name"):
            app_name = params.get("apm_app_name")
            service_name = params.get("apm_service_name")
            return self.get_custom_ts_dimension_values_from_apm(
                bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name, params=params
            )
        else:
            time_series_group_id = params.get("time_series_group_id")
            return self.get_custom_ts_dimension_values_from_global(
                bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id, params=params
            )

    @classmethod
    def get_custom_ts_dimension_values_from_apm(
        cls, bk_biz_id: int, app_name: str, service_name: str, params: dict
    ) -> list[dict]:
        from apm_web.models import Application

        app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) not found")
            return []

        if not app.time_series_group_id:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) metric data source is disabled")
            return []

        return cls.get_custom_ts_dimension_values_from_global(bk_biz_id, app.time_series_group_id, params)

    @classmethod
    def get_custom_ts_dimension_values_from_global(
        cls, bk_biz_id: int, time_series_group_id: int, params: dict
    ) -> list[dict]:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=bk_biz_id) | models.Q(is_platform=True),
            pk=time_series_group_id,
            bk_tenant_id=get_request_tenant_id(),
        )

        # 如果指标只有一个，则使用精确匹配
        data_label = table.data_label.split(",")[0]
        if len(params["metrics"]) == 1:
            match = f'{{__name__="bkmonitor:{data_label}:{params["metrics"][0]}"}}'
        else:
            match = f'{{__name__=~"bkmonitor:{data_label}:({"|".join(params["metrics"])})"}}'

        request_params = {
            "match": [match],
            "label": params["dimension"],
            "bk_biz_ids": [params["bk_biz_id"]],
            "start": params["start_time"],
            "end": params["end_time"],
        }
        result = api.unify_query.get_promql_label_values(request_params)
        values = result.get("values", {}).get(params["dimension"], [])
        return [{"name": value, "alias": value} for value in values]


class GetCustomTsGraphConfig(Resource):
    """
    获取自定义时序图表配置
    """

    class RequestSerializer(serializers.Serializer):
        class CompareSerializer(serializers.Serializer):
            type = serializers.ChoiceField(choices=["time", "metric"], label="对比模式", required=False)
            offset = serializers.ListField(label="时间对比偏移量", default=list)

        class LimitSerializer(serializers.Serializer):
            function = serializers.ChoiceField(choices=["top", "bottom"], label="限制函数", default="")
            limit = serializers.IntegerField(label="限制数量", default=0)

        class GroupBySerializer(serializers.Serializer):
            field = serializers.CharField(label="聚合维度")
            split = serializers.BooleanField(label="是否拆分", default=False)

        class ConditionSerializer(serializers.Serializer):
            key = serializers.CharField(label="字段名")
            method = serializers.CharField(label="运算符")
            value = serializers.ListField(label="值")
            condition = serializers.ChoiceField(choices=["and", "or"], label="条件", default="and")

        bk_biz_id = serializers.IntegerField(label="业务")

        # 场景：集成 -> 自定义指标
        time_series_group_id = serializers.IntegerField(label="自定义指标ID", required=False)

        # 场景：APM -> 自定义指标
        apm_app_name = serializers.CharField(label="APM 应用名称", required=False, allow_null=True)
        apm_service_name = serializers.CharField(label="APM 服务名称", required=False, allow_null=True)

        metrics = serializers.ListField(label="查询的指标", allow_empty=True)
        where = ConditionSerializer(label="过滤条件", many=True, allow_empty=True, default=list)
        group_by = GroupBySerializer(label="聚合维度", many=True, allow_empty=True, default=list)
        common_conditions = serializers.ListField(label="常用维度过滤", default=list)
        limit = LimitSerializer(label="限制返回的series数量", default={})
        compare = CompareSerializer(label="对比配置", default={})
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    class ResponseSerializer(serializers.Serializer):
        class GroupSerializer(serializers.Serializer):
            name = serializers.CharField(label="分组名称", allow_blank=True)

            class PanelSerializer(serializers.Serializer):
                title = serializers.CharField(label="图表标题", allow_blank=True)
                sub_title = serializers.CharField(label="子标题", allow_blank=True)

                class TargetSerializer(serializers.Serializer):
                    expression = serializers.CharField(label="表达式")
                    alias = serializers.CharField(label="别名", allow_blank=True)
                    query_configs = serializers.ListField(label="查询配置")
                    function = serializers.DictField(label="图表函数", allow_null=True, default={})
                    metric = serializers.DictField(label="指标", allow_null=True, default={})
                    unit = serializers.CharField(label="单位", allow_blank=True, default="")

                targets = TargetSerializer(label="目标", many=True)

            panels = PanelSerializer(label="图表配置", many=True)

        groups = GroupSerializer(label="分组", many=True, allow_empty=True)

    UNITY_QUERY_OPERATOR_MAPPING = {
        "reg": "req",
        "nreg": "nreq",
        "include": "req",
        "exclude": "nreq",
        "eq": "contains",
        "neq": "ncontains",
    }

    @classmethod
    def time_or_no_compare(
        cls, table: CustomTSTable, metrics: list[CustomTSField], params: dict, dimension_names: dict[str, str]
    ) -> list[dict]:
        """
        时间对比或无对比
        """
        # 查询拆图维度组合
        split_dimensions = [x["field"] for x in params.get("group_by", []) if x["split"]]
        series_metrics = cls.query_metric_series(
            table=table, metrics=metrics, dimensions=split_dimensions, params=params
        )

        # 计算限制函数
        functions = []
        limit = params.get("limit", {})
        if limit.get("limit", 0) > 0 and limit.get("function", ""):
            limit_number = limit.get("limit", 10)
            functions = [{"id": limit["function"].lower(), "params": [{"id": "n", "value": limit_number}]}]

        # 时间对比函数
        function = {}
        compare_config = params.get("compare", {})
        if compare_config and compare_config.get("type") == "time" and compare_config.get("offset"):
            function = {"time_compare": compare_config["offset"]}

        # 非拆图维度
        non_split_dimensions = [x["field"] for x in params.get("group_by", []) if not x["split"]]

        # 根据拆图维度分组
        groups: list[dict] = []

        for series_tuple, metric_list in series_metrics.items():
            # 生成分组名称
            group_name = ""
            if not series_tuple:
                if len(series_metrics) > 1:
                    group_name = "-"
            else:
                group_name = "|".join([f"{dimension_names.get(key) or key}={value}" for key, value in series_tuple])

            panels = []
            for metric in metric_list:
                all_metric_dimensions = set(metric.config.get("dimensions", []))
                query_config = {
                    "metrics": [
                        {"field": metric.name, "method": metric.config.get("aggregate_method") or "AVG", "alias": "a"}
                    ],
                    "interval": "$interval",
                    "table": table.table_id,
                    "data_label": table.data_label.split(",")[0],
                    "data_source_label": DataSourceLabel.CUSTOM,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    # 只使用指标的维度
                    "group_by": list(set(non_split_dimensions) & all_metric_dimensions),
                    # TODO: 考虑也按指标的维度过滤
                    "where": params.get("where", []),
                    "functions": functions,
                    # 只使用指标的维度
                    "filter_dict": {
                        # 分组过滤条件
                        "group_filter": {x[0]: x[1] for x in series_tuple},
                        # 常用维度过滤
                        "common_filter": {
                            f"{condition['key']}__{condition['method']}": condition["value"]
                            for condition in params.get("common_conditions", [])
                            if condition["key"] in all_metric_dimensions
                        },
                    },
                }
                panels.append(
                    {
                        "title": metric.description or metric.name,
                        "sub_title": f"custom:{table.data_label.split(',')[0]}:{metric.name}",
                        "targets": [
                            {
                                "expression": "a",
                                "alias": "",
                                "query_configs": [query_config],
                                "function": function,
                                "metric": {"name": metric.name, "alias": metric.description},
                            }
                        ],
                    }
                )

            groups.append({"name": group_name, "panels": panels})
        return groups

    @classmethod
    def metric_compare(
        cls, table: CustomTSTable, metrics: list[CustomTSField], params: dict, dimension_names: dict[str, str]
    ) -> list[dict]:
        """
        指标对比
        """
        # 查询全维度组合
        all_dimensions = [d["field"] for d in params.get("group_by", [])]
        series_metrics = cls.query_metric_series(table=table, metrics=metrics, dimensions=all_dimensions, params=params)

        # 按照拆图维度分组
        split_dimensions = {d["field"] for d in params.get("group_by", []) if d["split"]}
        series_groups: dict[tuple[tuple[str, str]], dict[tuple[str, str], list[CustomTSField]]] = defaultdict(dict)
        for series_tuple, metric_list in series_metrics.items():
            # 计算拆图维度
            group_series = tuple((k, v) for k, v in series_tuple if k in split_dimensions)
            panel_series = tuple((k, v) for k, v in series_tuple if k not in split_dimensions)
            series_groups[group_series][panel_series] = metric_list

        # 计算限制函数
        functions = []
        limit = params.get("limit", {})
        if limit.get("limit", 0) > 0 and limit.get("function", ""):
            limit_number = limit.get("limit", 10)
            functions = [{"id": limit["function"].lower(), "params": [{"id": "n", "value": limit_number}]}]

        # 根据拆图维度分组
        groups = []
        for group_series, series_dict in series_groups.items():
            group_name = ""
            if not group_series:
                if len(series_groups) > 1:
                    group_name = "-"
            else:
                group_name = "|".join([f"{dimension_names.get(key) or key}={value}" for key, value in group_series])

            # 根据非拆图维度分图
            panels = []
            for panel_series, metric_list in series_dict.items():
                targets = []

                # 一张图里包含多个指标查询
                for metric in metric_list:
                    query_config = {
                        "metrics": [
                            {
                                "field": metric.name,
                                "method": metric.config.get("aggregate_method") or "AVG",
                                "alias": "a",
                            }
                        ],
                        "interval": "$interval",
                        "table": table.table_id,
                        "data_label": table.data_label.split(",")[0],
                        "data_source_label": DataSourceLabel.CUSTOM,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        # 只使用指标的维度
                        "group_by": [],
                        # TODO: 考虑也按指标的维度过滤
                        "where": params.get("where", []),
                        "functions": functions,
                        # 只使用指标的维度
                        "filter_dict": {
                            # 分组过滤条件
                            "group_filter": {x[0]: x[1] for x in group_series},
                            "panel_filter": {x[0]: x[1] for x in panel_series},
                            # 常用维度过滤
                            "common_filter": {
                                f"{condition['key']}__{condition['method']}": condition["value"]
                                for condition in params.get("common_conditions", [])
                                if condition["key"] in metric.config.get("dimensions", [])
                            },
                        },
                    }
                    targets.append(
                        {
                            "expression": "a",
                            "alias": "",
                            "query_configs": [query_config],
                            "metric": {"name": metric.name, "alias": metric.description},
                        }
                    )
                # 计算图表标题
                panel_title = "-"
                if panel_series:
                    panel_title = "|".join(
                        [f"{dimension_names.get(key) or key}={value}" for key, value in panel_series]
                    )

                panels.append({"title": panel_title, "sub_title": "", "targets": targets})

            groups.append({"name": group_name, "panels": panels})

        return groups

    @classmethod
    def query_metric_series(
        cls, table: CustomTSTable, metrics: list[CustomTSField], dimensions: list[str], params: dict
    ) -> dict[tuple[tuple[str, str]], list[CustomTSField]]:
        """
        查询指标系列
        """
        # 如果维度为空，则返回所有指标
        if not dimensions:
            return {(): metrics}

        # 指标字典
        metrics_dict = {x.name: x for x in metrics}

        # 转换条件格式为 unify_query.query_series 所需的格式
        conditions = {"field_list": [], "condition_list": []}
        for i, condition in enumerate(params.get("where", [])):
            if i > 0:
                conditions["condition_list"].append(condition.get("condition", "and"))

            value = condition["value"] if isinstance(condition["value"], list) else [condition["value"]]
            conditions["field_list"].append(
                {
                    "field_name": condition["key"],
                    "value": value,
                    "op": cls.UNITY_QUERY_OPERATOR_MAPPING.get(condition["method"], condition["method"]),
                }
            )

        # 维度排序
        dimensions = sorted(dimensions)

        # 根据metrics的维度与待查询维度的交集，确定查询的维度
        dimensions_to_metrics = defaultdict(list)
        for metric in metrics:
            metric_dimensions = tuple(d for d in dimensions if d in metric.config.get("dimensions", []))
            dimensions_to_metrics[metric_dimensions].append(metric.name)

        series_metrics = defaultdict(set)
        for dimension_tuple, metric_list in dimensions_to_metrics.items():
            # 如果维度为空，则不需要查询维度组合，直接使用空元组
            if not dimension_tuple:
                series_metrics[()].update(metric_list)
                continue

            result = api.unify_query.query_series(
                {
                    "bk_biz_ids": [params["bk_biz_id"]],
                    "start_time": params["start_time"],
                    "end_time": params["end_time"],
                    "metric_name": f"({'|'.join(metric_list)})",
                    "table_id": table.table_id,
                    "keys": list(dimension_tuple),
                    "conditions": conditions,
                }
            )
            for series in result.get("series", []):
                # 生成一个元组，用于唯一标识一个series，需要使用key进行排序
                series_tuple: tuple[tuple[str, str]] = tuple(sorted(list(zip(result.get("keys", []), series))))
                series_metrics[series_tuple].update(metric_list)

        return {key: [metrics_dict[x] for x in sorted(list(value))] for key, value in series_metrics.items()}

    def perform_request(self, params: dict) -> dict:
        # 如果指标为空，则返回空列表
        if not params["metrics"]:
            return {"groups": []}

        bk_biz_id = params["bk_biz_id"]
        if params.get("apm_app_name"):
            app_name = params.get("apm_app_name")
            service_name = params.get("apm_service_name")
            return self.get_custom_ts_graph_config_from_apm(
                bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name, params=params
            )
        else:
            time_series_group_id = params.get("time_series_group_id")
            return self.get_custom_ts_graph_config_from_global(
                bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id, params=params
            )

    @classmethod
    def get_custom_ts_graph_config_from_apm(
        cls, bk_biz_id: int, app_name: str, service_name: str, params: dict
    ) -> dict:
        from apm_web.models import Application

        app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) not found")
            return {"groups": []}

        if not app.time_series_group_id:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) metric data source is disabled")
            return {"groups": []}

        return cls.get_custom_ts_graph_config_from_global(bk_biz_id, app.time_series_group_id, params)

    @classmethod
    def get_custom_ts_graph_config_from_global(cls, bk_biz_id: int, time_series_group_id: int, params: dict) -> dict:
        table = CustomTSTable.objects.get(
            models.Q(bk_biz_id=bk_biz_id) | models.Q(is_platform=True),
            pk=time_series_group_id,
            bk_tenant_id=get_request_tenant_id(),
        )
        metrics = CustomTSField.objects.filter(
            time_series_group_id=time_series_group_id,
            type=MetricType.METRIC,
            name__in=params["metrics"],
        )

        dimension_names: dict[str, str] = {}
        for dimension in CustomTSField.objects.filter(
            type=MetricType.DIMENSION, time_series_group_id=time_series_group_id
        ):
            dimension_names[dimension.name] = dimension.description
        compare_config = params.get("compare", {})
        if not compare_config or compare_config.get("type") == "time":
            groups = cls.time_or_no_compare(table, metrics, params, dimension_names)
        elif compare_config.get("type") == "metric":
            groups = cls.metric_compare(table, metrics, params, dimension_names)
        else:
            raise ValueError(f"Invalid compare config type: {compare_config.get('type')}")

        return {"groups": groups}


class GraphDrillDownResource(Resource):
    """
    维度下钻
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                method = serializers.CharField(default="", allow_blank=True)
                field = serializers.CharField(default="")
                alias = serializers.CharField(required=False)
                display = serializers.BooleanField(default=False)

            class FunctionSerializer(serializers.Serializer):
                class FunctionParamsSerializer(serializers.Serializer):
                    value = serializers.CharField()
                    id = serializers.CharField()

                id = serializers.CharField()
                params = serializers.ListField(child=serializers.DictField(), allow_empty=True)

            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )
            data_source_label = serializers.CharField(label="数据来源")
            table = serializers.CharField(label="结果表名", allow_blank=True, default="")
            data_label = serializers.CharField(label="数据标签", allow_blank=True, default="")
            metrics = serializers.ListField(label="查询指标", allow_empty=True, child=MetricSerializer(), default=[])
            where = serializers.ListField(label="过滤条件", default=[])
            # group_by = serializers.ListField(label="聚合字段", default=[])
            interval_unit = serializers.ChoiceField(label="聚合周期单位", choices=("s", "m"), default="s")
            interval = serializers.CharField(label="时间间隔", default="auto")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
            index_set_id = serializers.IntegerField(required=False, label="索引集ID", allow_null=True)

            # 计算函数参数
            functions = serializers.ListField(label="计算函数参数", default=[], child=FunctionSerializer())

            def validate(self, attrs):
                # 索引集和结果表参数校验
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")

                # 聚合周期单位处理
                if attrs.get("interval") and attrs["interval_unit"] == "m":
                    # 分钟级别，interval 应该是int
                    try:
                        attrs["interval"] = int(attrs["interval"]) * 60
                    except ValueError:
                        pass
                return attrs

        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", allow_empty=False, child=QueryConfigSerializer())
        expression = serializers.CharField(label="查询表达式", allow_blank=True)
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        function = serializers.DictField(label="图表函数", required=False, default=dict)

        group_by = serializers.ListField(label="下钻维度列表", allow_empty=False)
        alert_id = serializers.IntegerField(label="告警事件ID", required=False, allow_null=True)
        aggregation_method = serializers.ChoiceField(
            label="聚合方法", choices=["sum", "avg", "max", "min"], required=False
        )

    class ResponseSerializer(serializers.Serializer):
        dimensions = serializers.DictField(label="维度值", allow_null=True)
        value = serializers.FloatField(label="当前值", allow_null=True)
        percentage = serializers.FloatField(label="占比", allow_null=True)
        unit = serializers.CharField(label="单位", allow_blank=True)

        class CompareValueSerializer(serializers.Serializer):
            value = serializers.FloatField(label="对比值", allow_null=True)
            offset = serializers.CharField(label="偏移量")
            fluctuation = serializers.FloatField(label="波动值", allow_null=True)

        compare_values = serializers.ListField(label="对比", default=[], child=CompareValueSerializer())

    many_response_data = True

    def get_value(self, params: dict, datapoints: list[tuple[float | None, int]]) -> float:
        """
        计算聚合值
        """
        # 获取聚合方法
        aggregation_method = params.get("aggregation_method")
        alert_id = params.get("alert_id")
        if aggregation_method:
            # 显式传入了聚合方法，使用指定的方法
            method = aggregation_method.lower()
        elif alert_id:
            # 传了 alert_id 但未传 aggregation_method，使用 avg
            method = "avg"
        else:
            # 都未传，使用第一个指标的方法（向后兼容）
            method = params["query_configs"][0]["metrics"][0]["method"].lower()

        values = [point[0] for point in datapoints if point[0] is not None]

        if not values:
            return None

        cal_funcs = {
            "sum": lambda x: sum(x),
            "avg": lambda x: sum(x) / len(x),
            "max": lambda x: max(x),
            "min": lambda x: min(x),
            "count": lambda x: sum(x),
        }

        # 检查方法是否支持
        if method not in cal_funcs:
            raise ValueError(f"not support method: {method}")

        cal_value = cal_funcs[method](values)
        return round(cal_value, 3)

    def perform_request(self, params: dict) -> list:
        for item in params["query_configs"]:
            item["group_by"] = params["group_by"]
        result = resource.grafana.graph_unify_query(params)

        dimensions_values: dict[tuple[tuple[str, str]], dict] = defaultdict(
            lambda: {"value": None, "percentage": None, "compare_values": {}, "unit": ""}
        )

        # 计算平均值
        for item in result["series"]:
            dimension_tuple = tuple(sorted(item["dimensions"].items()))
            value = self.get_value(params, item["datapoints"])

            # 判断是当前值还是时间对比值
            if not item.get("time_offset") or item["time_offset"] == "current":
                dimensions_values[dimension_tuple]["value"] = value
            else:
                dimensions_values[dimension_tuple]["compare_values"][item["time_offset"]] = value
            dimensions_values[dimension_tuple]["unit"] = item.get("unit") or ""

        # 计算占比
        sum_value = sum([x["value"] for x in dimensions_values.values() if x["value"] is not None])
        for item in dimensions_values.values():
            item["percentage"] = (
                round(item["value"] / sum_value * 100, 3) if sum_value and item["value"] is not None else None
            )

        # 数据组装
        rsp_data = []
        for dimension_tuple, dimension_value in dimensions_values.items():
            data = {
                "dimensions": dict(dimension_tuple),
                "value": dimension_value["value"],
                "unit": dimension_value["unit"],
                "percentage": dimension_value["percentage"],
                "compare_values": [
                    {
                        "value": value,
                        "offset": offset,
                        # 波动值
                        "fluctuation": round((value - dimension_value["value"]) / dimension_value["value"] * 100, 3)
                        if dimension_value["value"] and value is not None
                        else None,
                    }
                    for offset, value in dimension_value["compare_values"].items()
                ],
            }
            rsp_data.append(data)

        return rsp_data
