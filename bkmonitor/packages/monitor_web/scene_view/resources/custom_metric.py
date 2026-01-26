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
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api, resource
from monitor_web.models import CustomTSTable
from monitor_web.scene_view.resources.serializers import CustomMetricBaseRequestSerializer

logger = logging.getLogger("monitor_web")


class GetCustomMetricTargetListResource(Resource):
    """
    获取自定义指标目标列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        id = serializers.IntegerField(label=_("自定义指标分组 ID"))

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

    class RequestSerializer(CustomMetricBaseRequestSerializer):
        pass

    def perform_request(self, params: dict) -> dict[str, list]:
        # 从 metadata 获取指标分组列表
        request_params = {
            "group_id": params["time_series_group_id"],
            "include_metrics": True,
        }
        if params.get("scope_prefix"):
            request_params["scope_name"] = params["scope_prefix"]
        metadata_result = api.metadata.query_time_series_scope(**request_params)

        # 转换数据结构
        metric_groups = []
        for scope_data in metadata_result:
            scope_id = scope_data.get("scope_id")
            scope_name = scope_data.get("scope_name", "")
            # 去除 scope_prefix 前缀
            if params.get("scope_prefix") and scope_name.startswith(params["scope_prefix"]):
                scope_name = scope_name[len(params["scope_prefix"]) :]
            metric_list = scope_data.get("metric_list", [])
            dimension_config = scope_data.get("dimension_config", {})

            # 构建指标列表
            metrics = []
            for metric_data in metric_list:
                metric_name = metric_data.get("metric_name", "")
                # 过滤内置指标（APM 场景）
                if params.get("is_apm_scenario") and any(
                    [str(metric_name).startswith("apm_"), str(metric_name).startswith("bk_apm_")]
                ):
                    continue

                field_config = metric_data.get("field_config", {})
                # 如果指标隐藏或禁用，则不展示
                if field_config.get("hidden", False) or field_config.get("disabled", False):
                    continue

                # 构建维度列表
                dimensions = []
                for dimension_name in metric_data.get("tag_list", []):
                    dim_config = dimension_config.get(dimension_name, {})
                    # 如果维度隐藏，则不展示
                    if dim_config.get("hidden", False):
                        continue
                    dimensions.append({"name": dimension_name, "alias": dim_config.get("alias", dimension_name)})

                metrics.append(
                    {
                        "field_id": metric_data.get("field_id"),
                        "metric_name": metric_name,
                        "alias": field_config.get("alias", ""),
                        "dimensions": dimensions,
                    }
                )

            # 构建公共维度列表
            common_dimensions = []
            for dimension_name, dim_config in dimension_config.items():
                # 如果维度隐藏，则不展示
                if dim_config.get("hidden", False):
                    continue
                # 如果维度公共，则添加到公共维度
                if dim_config.get("common", False):
                    common_dimensions.append({"name": dimension_name, "alias": dim_config.get("alias", dimension_name)})

            metric_groups.append(
                {
                    "scope_id": scope_id,
                    "name": scope_name,
                    "metrics": metrics,
                    "common_dimensions": common_dimensions,
                }
            )
        # 对分组进行排序：default 在最前面，其他分组按字典顺序排序
        metric_groups.sort(key=lambda g: (g.get("name") != "default", g.get("name", "")))

        return {"metric_groups": metric_groups}


class GetCustomTsDimensionValues(Resource):
    """
    获取自定义时序维度值
    """

    class RequestSerializer(CustomMetricBaseRequestSerializer):
        class MetricSerializer(serializers.Serializer):
            scope_name = serializers.CharField(label=_("分组名称"), allow_blank=True, default="")
            name = serializers.CharField(label=_("指标名称"))

        dimension = serializers.CharField(label=_("维度"))
        start_time = serializers.IntegerField(label=_("开始时间"))
        end_time = serializers.IntegerField(label=_("结束时间"))
        metrics = serializers.ListField(label=_("指标"), child=serializers.JSONField())

        def validate(self, attrs):
            metrics_list = []
            for _metrics in attrs.get("metrics", []):
                if isinstance(_metrics, str):
                    metrics_list.append(_metrics)
                else:
                    s = self.MetricSerializer(data=_metrics)
                    s.is_valid(raise_exception=True)
                    metrics_list.append(s.validated_data["name"])
            attrs["metrics"] = metrics_list
            return super().validate(attrs)

    def perform_request(self, params: dict) -> list[dict]:
        # 如果指标为空，则返回空列表
        if not params["metrics"]:
            return []

        # 判断是否为 APM 场景
        is_apm_scenario = params.get("is_apm_scenario")

        if is_apm_scenario:
            data_label = "APM"
        else:
            table = CustomTSTable.objects.get(
                models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True),
                pk=params["time_series_group_id"],
                bk_tenant_id=get_request_tenant_id(),
            )
            data_label = table.data_label.split(",")[0]

        # 构建指标名称匹配部分
        if len(params["metrics"]) == 1:
            metric_match = f'__name__="bkmonitor:{data_label}:{params["metrics"][0]}"'
        else:
            metric_match = f'__name__=~"bkmonitor:{data_label}:({"|".join(params["metrics"])})"'

        # 如果是 APM 场景，添加额外的标签过滤
        label_filters = []
        if is_apm_scenario:
            label_filters.append(f'app_name="{params["apm_app_name"]}"')
            label_filters.append(f'service_name="{params["apm_service_name"]}"')

        # 组装完整的 PromQL 匹配表达式
        if label_filters:
            match = f"{{{metric_match}, {', '.join(label_filters)}}}"
        else:
            match = f"{{{metric_match}}}"

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

    class RequestSerializer(CustomMetricBaseRequestSerializer):
        class CompareSerializer(serializers.Serializer):
            type = serializers.ChoiceField(label=_("对比模式"), choices=["time", "metric"], required=False)
            offset = serializers.ListField(label=_("时间对比偏移量"), default=list)

        class LimitSerializer(serializers.Serializer):
            function = serializers.ChoiceField(label=_("限制函数"), choices=["top", "bottom"], default="")
            limit = serializers.IntegerField(label=_("限制数量"), default=0)

        class GroupBySerializer(serializers.Serializer):
            field = serializers.CharField(label=_("聚合维度"))
            split = serializers.BooleanField(label=_("是否拆分"), default=False)

        class ConditionSerializer(serializers.Serializer):
            key = serializers.CharField(label=_("字段名"))
            method = serializers.CharField(label=_("运算符"))
            value = serializers.ListField(label=_("值"))
            condition = serializers.ChoiceField(choices=["and", "or"], label=_("条件"), default="and")

        class MetricSerializer(serializers.Serializer):
            scope_name = serializers.CharField(label=_("分组名称"), allow_blank=True, default="")
            name = serializers.CharField(label=_("指标名称"))

        metrics = serializers.ListField(label=_("查询的指标"), default=[])
        where = ConditionSerializer(label=_("过滤条件"), many=True, allow_empty=True, default=list)
        group_by = GroupBySerializer(label=_("聚合维度"), many=True, allow_empty=True, default=list)
        common_conditions = serializers.ListField(label=_("常用维度过滤"), default=list)
        limit = LimitSerializer(label=_("限制返回的 series 数量"), default={})
        compare = CompareSerializer(label=_("对比配置"), default={})
        start_time = serializers.IntegerField(label=_("开始时间"))
        end_time = serializers.IntegerField(label=_("结束时间"))

        def validate(self, attrs):
            metrics_list = []
            for _metrics in attrs.get("metrics", []):
                if isinstance(_metrics, str):
                    metrics_list.append(_metrics)
                else:
                    s = self.MetricSerializer(data=_metrics)
                    s.is_valid(raise_exception=True)
                    metrics_list.append(s.validated_data["name"])
            attrs["metrics"] = metrics_list
            return super().validate(attrs)

    class ResponseSerializer(serializers.Serializer):
        class GroupSerializer(serializers.Serializer):
            name = serializers.CharField(label=_("分组名称"), allow_blank=True)

            class PanelSerializer(serializers.Serializer):
                title = serializers.CharField(label=_("图表标题"), allow_blank=True)
                sub_title = serializers.CharField(label=_("子标题"), allow_blank=True)

                class TargetSerializer(serializers.Serializer):
                    expression = serializers.CharField(label=_("表达式"))
                    alias = serializers.CharField(label=_("别名"), allow_blank=True)
                    query_configs = serializers.ListField(label=_("查询配置"))
                    function = serializers.DictField(label=_("图表函数"), allow_null=True, default={})
                    metric = serializers.DictField(label=_("指标"), allow_null=True, default={})
                    unit = serializers.CharField(label=_("单位"), allow_blank=True, default="")

                targets = TargetSerializer(label=_("目标"), many=True)

            panels = PanelSerializer(label=_("图表配置"), many=True)

        groups = GroupSerializer(label=_("分组"), many=True, allow_empty=True)

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
        cls, result_table_id: str, data_label: str, metrics: list[dict], params: dict, dimension_names: dict[str, str]
    ) -> list[dict]:
        """
        时间对比或无对比
        metrics: 从 metadata 获取的指标列表，格式为 [{"name": "metric_name", "alias": "别名", "dimensions": [...], "aggregate_method": "AVG"}]
        """
        # 查询拆图维度组合
        split_dimensions = [x["field"] for x in params.get("group_by", []) if x["split"]]
        series_metrics = cls.query_metric_series(
            result_table_id=result_table_id, metrics=metrics, dimensions=split_dimensions, params=params
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
                all_metric_dimensions = set(metric.get("dimensions", []))
                # 构建 filter_dict
                filter_dict = {
                    # 分组过滤条件
                    "group_filter": {x[0]: x[1] for x in series_tuple},
                    # 常用维度过滤
                    "common_filter": {
                        f"{condition['key']}__{condition['method']}": condition["value"]
                        for condition in params.get("common_conditions", [])
                        if condition["key"] in all_metric_dimensions
                    },
                }

                # 如果是 APM 场景，补充 service_name 和 scope_name
                if params.get("is_apm_scenario"):
                    filter_dict["scope_name"] = metric["scope_name"]
                    filter_dict["service_name"] = params["apm_service_name"]

                query_config = {
                    "metrics": [
                        {"field": metric["name"], "method": metric.get("aggregate_method") or "AVG", "alias": "a"}
                    ],
                    "interval": "$interval",
                    "table": result_table_id,
                    "data_label": data_label.split(",")[0],
                    "data_source_label": DataSourceLabel.CUSTOM,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    # 只使用指标的维度
                    "group_by": list(set(non_split_dimensions) & all_metric_dimensions),
                    # TODO: 考虑也按指标的维度过滤
                    "where": params.get("where", []),
                    "functions": functions + metric.get("function", []),
                    # 只使用指标的维度
                    "filter_dict": filter_dict,
                }
                panels.append(
                    {
                        "title": metric.get("alias") or metric["name"],
                        "sub_title": f"custom:{data_label.split(',')[0]}:{metric['name']}",
                        "targets": [
                            {
                                "expression": "a",
                                "alias": "",
                                "query_configs": [query_config],
                                "function": function,
                                "metric": {"name": metric["name"], "alias": metric.get("alias", "")},
                                "unit": metric.get("unit", ""),
                            }
                        ],
                    }
                )

            groups.append({"name": group_name, "panels": panels})
        return groups

    @classmethod
    def metric_compare(
        cls, result_table_id: str, data_label: str, metrics: list[dict], params: dict, dimension_names: dict[str, str]
    ) -> list[dict]:
        """
        指标对比
        metrics: 从 metadata 获取的指标列表，格式为 [{"name": "metric_name", "alias": "别名", "dimensions": [...], "aggregate_method": "AVG"}]
        """
        # 查询全维度组合
        all_dimensions = [d["field"] for d in params.get("group_by", [])]
        series_metrics = cls.query_metric_series(
            result_table_id=result_table_id, metrics=metrics, dimensions=all_dimensions, params=params
        )

        # 按照拆图维度分组
        split_dimensions = {d["field"] for d in params.get("group_by", []) if d["split"]}
        series_groups: dict[tuple[tuple[str, str]], dict[tuple[str, str], list[dict]]] = defaultdict(dict)
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
                    # 构建 filter_dict
                    filter_dict = {
                        # 分组过滤条件
                        "group_filter": {x[0]: x[1] for x in group_series},
                        "panel_filter": {x[0]: x[1] for x in panel_series},
                        # 常用维度过滤
                        "common_filter": {
                            f"{condition['key']}__{condition['method']}": condition["value"]
                            for condition in params.get("common_conditions", [])
                            if condition["key"] in metric.get("dimensions", [])
                        },
                    }

                    # 如果是 APM 场景，补充 service_name 和 scope_name
                    if params.get("is_apm_scenario"):
                        filter_dict["scope_name"] = metric["scope_name"]
                        filter_dict["service_name"] = params["apm_service_name"]

                    query_config = {
                        "metrics": [
                            {
                                "field": metric["name"],
                                "method": metric.get("aggregate_method") or "AVG",
                                "alias": "a",
                            }
                        ],
                        "interval": "$interval",
                        "table": result_table_id,
                        "data_label": data_label.split(",")[0],
                        "data_source_label": DataSourceLabel.CUSTOM,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        # 只使用指标的维度
                        "group_by": [],
                        # TODO: 考虑也按指标的维度过滤
                        "where": params.get("where", []),
                        "functions": functions + metric.get("function", []),
                        # 只使用指标的维度
                        "filter_dict": filter_dict,
                    }
                    targets.append(
                        {
                            "expression": "a",
                            "alias": "",
                            "query_configs": [query_config],
                            "metric": {"name": metric["name"], "alias": metric.get("alias", "")},
                            "unit": metric.get("unit", ""),
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
        cls, result_table_id: str, metrics: list[dict], dimensions: list[str], params: dict
    ) -> dict[tuple[tuple[str, str]], list[dict]]:
        """
        查询指标系列
        metrics: 从 metadata 获取的指标列表
        返回：{((维度key, 维度value),): [指标]}
        """
        # 如果维度为空，则返回所有指标
        if not dimensions:
            return {(): metrics}

        # 指标字典，使用指标名作为 key
        metrics_dict = {x["name"]: x for x in metrics}

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
            # 从 metadata 的指标中获取维度
            metric_dimensions = tuple(d for d in dimensions if d in metric.get("dimensions", []))
            dimensions_to_metrics[metric_dimensions].append(metric["name"])

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
                    "table_id": result_table_id,
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

        is_apm_scenario = params.get("is_apm_scenario")
        if is_apm_scenario:
            result_table_id = params["result_table_id"]
            data_label = "APM"
        else:
            result_table_id, data_label = (
                CustomTSTable.objects.filter(
                    models.Q(bk_biz_id=params["bk_biz_id"]) | models.Q(is_platform=True),
                    pk=params["time_series_group_id"],
                    bk_tenant_id=get_request_tenant_id(),
                )
                .values_list("table_id", "data_label")
                .first()
            )

        # 从 metadata 获取指标分组列表
        request_params = {
            "group_id": params["time_series_group_id"],
            "include_metrics": True,
        }
        if params.get("scope_prefix"):
            request_params["scope_name"] = params["scope_prefix"]
        metadata_result = api.metadata.query_time_series_scope(**request_params)

        # 构建指标字典和维度字典
        metrics_list = []
        dimension_names: dict[str, str] = {}

        # 构建请求的指标集合
        requested_metrics = set(params["metrics"])

        for scope_data in metadata_result:
            metric_list = scope_data.get("metric_list", [])
            dimension_config = scope_data.get("dimension_config", {})

            # 收集维度名称
            for dimension_name, dim_config in dimension_config.items():
                if not dim_config.get("hidden", False):
                    dimension_names[dimension_name] = dim_config.get("alias", dimension_name)

            # 收集指标信息
            for metric_data in metric_list:
                metric_name = metric_data.get("metric_name", "")
                field_config = metric_data.get("field_config", {})
                scope_name = metric_data.get("field_scope", "")

                # 只处理请求的指标
                if metric_name not in requested_metrics:
                    continue

                # 如果指标隐藏或禁用，则跳过
                if field_config.get("hidden", False) or field_config.get("disabled", False):
                    continue

                # 收集指标的维度（排除隐藏的维度）
                dimensions = [
                    dimension_name
                    for dimension_name in metric_data.get("tag_list", [])
                    if not dimension_config.get(dimension_name, {}).get("hidden", False)
                ]

                # 去除 scope_prefix 前缀
                if params.get("scope_prefix") and scope_name.startswith(params["scope_prefix"]):
                    scope_name = scope_name[len(params["scope_prefix"]) :]

                metrics_list.append(
                    {
                        "name": metric_name,
                        "alias": field_config.get("alias", ""),
                        "dimensions": dimensions,
                        "aggregate_method": field_config.get("aggregate_method", "AVG"),
                        "function": field_config.get("function", []),
                        "unit": field_config.get("unit", ""),
                        "scope_name": scope_name,
                    }
                )

        compare_config = params.get("compare", {})
        if not compare_config or compare_config.get("type") == "time":
            groups = self.time_or_no_compare(result_table_id, data_label, metrics_list, params, dimension_names)
        elif compare_config.get("type") == "metric":
            groups = self.metric_compare(result_table_id, data_label, metrics_list, params, dimension_names)
        else:
            raise ValueError(f"Invalid compare config type: {compare_config.get('type')}")

        from constants.apm import ApmMetricProcessor

        table_info = {"data_label": data_label, "table_id": result_table_id}

        # 根据匹配结果决定是否保留 data_label 字段
        if ApmMetricProcessor.is_match_data_label(table_info) and ApmMetricProcessor.is_match_table_id(table_info):
            for group in groups:
                for panel in group.get("panels", []):
                    for target in panel.get("targets", []):
                        for query_config in target.get("query_configs", []):
                            query_config.pop("data_label")

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
                label=_("数据类型"), default="time_series", allow_null=True, allow_blank=True
            )
            data_source_label = serializers.CharField(label=_("数据来源"))
            table = serializers.CharField(label=_("结果表名"), allow_blank=True, default="")
            data_label = serializers.CharField(label=_("数据标签"), allow_blank=True, default="")
            metrics = serializers.ListField(label=_("查询指标"), allow_empty=True, child=MetricSerializer(), default=[])
            where = serializers.ListField(label=_("过滤条件"), default=[])
            # group_by = serializers.ListField(label="聚合字段", default=[])
            interval_unit = serializers.ChoiceField(label=_("聚合周期单位"), choices=("s", "m"), default="s")
            interval = serializers.CharField(label=_("时间间隔"), default="auto")
            filter_dict = serializers.DictField(label=_("过滤条件"), default={})
            time_field = serializers.CharField(label=_("时间字段"), allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(label=_("日志查询语句"), default="", allow_blank=True)
            index_set_id = serializers.IntegerField(label=_("索引集ID"), required=False, allow_null=True)

            # 计算函数参数
            functions = serializers.ListField(label=_("计算函数参数"), default=[], child=FunctionSerializer())

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

        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        query_configs = serializers.ListField(label=_("查询配置列表"), allow_empty=False, child=QueryConfigSerializer())
        expression = serializers.CharField(label=_("查询表达式"), allow_blank=True)
        start_time = serializers.IntegerField(label=_("开始时间"))
        end_time = serializers.IntegerField(label=_("结束时间"))
        function = serializers.DictField(label=_("图表函数"), required=False, default=dict)

        group_by = serializers.ListField(label=_("下钻维度列表"), allow_empty=False)
        alert_id = serializers.IntegerField(label=_("告警事件ID"), required=False, allow_null=True)
        aggregation_method = serializers.ChoiceField(
            label=_("聚合方法"), choices=["sum", "avg", "max", "min"], required=False
        )

    class ResponseSerializer(serializers.Serializer):
        dimensions = serializers.DictField(label=_("维度值"), allow_null=True)
        value = serializers.FloatField(label=_("当前值"), allow_null=True)
        percentage = serializers.FloatField(label=_("占比"), allow_null=True)
        unit = serializers.CharField(label=_("单位"), allow_blank=True)

        class CompareValueSerializer(serializers.Serializer):
            value = serializers.FloatField(label=_("对比值"), allow_null=True)
            offset = serializers.CharField(label=_("偏移量"))
            fluctuation = serializers.FloatField(label=_("波动值"), allow_null=True)

        compare_values = serializers.ListField(label=_("对比"), default=[], child=CompareValueSerializer())

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
