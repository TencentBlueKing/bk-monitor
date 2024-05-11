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
import itertools
import json
import logging
import re
from collections import defaultdict
from typing import Callable, Dict, Generator, Iterable, List, Set, Tuple

from django.conf import settings
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bk_dataview.api import get_org_by_name
from bkmonitor.data_source import UnifyQuery, get_auto_interval, load_data_source
from bkmonitor.models import NO_DATA_TAG_DIMENSION, MetricListCache
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation
from constants.data_source import TS_MAX_SLIMIT, DataSourceLabel
from core.drf_resource import Resource, api, resource
from core.errors.api import BKAPIError
from monitor_web.grafana.data_migrate import TimeSeriesPanel

logger = logging.getLogger(__name__)


class GetGraphQueryConfig(Resource):
    """
    数据检索图表配置查询
    数据检索分为4种类型
    1. 不对比
    - 视图不合并: 按每个查询查出对应的维度，每个维度一张图平铺展示
    - 视图合并: 将所有指标和维度图表全部在一张图内进行展示
    - 数量限制: 限制每个指标的最大维度数量
    2. 目标对比
    - 每个指标一张图，不按维度分图，目的是对比不同的维度
    - 数量限制: 限制同一图表的最大维度数量
    3. 时间对比
    - 在不对比/视图不合并的基础上，每个维度查询多个时间段的数据
    - 数量限制: 限制每个指标的最大维度数量
    4. 指标对比
    - 每个维度一个图标，不同的指标放在同一图表内进行比较
    - 数量限制: 限制维度总数量
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()
                method = serializers.CharField()
                alias = serializers.CharField(required=False)

            class FunctionSerializer(serializers.Serializer):
                id = serializers.CharField()
                params = serializers.ListField(child=serializers.DictField(), allow_empty=True)

            class WhereSerializer(serializers.Serializer):
                condition = serializers.ChoiceField(required=False, choices=("and", "or"))
                key = serializers.CharField()
                method = serializers.CharField()
                value = serializers.ListField(child=serializers.CharField(allow_blank=True))

            class FilterDictSerializer(serializers.Serializer):
                targets = serializers.ListField(default=[], child=serializers.DictField())

            data_source_label = serializers.CharField(label="数据源标签")
            data_type_label = serializers.CharField(label="数据类型标签")
            metric = serializers.CharField(label="查询指标字段", required=False)
            method = serializers.CharField(label="聚合方法", required=False)
            alias = serializers.CharField(label="别名")
            table = serializers.CharField(label="结果表", required=False, allow_null=True, allow_blank=True)
            index_set_id = serializers.IntegerField(label="索引集ID", required=False, allow_null=True)
            promql = serializers.CharField(label="PromQL", default="")

            interval = serializers.CharField(label="聚合周期", default="auto")
            interval_unit = serializers.ChoiceField(label="聚合周期单位", choices=("s", "m"), default="s")
            group_by = serializers.ListField(
                label="聚合维度", child=serializers.CharField(allow_blank=False), required=False
            )
            where = serializers.ListField(label="查询条件", child=WhereSerializer(), required=False)
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, default=None)
            functions = serializers.ListField(label="计算函数参数", default=[], child=FunctionSerializer())
            filter_dict = FilterDictSerializer(required=False, allow_null=True)
            data_label = serializers.CharField(label="数据标识", required=False, allow_blank=True, allow_null=True)

            # 是否展示单指标
            display = serializers.BooleanField(label="是否单独展示", default=True)

            def validate(self, attrs):
                # 图表查询周期检查
                interval = attrs["interval"]
                if interval.isdigit():
                    attrs["interval"] = int(interval)

                # 索引集和结果表参数校验
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")
                # elif attrs["data_source_label"] != DataSourceLabel.BK_LOG_SEARCH and not attrs.get("table"):
                #     raise ValidationError("table can not be empty.")
                return attrs

        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置", allow_empty=False, child=QueryConfigSerializer())
        expressions = serializers.DictField(label="表达式", child=serializers.CharField(), default={})
        functions = serializers.DictField(label="计算函数", child=serializers.ListField(), default={})
        target = serializers.ListField(label="监控目标")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        compare_config = serializers.DictField(required=True, label="对比配置")

        def validate_target(self, target: List):
            """
            监控目标兼容两种目标格式
            """
            if not target:
                return []
            if isinstance(target[0], list):
                if not target[0]:
                    return []
                return target[0][0]["value"]
            return target

    @staticmethod
    def create_where_with_dimensions(where: list, dimensions: dict) -> List[Dict]:
        """
        在where条件中插入维度条件
        """
        default_condition = []
        for key, value in dimensions.items():
            if key == NO_DATA_TAG_DIMENSION:
                # 无数据标签不需要组装
                continue
            default_condition.append(
                {"condition": "and", "key": key, "method": "eq", "value": value if isinstance(value, list) else [value]}
            )

        new_where = []
        and_conditions = []
        for index, condition in enumerate(where.copy()):
            # 如果条件是and，则直接保存
            if condition.get("condition") != "or":
                and_conditions.append(condition)
                if index < len(where) - 1:
                    continue

            instance = load_agg_condition_instance(and_conditions)
            # 判断这组条件是否符合当前维度
            if and_conditions:
                if instance.is_match(dimensions):
                    and_conditions = [c for c in and_conditions if c["key"] not in dimensions]

                and_conditions.extend(default_condition)
                if new_where:
                    and_conditions[0]["condition"] = "or"
                else:
                    and_conditions[0].pop("condition", None)
                new_where.extend(and_conditions)

            and_conditions = []
            if condition.get("condition") == "or":
                and_conditions.append(condition)

        if and_conditions:
            instance = load_agg_condition_instance(and_conditions)
            if instance.is_match(dimensions):
                and_conditions = [c for c in and_conditions if c["key"] not in dimensions]
                and_conditions.extend(default_condition)
                if new_where:
                    and_conditions[0]["condition"] = "or"
                else:
                    and_conditions[0].pop("condition", None)
                new_where.extend(and_conditions)

        # 如果没有任何条件，则需要补全维度条件
        if not new_where:
            new_where = default_condition

        # 去除第一个条件的and/or
        if new_where and new_where[0].get("condition"):
            del new_where[0]["condition"]

        return new_where

    @staticmethod
    def to_unify_query(query_config: Dict) -> Dict:
        """
        查询配置转换
        """
        query_config = json.loads(json.dumps(query_config))

        where = query_config["where"]
        filter_dict = query_config.get("filter_dict", {})
        if filter_dict and filter_dict["targets"] and filter_dict["targets"][0]:
            for k, v in filter_dict["targets"][0].items():
                condition = {
                    "condition": "and",
                    "key": k,
                    "method": "include",
                }
                if not isinstance(v, list):
                    condition["value"] = [v]
                else:
                    condition["value"] = v
                where.append(condition)

        return {
            "data_source_label": query_config["data_source_label"],
            "data_type_label": query_config["data_type_label"],
            "metrics": [
                {"field": query_config["metric"], "method": query_config["method"], "alias": query_config["alias"]}
            ],
            "table": query_config.get("table", ""),
            "data_label": query_config.get("data_label", ""),
            "index_set_id": query_config.get("index_set_id"),
            "group_by": query_config["group_by"],
            "where": where,
            "interval": query_config["interval"],
            "interval_unit": query_config["interval_unit"],
            "time_field": query_config["time_field"],
            "filter_dict": {},
            "functions": query_config["functions"],
        }

    @staticmethod
    def get_dimension_fields(config: Dict) -> List[str]:
        """
        获取查询配置维度
        """
        dimension_fields = set()
        for query_config in config["query_configs"]:
            # 当使用histogram_quantile时，维度查询需要去除le维度
            remove_le = False
            for function in query_config["functions"]:
                if function["id"] == "histogram_quantile":
                    remove_le = True

            group_by = query_config["group_by"].copy()
            if remove_le and "le" in group_by:
                group_by.remove("le")
            dimension_fields.update(group_by)
        return sorted(list(dimension_fields))

    @classmethod
    def create_unify_query_config(
        cls, bk_biz_id: int, query_configs: List[Dict], expressions: Dict[str, str], functions: Dict[str, List]
    ) -> List[Dict]:
        """
        解析表达式，生产unify-query配置
        """
        configs = []

        for query_config in query_configs:
            if query_config["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                metric = MetricListCache.objects.filter(
                    data_source_label=query_config["data_source_label"],
                    data_type_label=query_config["data_type_label"],
                    related_id=query_config["index_set_id"],
                    metric_field=query_config["metric"],
                )

            else:
                metric = MetricListCache.objects.filter(
                    data_source_label=query_config["data_source_label"],
                    data_type_label=query_config["data_type_label"],
                    result_table_id=query_config["table"],
                    metric_field=query_config["metric"],
                )

            if not metric:
                query_config["name"] = f'{query_config["method"]}({query_config["metric"]})'
            else:
                metric = metric[0]
                query_config["name"] = f'{query_config["method"]}({metric.metric_field_name})'

        # 单指标生成查询配置
        for query_config in query_configs:
            if not query_config["display"]:
                continue
            configs.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "query_configs": [cls.to_unify_query(query_config)],
                    "expression": query_config["alias"],
                    "alias": query_config["alias"],
                    "name": query_config["name"],
                }
            )

        # 表达式生成查询配置
        for alias, expression in expressions.items():
            config = {
                "bk_biz_id": bk_biz_id,
                "query_configs": [],
                "expression": expression,
                "functions": functions.get(alias, []),
                "alias": alias,
            }

            name = expression
            for query_config in query_configs:
                if query_config["alias"] not in expression:
                    continue
                name = name.replace(query_config["alias"], query_config["name"])
                config["query_configs"].append(cls.to_unify_query(query_config))
            config["name"] = name
            configs.append(config)
        return configs

    @classmethod
    def get_condition_set(cls, unify_query_config, dimensions_set, instance_dimensions_set):
        """
        获取指定条件维度集合
        """

        and_conditions = []
        or_conditions = []
        all_conditions = []
        # 筛选已聚合的条件维度
        for query_config in unify_query_config["query_configs"]:
            condition_keys = [where["key"] for where in query_config["where"]]
            if not set(condition_keys) <= set(query_config["group_by"]):
                continue
            for where in query_config["where"]:
                if where["method"] != "eq":
                    break
                condition = where.get("condition", "and")
                if condition == "and":
                    and_conditions.append(tuple((where["key"], str(value)) for value in where["value"]))
                elif condition == "or":
                    or_conditions.append(and_conditions)
                    and_conditions = [tuple((where["key"], str(value)) for value in where["value"])]
            if and_conditions:
                or_conditions.append(and_conditions)

        for or_cond in or_conditions:
            all_conditions.extend(list(itertools.product(*or_cond)))

        condition_dimensions_set = set()
        cond_map = defaultdict(set)
        for condition in all_conditions:
            cond_key = tuple(sorted([cond[0] for cond in condition]))
            cond_map[cond_key].add(tuple(sorted(list(condition))))

        for cond_key, conditions in cond_map.items():
            origin_dimensions_set = set()
            # 原始维度数据过滤
            for origin_dimensions in dimensions_set:
                origin_dimensions_set.add(
                    tuple(
                        sorted(
                            [
                                (dimension[0], dimension[1])
                                for dimension in origin_dimensions
                                if dimension[0] in cond_key
                            ]
                        )
                    )
                )
            # 目标维度数据过滤
            for instance_dimensions in instance_dimensions_set:
                origin_dimensions_set.add(
                    tuple(
                        sorted(
                            [
                                (dimension[0], dimension[1])
                                for dimension in instance_dimensions
                                if dimension[0] in cond_key
                            ]
                        )
                    )
                )
            condition_dimensions_set = condition_dimensions_set | {
                cond for cond in conditions if cond not in origin_dimensions_set
            }

        return condition_dimensions_set

    @classmethod
    def get_dimensions_set(cls, params, unify_query_config: Dict) -> Tuple[Set[Tuple[Tuple]], List[Tuple[Tuple]]]:
        """
        查询维度组合
        """
        unify_query_config = json.loads(json.dumps(unify_query_config))
        dimension_fields = cls.get_dimension_fields(unify_query_config)
        # 维度字段
        for query_config in unify_query_config["query_configs"]:
            query_config["functions"] = []
            query_config["interval"] = get_auto_interval(60, params["start_time"], params["end_time"])

        data_source_label = unify_query_config["query_configs"][0]["data_source_label"]

        # 将节点解析为实例
        target_instances = resource.cc.parse_topo_target(params["bk_biz_id"], list(dimension_fields), params["target"])
        if target_instances is None:
            return set(), []

        if target_instances:
            for query_config in unify_query_config["query_configs"]:
                if "filter_dict" not in query_config:
                    query_config["filter_dict"] = {}
                query_config["filter_dict"]["target"] = target_instances

        # 维度数据查询
        data_sources = []
        for query_config in unify_query_config["query_configs"]:
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_sources.append(data_source_class(bk_biz_id=params["bk_biz_id"], **query_config))

        query = UnifyQuery(
            bk_biz_id=params["bk_biz_id"], data_sources=data_sources, expression=unify_query_config["expression"]
        )
        points = query.query_data(
            start_time=params["start_time"] * 1000,
            end_time=params["end_time"] * 1000,
            limit=settings.SQL_MAX_LIMIT
            if data_source_label in [DataSourceLabel.BK_DATA, DataSourceLabel.BK_LOG_SEARCH]
            else 1,
            slimit=TS_MAX_SLIMIT,
        )

        # 取出所有的维度组合
        dimensions_set: Set[Tuple] = set()
        for point in points:
            dimensions = tuple((field, point[field]) for field in dimension_fields if field in point)
            if len(dimensions) < len(dimension_fields):
                continue
            dimensions_set.add(tuple(dimensions))

        # 有监控目标的，按目标实例补全空图
        target_dimensions_set = set()
        if target_instances:
            target_dimensions = target_instances[0].keys()
            for origin_dimensions in dimensions_set:
                target_dimensions_set.add(
                    tuple(
                        (dimension[0], dimension[1])
                        for dimension in origin_dimensions
                        if dimension[0] in target_dimensions
                    )
                )

        instance_dimensions_set: Set[Tuple] = set()
        for target_instance in target_instances:
            dimensions_list = [{}]
            for key, value in target_instance.items():
                if not isinstance(value, list):
                    value = [value]
                for v in value:
                    dimensions_list = [{**dimension, key: v} for dimension in dimensions_list if key not in dimension]
            for dimensions in dimensions_list:
                dimension_tuple = tuple(sorted([(key, str(value)) for key, value in dimensions.items()]))
                if dimension_tuple in target_dimensions_set:
                    continue
                instance_dimensions_set.add(dimension_tuple)

        # 有查询条件的，按条件维度补全空图
        condition_dimensions_set = cls.get_condition_set(unify_query_config, dimensions_set, instance_dimensions_set)

        return dimensions_set, sorted(list(instance_dimensions_set | condition_dimensions_set))

    @classmethod
    def get_dimensions_translate_mapping(cls, bk_biz_id: int, dimension_set: Iterable[Tuple[Tuple]]) -> Dict:
        """
        维度翻译映射
        """
        dimension_mapping = defaultdict(dict)

        host_id_set = set()
        service_instance_id_set = set()
        for dimensions in dimension_set:
            for key, value in dimensions:
                if key == "bk_host_id":
                    host_id_set.add(value)
                elif key in ["service_instance_id", "bk_target_service_instance_id"]:
                    service_instance_id_set.add(value)

        if host_id_set:
            try:
                hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=list(host_id_set))
            except BKAPIError:
                hosts = []
            dimension_mapping["bk_host_id"] = {str(host.bk_host_id): host.display_name for host in hosts}

        if service_instance_id_set:
            try:
                service_instances = api.cmdb.get_service_instance_by_id(
                    bk_biz_id=bk_biz_id, service_instance_ids=list(service_instance_id_set)
                )
            except BKAPIError:
                service_instances = []
            dimension_mapping["service_instance_id"] = {
                str(service_instance.service_instance_id): service_instance.name
                for service_instance in service_instances
            }
            dimension_mapping["bk_target_service_instance_id"] = dimension_mapping["service_instance_id"]

        return dimension_mapping

    @classmethod
    def no_compare(cls, params: Dict, unify_query_configs: List[Dict]) -> List[Dict]:
        """
        不对比
        - 每个指标的每个维度一张图
          表名: 一个指标信息
          别名: 维度组合，如果为空则使用指标名
        - 视图合并，全部数据放到一张图上
          表名: 多个指标信息
          别名: 指标名+维度组合
        """

        index = 1
        panels: List[dict] = (
            []
            if params["compare_config"].get("split", True)
            else [{"id": 1, "type": "graph", "title": _("总览"), "subTitle": "", "targets": []}]
        )

        for unify_query_config in unify_query_configs:
            # 查询维度
            dimension_fields = cls.get_dimension_fields(unify_query_config)

            # 对比配置
            if params["compare_config"].get("split", True):
                # 根据维度生成图表查询配置
                for i, dimensions_set in enumerate(cls.get_dimensions_set(params, unify_query_config)):
                    # 维度翻译
                    dimensions_translate_mapping = cls.get_dimensions_translate_mapping(
                        params["bk_biz_id"], dimensions_set
                    )

                    for dimension_tuple in dimensions_set:
                        new_unify_query_config: Dict = json.loads(json.dumps(unify_query_config))
                        dimensions: Dict = {field: value for field, value in dimension_tuple}

                        # 按维度增加过滤条件
                        for query_config in new_unify_query_config["query_configs"]:
                            query_config["where"] = cls.create_where_with_dimensions(
                                query_config["where"],
                                {
                                    field: value
                                    for field, value in dimensions.items()
                                    if field in query_config["group_by"]
                                },
                            )

                        # 图例名表达式
                        if dimension_fields:
                            alias = " | ".join(f"$tag_{field}" for field in dimension_fields)
                        else:
                            if len(new_unify_query_config["query_configs"]) > 1:
                                alias = new_unify_query_config["alias"]
                            else:
                                alias = new_unify_query_config["name"]

                        # 使用dimension_fields保证标题与图例的维度顺序是相同的
                        dimension_string = " | ".join(
                            str(dimensions_translate_mapping[field].get(dimensions[field], dimensions[field]))
                            for field in dimension_fields
                            if field in dimensions
                        )
                        title = unify_query_config["name"]
                        if i == 1 and dimension_string:
                            title += " - " + dimension_string
                        group = (
                            f"{_('查询项') if len(unify_query_config['expression']) == 1 else _('表达式')}"
                            f"{unify_query_config['alias']} {unify_query_config['name']}"
                        )
                        panels.append(
                            {
                                "id": index,
                                "type": "graph",
                                "title": title,
                                "subTitle": "",
                                "index": dimension_string,
                                "group": group,
                                "targets": [
                                    {
                                        "data": new_unify_query_config,
                                        "datasourceId": "time_series",
                                        "name": _("时序数据"),
                                        "alias": alias,
                                        "source": unify_query_config["alias"],
                                    }
                                ],
                            }
                        )
                        index += 1
            else:
                # 如果进行视图合并，只需要将查询配置全部放到targets下即可
                new_unify_query_config: Dict = json.loads(json.dumps(unify_query_config))
                new_unify_query_config["slimit"] = TS_MAX_SLIMIT
                new_unify_query_config["target"] = params["target"]
                if len(new_unify_query_config["query_configs"]) > 1:
                    alias = new_unify_query_config["alias"]
                else:
                    alias = new_unify_query_config["name"]

                if dimension_fields:
                    alias += " - " + " | ".join(f"$tag_{field}" for field in dimension_fields)

                panels[0]["targets"].append(
                    {
                        "data": new_unify_query_config,
                        "datasourceId": "time_series",
                        "name": _("时序数据"),
                        "alias": alias,
                        "source": unify_query_config["alias"],
                    }
                )

        return panels

    @classmethod
    def metric_compare(cls, params: Dict, unify_query_configs: List[Dict]) -> List[Dict]:
        """
        指标对比
        - 将相同维度不同指标放在一张图上
          表名：维度组合
          别名: 指标名
        """
        dimensions_targets = defaultdict(lambda: [])

        for unify_query_config in unify_query_configs:
            for dimensions_set in cls.get_dimensions_set(params, unify_query_config):
                # 维度翻译
                dimensions_translate_mapping = cls.get_dimensions_translate_mapping(params["bk_biz_id"], dimensions_set)

                for dimensions in dimensions_set:
                    new_unify_query_config: Dict = json.loads(json.dumps(unify_query_config))

                    # 按维度增加过滤条件
                    for query_config in new_unify_query_config["query_configs"]:
                        query_config["filter_dict"] = {
                            field: value for field, value in dimensions if field in query_config["group_by"]
                        }

                    if len(new_unify_query_config["query_configs"]) > 1:
                        alias = new_unify_query_config["alias"]
                    else:
                        alias = new_unify_query_config["name"]

                    translated_dimensions = tuple(
                        (key, dimensions_translate_mapping[key].get(value, value)) for key, value in dimensions
                    )
                    dimensions_targets[translated_dimensions].append(
                        {
                            "data": new_unify_query_config,
                            "datasourceId": "time_series",
                            "name": _("时序数据"),
                            "alias": alias,
                            "source": unify_query_config["alias"],
                        }
                    )

        panels = []
        index = 1
        for dimensions, targets in dimensions_targets.items():
            title = " | ".join(value for field, value in dimensions)
            panels.append(
                {
                    "id": index,
                    "type": "graph",
                    "title": title,
                    "subTitle": "",
                    "index": title,
                    "group": "",
                    "targets": targets,
                }
            )
            index += 1
        return panels

    @classmethod
    def target_compare(cls, params: Dict, unify_query_configs: List[Dict]) -> List[Dict]:
        """
        目标对比(维度对比)
        - 每个指标一张图
          表名: 指标名
          别名: 维度组合，如果为空则使用指标名
        """
        panels = []
        for index, unify_query_config in enumerate(unify_query_configs):
            # 查询维度
            dimension_fields: Set[str] = set()
            for query_config in unify_query_config["query_configs"]:
                dimension_fields.update(query_config["group_by"])

            # 别名表达式
            if dimension_fields:
                alias = " | ".join(f"$tag_{field}" for field in dimension_fields)
            else:
                alias = "result"

            new_unify_query_config: Dict = json.loads(json.dumps(unify_query_config))
            new_unify_query_config["slimit"] = TS_MAX_SLIMIT
            new_unify_query_config["target"] = params["target"]

            panels.append(
                {
                    "id": index + 1,
                    "type": "graph",
                    "title": unify_query_config["name"],
                    "subTitle": "",
                    "targets": [
                        {
                            "data": new_unify_query_config,
                            "datasourceId": "time_series",
                            "name": _("时序数据"),
                            "alias": alias,
                            "source": unify_query_config["alias"],
                        }
                    ],
                }
            )

        return panels

    @classmethod
    def time_compare(cls, params: Dict, unify_query_configs: List[Dict]) -> List[Dict]:
        """
        时间对比
        - 查询多段时间数据
          表名: 指标名
          别名: 时间前缀+维度组合
        """
        time_offset = params["compare_config"].get("time_offset", [])

        # 兼容单个时间对比配置
        if not isinstance(time_offset, list):
            time_offset = [time_offset]
        time_offset = [offset_text for offset_text in time_offset if re.match(r"\d+[mhdwMy]", str(offset_text))]

        panels = cls.no_compare(params, unify_query_configs)
        for panel in panels:
            targets = panel["targets"]
            for target in targets:
                unify_query_config = target["data"]

                # 查询维度
                dimension_fields: Set[str] = set()
                for query_config in unify_query_config["query_configs"]:
                    dimension_fields.update(query_config["group_by"])

                # 别名表达式
                alias = "$time_offset"
                if dimension_fields:
                    alias += " - " + " | ".join(f"$tag_{field}" for field in dimension_fields)

                target["alias"] = alias
                unify_query_config["function"] = {"time_compare": time_offset}

        return panels

    def perform_request(self, params):
        # promql查询兼容
        if params["query_configs"][0]["data_source_label"] == DataSourceLabel.PROMETHEUS:
            query_configs = []
            for query_config in params["query_configs"]:
                query_configs.append(
                    {
                        "alias": query_config["alias"],
                        "promql": query_config["promql"],
                        "step": query_config["interval"],
                    }
                )

            return resource.data_explorer.get_promql_query_config(
                bk_biz_id=params["bk_biz_id"],
                query_configs=query_configs,
                compare_config=params["compare_config"],
                start_time=params["start_time"],
                end_time=params["end_time"],
            )

        compare_type = params["compare_config"].get("type")
        unify_query_configs = self.create_unify_query_config(
            bk_biz_id=params["bk_biz_id"],
            query_configs=params["query_configs"],
            expressions=params["expressions"],
            functions=params["functions"],
        )

        compare_func: Dict[str, Callable[[Dict, List], List]] = defaultdict(
            lambda: self.no_compare,
            {"time": self.time_compare, "metric": self.metric_compare, "target": self.target_compare},
        )

        panels = compare_func[compare_type](params, unify_query_configs)

        ret = {
            "title": _("数据检索"),
            "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "30m", "1h", "2h", "1d"]},
            "panels": panels,
        }
        return ret


class GetPromqlQueryConfig(Resource):
    """
    PromQL模式数据检索图表配置

    对比分组
    1. 不对比
      每个查询项是panel，title为查询项名
    2. 合并
      将所有数据塞到一个panel中，无group，title为总览

    compare_config: {
        "type": "time",
        "time_offset": ["1h", "1d"],
        "split": true
    }
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            promql = serializers.CharField(label="PromQL")
            step = serializers.CharField(default="auto")
            alias = serializers.CharField()

        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置", child=QueryConfigSerializer())

        compare_config = serializers.DictField(required=True, label="对比配置")

        step = serializers.CharField(label="周期", default="")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")

    def create_unify_query_config(self, params: Dict):
        """
        生成unify-query查询参数
        """
        bk_biz_id = params["bk_biz_id"]

        unify_query_configs = []
        for query_config in params["query_configs"]:
            if query_config["step"] == "auto":
                interval = get_auto_interval(60, params["start_time"], params["end_time"])
            else:
                if query_config["step"].isdigit():
                    query_config["step"] = f"{query_config['step']}s"
                interval = -parse_time_compare_abbreviation(query_config["step"])
            unify_query_configs.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "query_configs": [
                        {
                            "data_source_label": "prometheus",
                            "data_type_label": "time_series",
                            "promql": query_config["promql"],
                            "interval": interval,
                            "alias": query_config["alias"],
                        }
                    ],
                    "expression": "",
                    "alias": query_config["alias"],
                }
            )

        return unify_query_configs

    def no_compare(self, params: Dict, unify_query_configs: List[Dict]) -> List[Dict]:
        """
        不对比
        """
        panels = []
        index = 1
        if params["compare_config"].get("split", True):
            for query_config in unify_query_configs:
                panels.append(
                    {
                        "id": index,
                        "type": "graph",
                        "title": query_config["alias"],
                        "subTitle": "",
                        "group": query_config["alias"],
                        "targets": [
                            {
                                "data": query_config,
                                "datasourceId": "time_series",
                                "name": _("时序数据"),
                                "alias": "",
                                "source": query_config["alias"],
                            }
                        ],
                    }
                )
                index += 1
        else:
            targets = []
            for query_config in unify_query_configs:
                query_config["expression"] = query_config["alias"]
                targets.append(
                    {
                        "data": query_config,
                        "datasourceId": "time_series",
                        "name": _("时序数据"),
                        "alias": "",
                        "source": query_config["alias"],
                    }
                )
            panels.append(
                {
                    "id": index,
                    "type": "graph",
                    "title": _("总览"),
                    "subTitle": "",
                    "group": _("总览"),
                    "targets": targets,
                }
            )

        return panels

    def perform_request(self, params):
        query_configs = self.create_unify_query_config(params)
        panels = self.no_compare(params, query_configs)
        return {
            "title": _("数据检索"),
            "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "30m", "1h", "2h", "1d"]},
            "panels": panels,
        }


class GetEventViewConfig(Resource):
    """
    事件检索视图配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        table_id = serializers.IntegerField(required=True, label="结果表ID")
        data_source_label = serializers.CharField(required=True, label="数据来源")
        data_type_label = serializers.CharField(required=True, label="数据类型")
        name = serializers.CharField(default="事件检索配置", allow_blank=True, label="图表配置名")
        query_string = serializers.CharField(default="", allow_blank=True, label="查询语句")

    @classmethod
    def get_panel_config(cls, params):
        """
        生成图表配置
        """

        return [
            {
                "id": f"{params['table_id']}",
                "type": "graph",
                "title": params["name"],
                "subTitle": f"{params['table_id']}{params['name']}",
                "targets": [
                    {
                        "data": {
                            "alias": "A",
                            "bk_biz_id": params["bk_biz_id"],
                            "expression": "A",
                            "query_configs": [
                                {
                                    "metrics": [{"field": "_index", "method": "COUNT", "alias": "A"}],
                                    "interval": 60,
                                    "table": params["table_id"],
                                    "data_source_label": params["data_source_label"],
                                    "data_type_label": params["data_type_label"],
                                    "group_by": [],
                                    "query_string": params.get("query_string", ""),
                                    "bk_biz_id": 2,
                                    "where": [],
                                    "functions": [],
                                }
                            ],
                        },
                        "alias": "event.count",
                        "datasourceId": "time_series",
                        "name": _("时序数据"),
                    }
                ],
            },
            {
                "id": f"table_{params['table_id']}",
                "type": "table",
                "title": _("{} - 事件数据").format(params['name']),
                "targets": [
                    {
                        "data": {
                            "alias": "A",
                            "bk_biz_id": params["bk_biz_id"],
                            "expression": "A",
                            "data_format": "table",
                            "query_string": params.get("query_string", ""),
                            "data_source_label": params["data_source_label"],
                            "data_type_label": params["data_type_label"],
                            "result_table_id": params["table_id"],
                            "where": [],
                            "limit": 20,
                        },
                        "datasourceId": "log",
                        "name": _("事件数据"),
                    }
                ],
            },
        ]

    def perform_request(self, params):
        return {
            "title": _("事件检索图表"),
            "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "30m", "1h", "2h", "1d"]},
            "panels": self.get_panel_config(params),
        }


class SaveToDashboard(Resource):
    class RequestSerializer(serializers.Serializer):
        class PanelSerializer(serializers.Serializer):
            class QuerySerializer(serializers.Serializer):
                class QueryConfigSerializer(serializers.Serializer):
                    class MetricSerializer(serializers.Serializer):
                        field = serializers.CharField()
                        method = serializers.CharField()
                        alias = serializers.CharField(required=False)
                        display = serializers.BooleanField(default=False)

                    class FunctionSerializer(serializers.Serializer):
                        class FunctionParamsSerializer(serializers.Serializer):
                            id = serializers.CharField()
                            value = serializers.CharField()

                        id = serializers.CharField()
                        params = serializers.ListField(child=serializers.DictField(), allow_empty=True)

                    data_source_label = serializers.CharField(label="数据来源")
                    data_type_label = serializers.CharField(
                        label="数据类型", default="time_series", allow_null=True, allow_blank=True
                    )
                    display = serializers.BooleanField(default=False)
                    metrics = serializers.ListField(
                        label="查询指标", allow_empty=False, child=MetricSerializer(), required=False
                    )
                    promql = serializers.CharField(default="")
                    table = serializers.CharField(label="结果表名", required=False, allow_blank=True)
                    data_label = serializers.CharField(label="db标识", required=False, allow_blank=True)
                    where = serializers.ListField(label="过滤条件", default=[])
                    group_by = serializers.ListField(label="聚合字段", default=[])
                    interval = serializers.CharField(default=60, label="时间间隔")
                    interval_unit = serializers.ChoiceField(label="聚合周期单位", choices=("s", "m", "h"), default="s")
                    filter_dict = serializers.DictField(default={}, label="过滤条件")
                    time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

                    # 日志平台配置
                    query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
                    index_set_id = serializers.IntegerField(required=False, label="索引集ID", allow_null=True)

                    # 计算函数参数
                    functions = serializers.ListField(label="计算函数参数", default=[], child=FunctionSerializer())

                expression = serializers.CharField(allow_blank=True)
                alias = serializers.CharField(default="", allow_blank=True)
                query_configs = serializers.ListField(child=QueryConfigSerializer())
                function = serializers.DictField(default={})
                functions = serializers.ListField(
                    label="计算函数", default=[], child=QueryConfigSerializer.FunctionSerializer()
                )

            name = serializers.CharField(label="图表名称")
            queries = serializers.ListField(label="查询配合", allow_empty=False, child=QuerySerializer())
            fill = serializers.BooleanField(default=False)
            min_y_zero = serializers.BooleanField(default=False)

        bk_biz_id = serializers.IntegerField()
        panels = serializers.ListField(allow_empty=False, child=PanelSerializer())
        dashboard_uids = serializers.ListField(allow_empty=True, child=serializers.CharField())

    @classmethod
    def add_target(
        cls, panel: TimeSeriesPanel, functions: list, query_configs: List[Dict], alias: str, expression: str
    ):
        """
        添加target配置
        """
        if query_configs[0]["data_source_label"] == DataSourceLabel.PROMETHEUS:
            panel.targets.append(
                {
                    "refId": "A",
                    "source": query_configs[0]["promql"],
                    "step": f"{query_configs[0]['interval']}s",
                    "format": "time_series",
                    "type": "range",
                    "mode": "code",
                }
            )
        else:
            new_query_configs = json.loads(json.dumps(query_configs))
            if len(new_query_configs) == 1 and not functions:
                new_query_configs[0]["alias"] = alias
                new_query_configs[0]["display"] = True
            panel.targets.append(
                {
                    "cluster": [],
                    "expressionList": [
                        {"active": True, "expression": expression, "functions": functions, "alias": alias or ""}
                    ]
                    if len(new_query_configs) > 1 or functions
                    else [],
                    "host": [],
                    "module": [],
                    "query_configs": new_query_configs,
                    "refId": chr(ord("A") + len(panel.targets)),
                }
            )

    @classmethod
    def get_panel(cls, panel_config: dict) -> TimeSeriesPanel:
        """
        获取图表配置
        """
        panel = TimeSeriesPanel(
            title=panel_config["name"],
            gridPos={"x": 0, "y": 0, "w": 0, "h": 0},
            yaxes=[{"min": panel_config["min_y_zero"]}],
            min_y=0 if panel_config["min_y_zero"] else None,
            fill_opacity=50 if panel_config["fill"] else 0,
            draw_style="line",
        )

        for query in panel_config["queries"]:
            # 解析时间对比参数
            time_compare = query["function"].get("time_compare", [])
            if not isinstance(time_compare, list):
                time_compare = [time_compare]
            time_compare = [offset_text for offset_text in time_compare if re.match(r"\d+[mhdwMy]", str(offset_text))]

            # 图表查询配置生成
            query_configs = []
            for query_config in query["query_configs"]:
                if query_config["data_source_label"] == DataSourceLabel.PROMETHEUS:
                    query_configs.append(
                        {
                            "data_source_label": query_config["data_source_label"],
                            "data_type_label": query_config["data_type_label"],
                            "interval": query_config["interval"],
                            "promql": query_config["promql"],
                        }
                    )
                else:
                    query_configs.append(
                        {
                            "alias": "",
                            "data_source_label": query_config["data_source_label"],
                            "data_type_label": query_config["data_type_label"],
                            "display": False,
                            "filter_dict": query_config["filter_dict"],
                            "functions": query_config["functions"],
                            "group_by": query_config["group_by"],
                            "interval": query_config["interval"],
                            "interval_unit": query_config["interval_unit"],
                            "method": query_config["metrics"][0]["method"],
                            "metric_field": query_config["metrics"][0]["field"],
                            "refId": query_config["metrics"][0]["alias"],
                            "result_table_id": query_config["table"],
                            "data_label": query_config.get("data_label", ""),
                            "result_table_label": "",
                            "time_field": query_config.get("time_field", "time"),
                            "where": query_config["where"],
                        }
                    )

            if time_compare and len(query_configs) == 1:
                # 增加时间对比配置
                for offset_text in time_compare:
                    new_query_configs = json.loads(json.dumps(query_configs))
                    for query_config in new_query_configs:
                        query_config["functions"].append(
                            {"id": "time_shift", "params": [{"id": "offset", "value": offset_text}]}
                        )

                    alias = query["alias"].replace("$time_offset", offset_text)
                    cls.add_target(panel, query.get("functions", []), query_configs, alias, query["expression"])
                alias = query["alias"].replace("$time_offset", "current")
            else:
                alias = query["alias"].replace("$time_offset - ", "").replace("$time_offset", "")

            cls.add_target(panel, query.get("functions", []), query_configs, alias, query["expression"])
        return panel

    @classmethod
    def location_generator(cls, dashboard: dict, w: int, h: int) -> Generator[dict, None, None]:
        """
        在仪表盘中搜索大小合适的空位
        """
        assert w <= 24

        panels = dashboard.get("panels", [])

        # 计算最大高度
        max_y = 0
        for panel in panels:
            if max_y < panel["gridPos"]["y"] + panel["gridPos"]["h"]:
                max_y = panel["gridPos"]["y"] + panel["gridPos"]["h"]

            for inner_panel in panel.get("panels", []):
                if max_y < inner_panel["gridPos"]["y"] + inner_panel["gridPos"]["h"]:
                    max_y = inner_panel["gridPos"]["y"] + inner_panel["gridPos"]["h"]

        # 初始化矩阵
        max_y += h + 1
        grid = []
        for i in range(25):
            grid.append([])
            for j in range(max_y):
                grid[i].append([0, (0, 0)])

        # 记录已存在的图表
        for panel in panels:
            location = panel["gridPos"]
            for x in range(location["x"], location["x"] + location["w"] + 1):
                for y in range(location["y"], location["y"] + location["h"] + 1):
                    grid[x][y] = [1, (0, 0)]

        # 搜索大小合适的空位
        for y in range(max_y):
            for x in range(25):
                if grid[x][y][0] == 1:
                    continue

                if x > 0:
                    grid[x][y][1] = max((grid[x - 1][y][1][0] + 1, grid[x - 1][y][1][1]), grid[x][y][1])

                if y > 0:
                    grid[x][y][1] = max((grid[x][y - 1][1][0], grid[x][y - 1][1][1] + 1), grid[x][y][1])

                if grid[x][y][1][0] >= w and grid[x][y][1][1] >= h:
                    # 记录使用的区域
                    for _x in range(x - w + 1, x + 1):
                        for _y in range(y - h + 1, y + 1):
                            grid[_x][_y] = [1, (0, 0)]
                    yield {"x": x - w, "y": y - h, "w": w, "h": h}

        del grid

        while True:
            for x in [0, 12]:
                yield {"x": x, "y": max_y, "w": w, "h": h}

            max_y += h

    @classmethod
    def panel_id_generator(cls, dashboard) -> Generator[int, None, None]:
        index = 1
        for panel in dashboard.get("panels", []):
            if index < panel["id"]:
                index = panel["id"]

        while True:
            index += 1
            yield index

    def perform_request(self, params):
        org_id = get_org_by_name(params["bk_biz_id"])["id"]

        # 获取仪表盘配置
        dashboards = []
        for dashboard_uid in params["dashboard_uids"]:
            result = api.grafana.get_dashboard_by_uid(uid=dashboard_uid, org_id=org_id)
            if result["result"] and result["data"].get("dashboard"):
                dashboard = result["data"]["dashboard"]
                dashboard["folderId"] = result["data"]["meta"]["folderId"]
                dashboards.append(dashboard)

        panels = []
        for panel_config in params["panels"]:
            panels.append(self.get_panel(panel_config).to_dict())

        # 更新仪表盘配置
        for dashboard in dashboards:
            location_generator = self.location_generator(dashboard, 12, 6)
            panel_id_generator = self.panel_id_generator(dashboard)
            dashboard.setdefault("panels", [])
            for panel in panels:
                panel["gridPos"] = next(location_generator)
                panel["id"] = next(panel_id_generator)
                dashboard["panels"].append(panel)

        results = []

        # 更新仪表盘
        for dashboard in dashboards:
            results.append(
                api.grafana.create_or_update_dashboard_by_uid(
                    org_id=org_id, overwrite=True, dashboard=dashboard, folderId=dashboard.pop("folderId")
                )
            )

        return results


class GetGroupByCount(Resource):
    """
    维度聚合数量统计
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        data_source_label = serializers.CharField(label="数据来源")
        data_type_label = serializers.CharField(label="数据类型")

        query_string = serializers.CharField(default="", allow_blank=True)
        index_set_id = serializers.CharField(label="索引集ID", default="", allow_blank=True)
        result_table_id = serializers.CharField(label="结果表ID", default="", allow_blank=True)
        where = serializers.ListField(label="过滤条件", default=lambda: [])
        filter_dict = serializers.DictField(default=lambda: {})

        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    def perform_request(self, params):
        available_params = {"limit": 500}
        available_params.update(**params)

        result = resource.grafana.log_query(available_params)
        log_list = result.get("data", [])
        count_dict = defaultdict(lambda: defaultdict(lambda: 0))
        total = len(log_list)
        for data in log_list:
            for key, value in data.items():
                if key.split(".", -1)[0] == "dimensions":
                    count_dict[key.split(".", -1)[-1]][value] += 1
                    continue
                if key != "time" and key != "event.content":
                    count_dict[key][value] += 1

        count_list = [
            {
                "field": key,
                "total": len(values.items()),
                "dimensions": sorted(
                    [
                        {
                            "value": value,
                            "number": count,
                            "percentage": round(count / total * 100, 2),
                        }
                        for value, count in values.items()
                    ],
                    key=lambda dimension: -dimension["number"],
                ),
            }
            for key, values in count_dict.items()
        ]

        return {"total": total, "count": count_list}
