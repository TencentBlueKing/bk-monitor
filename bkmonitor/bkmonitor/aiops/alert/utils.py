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
import abc
import copy
import json
import logging
import math
import re
from collections import defaultdict
from itertools import chain
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.aiops.utils import AiSetting, ReadOnlyAiSetting
from bkmonitor.dataflow.constant import VisualType
from bkmonitor.documents import AlertDocument
from bkmonitor.models import NO_DATA_TAG_DIMENSION, AlgorithmModel, MetricListCache
from bkmonitor.strategy.new_strategy import parse_metric_id
from bkmonitor.utils.range import load_agg_condition_instance
from constants.alert import CLUSTER_PATTERN
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SPLIT_DIMENSIONS
from core.drf_resource import api
from core.errors.alert import AIOpsFunctionAccessedError, AIOpsResultError
from core.errors.api import BKAPIError
from core.unit import load_unit

logger = logging.getLogger("bkmonitor")


class AIOPSManager(abc.ABC):
    AIOPS_FUNCTION_NOT_ACCESSED_CODE = 1513810
    AVAILABLE_DATA_LABEL = (
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
        (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES),
    )

    def __init__(self, alert: AlertDocument, ai_settings: Optional[ReadOnlyAiSetting] = None):
        self.alert = alert

        if ai_settings:
            self.ai_setting = ai_settings
        else:
            self.ai_setting = AiSetting(bk_biz_id=alert.event["bk_biz_id"])

    @classmethod
    def translate_bk_monitor_log_metric(cls, query_config, **kwargs):
        # 关键字的节点维度需要转换成实际的维度字段
        dimensions = kwargs.get("dimensions", {})
        if "bk_obj_id" in dimensions and "bk_inst_id" in dimensions:
            bk_obj_id = dimensions.pop("bk_obj_id")
            bk_inst_id = dimensions.pop("bk_inst_id")
            dimensions[f"bk_{bk_obj_id}_id"] = str(bk_inst_id)

        query_config["metric_field"] = "event.count"

    @classmethod
    def translate_custom_event_metric(cls, query_config, **kwargs):
        # 关键字的节点维度需要转换成实际的维度字段
        filter_dict = kwargs.get("filter_dict", {})
        filter_dict["event_name"] = query_config["custom_event_name"]
        query_config["metric_field"] = "_index"

    @classmethod
    def translate_bk_monitor_alert_metric(cls, query_config, **kwargs):
        query_config["metric_field"] = query_config["bkmonitor_strategy_id"]
        query_config["result_table_id"] = "alert"

    @classmethod
    def translate_bk_log_search_log_metric(cls, query_config, **kwargs):
        query_config["metric_field"] = "_index"

    @classmethod
    def get_graph_panel(
        cls, alert: AlertDocument, compare_function: Optional[Dict] = None, use_raw_query_config: bool = False
    ):
        """
        获取图表配置
        :param alert: 告警对象
        :param compare_function:
        :param use_raw_query_config: 是否使用原始查询配置（适用于AIOps接入后要获取原始数据源的场景）
        """
        if compare_function is None:
            compare_function = {"time_compare": ["1d", "1w"]}

        if not alert.strategy:
            # 策略为空，则显示告警数量统计
            return {
                "id": "event",
                "type": "bar",
                "title": "异常事件统计",
                "subTitle": alert.alert_name,
                "targets": [
                    {
                        "data": {
                            "expression": "",
                            "query_configs": [
                                {
                                    "data_source_label": DataSourceLabel.BK_FTA,
                                    "data_type_label": DataTypeLabel.ALERT,
                                    "group_by": [],
                                    "table": "alert",
                                    "metrics": [{"field": alert.alert_name, "method": "COUNT"}],
                                    "interval": 60,
                                    "where": [],
                                    "time_field": "time",
                                    "filter_dict": {"dedupe_md5": alert.dedupe_md5},
                                }
                            ],
                            "function": compare_function,
                        },
                        "datasourceId": "time_series",
                        "name": "时序数据",
                        "alias": "$time_offset",
                    }
                ],
            }

        item = alert.strategy["items"][0]
        query_config = item["query_configs"][0]

        if use_raw_query_config:
            raw_query_config = query_config.get("raw_query_config", {})
            query_config.update(raw_query_config)

        unify_query_params = {
            "expression": item.get("expression", ""),
            "functions": item.get("functions", []),
            "query_configs": [],
            "function": compare_function,
        }

        extra_unify_query_params = {
            "expression": item.get("expression", ""),
            "functions": item.get("functions", []),
            "query_configs": [],
            "function": compare_function,
        }

        if (
            query_config["data_source_label"],
            query_config["data_type_label"],
        ) in cls.AVAILABLE_DATA_LABEL:
            for query_config in item["query_configs"]:
                if use_raw_query_config:
                    raw_query_config = query_config.get("raw_query_config", {})
                    query_config.update(raw_query_config)

                dimensions = {}
                dimension_fields = query_config.get("agg_dimension", [])
                try:
                    dimensions = alert.event.extra_info.origin_alarm.data.dimensions.to_dict()
                    dimension_fields = alert.event.extra_info.origin_alarm.data.dimension_fields
                    dimension_fields = [field for field in dimension_fields if not field.startswith("bk_task_index_")]
                except Exception:  # noqa
                    pass

                dimensions = {
                    key: value
                    for key, value in dimensions.items()
                    if key in dimension_fields and not (key == "le" and value is None)
                }
                filter_dict = {}
                translate_method_name = 'translate_{}_{}_metric'.format(
                    query_config["data_source_label"].lower(), query_config["data_type_label"].lower()
                )

                if query_config["data_source_label"] == DataSourceLabel.BK_FTA:
                    query_config["metric_field"] = query_config["alert_name"]
                    query_config["result_table_id"] = "event"
                elif hasattr(cls, translate_method_name):
                    translate_method = getattr(cls, translate_method_name)
                    translate_method(query_config, dimensions=dimensions, filter_dict=filter_dict)

                # promql添加维度过滤特殊处理
                if query_config["data_source_label"] == DataSourceLabel.PROMETHEUS:
                    where = []
                    agg_dimension = []
                    metrics = []
                    filter_dict = dimensions
                else:
                    where = cls.create_where_with_dimensions(query_config["agg_condition"], dimensions)
                    agg_dimension = list(set(query_config["agg_dimension"]) & set(dimensions.keys()))
                    if "le" in query_config["agg_dimension"]:
                        # 针对le做特殊处理
                        agg_dimension.append("le")

                    metrics = [
                        {
                            "field": query_config.get("metric_field", "_index"),
                            "method": query_config.get("agg_method", "COUNT"),
                            "alias": query_config.get("alias", "A"),
                        }
                    ]

                if query_config["data_type_label"] == DataTypeLabel.ALERT:
                    metrics[0]["display"] = True

                # 扩展指标（针对智能异常检测，需要根据敏感度来）
                algorithm_list = item.get("algorithms", [])
                intelligent_algorithm_list = [
                    algorithm
                    for algorithm in algorithm_list
                    if algorithm["level"] == alert.severity and algorithm["type"] in AlgorithmModel.AIOPS_ALGORITHMS
                ]

                intelligent_detect_accessed = bool(query_config.get("intelligent_detect", {}).get("result_table_id"))

                extra_metrics = []
                if not use_raw_query_config and intelligent_algorithm_list and intelligent_detect_accessed:
                    visual_type = intelligent_algorithm_list[0]["config"].get("visual_type")
                    if visual_type != VisualType.FORECASTING:
                        metrics.append(
                            {
                                "field": "is_anomaly",
                                "method": query_config.get("agg_method", "MAX"),
                                "display": True,
                            }
                        )

                    if visual_type == VisualType.BOUNDARY:
                        metrics.extend(
                            [
                                {
                                    "field": "lower_bound",
                                    "method": query_config.get("agg_method", "MIN"),
                                    "display": True,
                                },
                                {
                                    "field": "upper_bound",
                                    "method": query_config.get("agg_method", "MAX"),
                                    "display": True,
                                },
                            ]
                        )
                    elif visual_type == VisualType.SCORE:
                        extra_metrics.append(
                            {"field": "anomaly_score", "method": query_config.get("agg_method", "MAX")}
                        )
                    elif visual_type == VisualType.FORECASTING:
                        extra_metrics.extend(
                            [
                                metrics[0],
                                {"field": "predict", "method": "", "display": True},
                                {"field": "lower_bound", "method": "", "display": True},
                                {"field": "upper_bound", "method": "", "display": True},
                            ]
                        )

                    # 当算法是离群检测时需要做特别的处理
                    if intelligent_algorithm_list[0]["type"] == AlgorithmModel.AlgorithmChoices.AbnormalCluster:
                        metrics = [
                            {"field": "value", "method": "AVG"},
                            {"field": "bounds", "method": "", "display": True},
                        ]

                        extra_metrics = []

                        agg_dimension = ["cluster"]

                        clusters = alert.event.extra_info.origin_alarm.data["values"]["cluster"]
                        pattern = re.compile(CLUSTER_PATTERN)
                        cluster_str_list = pattern.findall(clusters)
                        where.append({"condition": "and", "key": "cluster", "method": "eq", "value": cluster_str_list})

                        for index, condition in enumerate(where.copy()):
                            if condition.get("key") == "is_anomaly":
                                where.pop(index)
                                break

                query_config = {
                    "custom_event_name": query_config.get("custom_event_name", ""),
                    "query_string": query_config.get("query_string", ""),
                    "index_set_id": query_config.get("index_set_id", 0),
                    "bk_biz_id": alert.event.bk_biz_id,
                    "data_source_label": query_config["data_source_label"],
                    "data_type_label": query_config["data_type_label"],
                    "group_by": agg_dimension,
                    "table": query_config.get("result_table_id", ""),
                    "data_label": query_config.get("data_label", ""),
                    "promql": query_config.get("promql", ""),
                    "metrics": metrics,
                    "interval": query_config.get("agg_interval", 60),
                    "where": where,
                    "time_field": query_config.get("time_field"),
                    "extend_fields": query_config.get("extend_fields", {}),
                    "filter_dict": filter_dict,
                    "functions": query_config.get("functions", []),
                }

                unify_query_params["query_configs"].append(query_config)

                if extra_metrics:
                    extra_query_config = copy.deepcopy(query_config)
                    extra_query_config["metrics"] = extra_metrics
                    extra_unify_query_params["query_configs"].append(extra_query_config)

        if not unify_query_params["query_configs"]:
            return

        data_source_label = unify_query_params["query_configs"][0]["data_source_label"]
        data_type_label = unify_query_params["query_configs"][0]["data_type_label"]
        is_bar = (data_source_label, data_type_label) in (
            (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
            (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),
            (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
            (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
            (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        )

        is_composite = data_type_label == DataTypeLabel.ALERT

        sub_titles = "\n".join([query_config["metric_id"] for query_config in item["query_configs"]])

        panel = {
            "id": "event",
            "type": "bar" if is_bar else "graph",
            "title": item.get("name") or item.get("expression", ""),
            "subTitle": sub_titles,
            "targets": [
                {
                    "data": unify_query_params,
                    "datasourceId": "time_series",
                    "name": "时序数据",
                    "alias": "$metric_field-$time_offset" if is_composite else "$time_offset",
                }
            ],
        }

        if extra_unify_query_params["query_configs"]:
            panel["targets"].append(
                {
                    "data": extra_unify_query_params,
                    "datasourceId": "time_series",
                    "name": _("时序数据"),
                    "alias": "$time_offset",
                }
            )

        return panel

    @classmethod
    def create_where_with_dimensions(cls, where: list, dimensions: dict):
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

    @abc.abstractmethod
    def fetch_aiops_result(self):
        raise NotImplementedError

    @abc.abstractmethod
    def is_enable(self):
        raise NotImplementedError


class DimensionDrillManager(AIOPSManager):
    def parse_serving_result(
        self, metric: MetricListCache, serving_output: Dict
    ) -> Tuple[Dict, List[Dict], List[Dict]]:
        """解析维度下钻算法的预测结果.

        :param metric: 告警指标详情
        :param serving_output: 预测输出
        """
        graph_dimensions = json.loads(serving_output["root_leaves"])

        root_dimensions = json.loads(serving_output["root_dims"])
        info = {
            "anomaly_dimension_count": len(root_dimensions),
            "anomaly_dimension_value_count": sum(map(lambda x: x["root_cnt"], root_dimensions)),
        }

        # 维度中文名映射
        dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}

        anomaly_dimensions = []
        for root_dimension in root_dimensions:
            sorted_dimension = sorted(root_dimension["dim_combine"])
            anomaly_dimensions.append(
                {
                    "anomaly_dimension": sorted_dimension,
                    "anomaly_dimension_alias": "|".join(map(lambda x: dim_mappings[x], sorted_dimension)),
                    "anomaly_dimension_class": "&".join(sorted_dimension),
                    "dimension_anomaly_value_count": root_dimension["root_cnt"],
                    "dimension_value_total_count": root_dimension["total_cnt"],
                    "dimension_value_percent": (
                        round(root_dimension["root_cnt"] * 100 / root_dimension["total_cnt"], 2)
                        if root_dimension["total_cnt"]
                        else 0
                    ),
                    "anomaly_score_top10": self.generate_anomaly_score_top10(root_dimension),
                    "anomaly_score_distribution": self.generate_anomaly_score_distribution(metric, root_dimension),
                    "dim_surprise": root_dimension["dim_surprise"],
                }
            )

        return info, anomaly_dimensions, graph_dimensions

    @classmethod
    def generate_anomaly_graph_panels(
        cls, alert: AlertDocument, metric: MetricListCache, graph_panel: Dict, graph_dimensions: List[Dict]
    ) -> List[Dict]:
        """生成异常分值较高的维度图表参数.

        :param alert: 告警信息
        :param metric: 指标详情，用来补充中文维度信息
        :param graph_panel: 原始告警图表参数
        :param graph_dimensions: 异常分值较高的维度组合
            [
                {
                    "root": {
                        "bk_target_ip": "127.0.0.1",
                    },
                    "surprise": 0.013142875563731185,
                    "score": 0.07142857142857142,
                    "dim_surprise": 15.814226534141184
                },
                {
                    "root": {
                        "bk_target_ip": "127.0.0.1",
                    },
                    "surprise": 0.0016981856483826371,
                    "score": 0.07142857142857142,
                    "dim_surprise": 15.814226534141184
                }
            ]
        :return: 以graph_panel作为模板，基于维度下钻结果构建的panels配置列表
        """
        graph_panels = []

        # 维度中文名映射
        dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}

        for dimension in graph_dimensions:
            base_graph_panel = copy.deepcopy(graph_panel)
            base_graph_panel["id"] = cls.generate_id_by_dimension_dict(dimension["root"])
            base_graph_panel["type"] = "aiops-dimension-lint"
            base_graph_panel["subTitle"] = " "
            base_graph_panel["anomaly_score"] = round(float(dimension["score"]), 2)
            base_graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
            base_graph_panel["targets"][0]["alias"] = ""
            base_graph_panel["targets"][0]["data"]["id"] = alert.id
            base_graph_panel["targets"][0]["data"]["function"] = {}

            # 因为告警维度已经确认，所以这里查询需要清空原始维度聚合配置
            query_configs = base_graph_panel["targets"][0]["data"]["query_configs"]
            for query_config in query_configs:
                query_config["group_by"] = []
                query_config["functions"] = [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}]

            # 补充维度下钻的维度过滤条件
            dimension_keys = sorted(dimension["root"].keys())
            base_graph_panel["title"] = "_".join(
                map(lambda x: f"{dim_mappings.get(x, x)}: {dimension['root'][x]}", dimension_keys)
            )
            base_graph_panel["anomaly_dimension_class"] = "&".join(dimension_keys)
            for condition_key in dimension_keys:
                condition_value = dimension["root"][condition_key]
                condition = {"key": condition_key, "value": [condition_value], "method": "eq", "condition": "and"}
                for query_config in query_configs:
                    query_config["group_by"].append(condition_key)
                    query_config["where"].append(condition)

            graph_panels.append(base_graph_panel)

        return sorted(graph_panels, key=lambda x: -x["anomaly_score"])

    @classmethod
    def generate_anomaly_score_top10(cls, root_dimension: Dict) -> List[Dict]:
        """根据API Serving的异常维度信息构建异常分值Top10的维度组合列表.
        :param root_dimension: 异常维度信息
            {
                "dim_combine": ["bk_target_ip"],     # 异常维度列表
                "total_cnt": 2476,                   # 维度组合总数
                "root_cnt": 10,                      # 异常维度组合总数
                "dim_surprise": 15.814226534141184,  # JS散度
                "anomaly_data": [                    # 异常分值超过阈值的维度组合
                    [
                        ("127.0.0.1"),               # 跟dim_combine一一对应的维度值
                        "0.0",                       # 指标值
                        "0.07"                       # 异常分值
                    ]
                ],
                "normal_data": [                     # 异常分值不超过阈值的维度组合
                    [
                        ("127.0.0.2"),
                        "0.0",
                        "0.06"
                    ]
                ]
            }
        :return: 异常分值前10的维度组合列表，如果存在并列的异常分值且全取会超过10，则随机选择补充列表至10即可
            [
                {
                    "id": "bk_target_ip=127.0.0.1",
                    "dimension_value": "127.0.0.1",
                    "anomaly_score": 0.07,
                    "is_anomaly": true
                },
                {
                    "id": "bk_target_ip=127.0.0.2",
                    "dimension_value": "127.0.0.2",
                    "anomaly_score": 0.06,
                    "is_anomaly": false
                }
            ]
        """
        # 基于异常分值倒序排序
        anomaly_data = sorted(root_dimension["anomaly_data"], key=lambda x: -float(x[2]))
        top10_data = anomaly_data[:10]

        return [
            {
                **cls.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item),
                "is_anomaly": True,
            }
            for item in top10_data
        ]

    @classmethod
    def generate_anomaly_score_distribution(cls, metric: MetricListCache, root_dimension: Dict) -> Dict:
        """根据API Serving的异常维度信息构建异常维度分布.

        :param alert: 告警详情
        :param root_dimension: 异常维度信息
            {
                "dim_combine": ["bk_target_ip"],     # 异常维度列表
                "total_cnt": 2476,                   # 维度组合总数
                "root_cnt": 10,                      # 异常维度组合总数
                "dim_surprise": 15.814226534141184,  # JS散度
                "anomaly_data": [                    # 异常分值超过阈值的维度组合
                    [
                        ("127.0.0.1"),               # 跟dim_combine一一对应的维度值
                        "0.0",                       # 指标值
                        "0.07"                       # 异常分值
                    ]
                ],
                "normal_data": [                     # 异常分值不超过阈值的维度组合
                    [
                        ["127.0.0.2"],
                        "0.0",
                        "0.06"
                    ]
                ]
            }
        :return: 异常维度分布，异常分值按照四舍五入的方式放入以0.1为间隔的0-1的箱子中
            {
                "metric_alias": "CPU使用率",
                "unit": "%",
                "median": 0.5,
                "data": [
                    {
                        "anomaly_score": 1.0,
                        "dimension_details": [
                            {
                                "id": "bk_target_cluster=集群4",
                                "dimension_value": "集群4",
                                "metric_value": 80,
                                "anomaly_score": 1.0
                            }
                        ]
                    },
                    {
                        "anomaly_score": 0.9,
                        "dimension_details": [
                            {
                                "id": "bk_target_cluster=集群5",
                                "dimension_value": "集群5",
                                "metric_value": 80,
                                "anomaly_score": 0.88
                            },
                            {
                                "id": "bk_target_cluster=集群6",
                                "dimension_value": "集群6",
                                "metric_value": 80,
                                "anomaly_score": 0.91
                            }
                        ]
                    }
                ]
            }
        """

        distribution_data = defaultdict(lambda: {"is_anomaly": False, "details": []})
        score_data = []
        # 处理异常数据
        for item in root_dimension["anomaly_data"]:
            anomaly_score = round(float(item[2]), 1)
            score_data.append(float(item[2]))
            distribution_data[anomaly_score]["is_anomaly"] = True
            distribution_data[anomaly_score]["details"].append(
                {**cls.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item), "is_anomaly": True}
            )

        # 处理正常数据
        for item in root_dimension["normal_data"]:
            dimension_score = max(float(item[2]), 0)  # 如果异常分值小于0，说明维度是正常的，则取0来作展示
            anomaly_score = round(dimension_score, 1)
            score_data.append(dimension_score)
            distribution_data[anomaly_score]["details"].append(
                {**cls.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item), "is_anomaly": False}
            )

        for anomaly_data in distribution_data.values():
            anomaly_data["details"] = sorted(anomaly_data["details"], key=lambda x: -x["anomaly_score"])

        # 获取score_data的中位数
        if not score_data:
            score_data_median = 0
        elif len(score_data) % 2 == 0:
            score_data_median = (
                sorted(score_data)[len(score_data) // 2] + sorted(score_data)[len(score_data) // 2 - 1]
            ) / 2
        else:
            score_data_median = sorted(score_data)[len(score_data) // 2]

        return {
            "metric_alias": metric.metric_field_name,
            "unit": metric.unit,
            "median": round(score_data_median, 2),
            "data": sorted(
                [
                    {
                        "anomaly_score": round(anomaly_score, 2),
                        "is_anomaly": distribution_item["is_anomaly"],
                        "dimension_details": distribution_item["details"],
                    }
                    for anomaly_score, distribution_item in distribution_data.items()
                ],
                key=lambda item: -item["anomaly_score"],
            ),
        }

    @classmethod
    def generate_id_by_dimension_dict(cls, dimensions: Dict) -> str:
        """根据维度字典生成某个维度组合的唯一ID.

        :param dimensions: 维度字典
        :return: 类似querystring的结构, 如: dim_key1-dim_value1&dim_key2-dim_value2
        """
        keys = sorted(list(dimensions.keys()))
        return "&".join(f"{key}-{dimensions[key]}" for key in keys)

    @classmethod
    def generate_anomaly_dimension_detail(cls, dimension_keys: List, dimension_data: List) -> Dict:
        """根据异常维度数据生成维度详情.

        :param dimension_keys: 维度列表
        :param dimension_data: 异常维度数据
        """
        return {
            "id": cls.generate_id_by_dimension_dict(dict(zip(dimension_keys, dimension_data[0]))),
            "dimension_value": "|".join(dimension_data[0]),
            "metric_value": float(dimension_data[1]) if not math.isnan(float(dimension_data[1])) else "NaN",
            "anomaly_score": max(round(float(dimension_data[2]), 2), 0),  # 如果异常分值小于0，说明维度是正常的，则取0来作展示
        }

    def is_enable(self):
        return self.ai_setting.dimension_drill.is_enabled

    def generate_predict_args(self, metric: MetricListCache, query_configs: List[dict]) -> Dict:
        """基于告警信息构建维度下钻API Serving的预测参数
        :param metric: 告警指标详情
        :param query_configs: 告警指标默认查询参数
        :return:
        """
        for query_config in query_configs:
            group_bys = []
            src_group_bys = query_config["group_by"]

            for dimension in metric.dimensions:
                # 如果某个维度在过滤条件里，则不对该维度进行下钻
                if dimension.get("is_dimension", True) and dimension["id"] not in chain(
                    src_group_bys, SPLIT_DIMENSIONS
                ):
                    group_bys.append(dimension["id"])

            query_config["group_by"] = group_bys

        return {
            "json_args": json.dumps(
                {
                    "expression": "a",
                    "query_configs": query_configs,
                    "target_time": self.alert.latest_time * 1000,
                    "bk_biz_id": self.alert.event["bk_biz_id"],
                    "alert_id": self.alert.id,
                }
            ),
        }

    def get_serving_output(self, metric: MetricListCache, graph_panel: Dict):

        processing_id = settings.BK_DATA_DIMENSION_DRILL_PROCESSING_ID
        query_configs = copy.deepcopy(graph_panel["targets"][0]["data"]["query_configs"])

        try:
            response = api.bkdata.api_serving_execute(
                timeout=30,
                processing_id=processing_id,
                data={"inputs": [{"timestamp": self.alert.latest_time * 1000}]},
                config={"predict_args": self.generate_predict_args(metric, query_configs)},
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": _("算法无输出")})
        except BKAPIError as e:
            logger.exception(f"failed to call aiops api serving({processing_id}): {e}")

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": _("维度下钻")})
            else:
                raise AIOpsResultError({"err": str(e)})

        return response["data"]["data"][0]["output"][0]

    def fetch_aiops_result(self):

        if not self.is_enable():
            # raise AIOpsDisableError({"func": _("维度下钻")})
            raise AIOpsFunctionAccessedError({"func": _("维度下钻")})

        graph_panel = AIOPSManager.get_graph_panel(self.alert, use_raw_query_config=True)
        # 获取当前告警的指标详情
        metric_info = parse_metric_id(self.alert.event["metric"][0])
        metric = MetricListCache.objects.filter(**metric_info).first()

        serving_output = self.get_serving_output(metric, graph_panel)

        return self.format_result(metric, serving_output, graph_panel)

    def format_result(self, metric: MetricListCache, serving_output: Dict, graph_panel: Dict):
        info, anomaly_dimensions, graph_dimensions = self.parse_serving_result(metric, serving_output)
        graph_panels = self.generate_anomaly_graph_panels(self.alert, metric, graph_panel, graph_dimensions)

        return {
            "info": info,
            "anomaly_dimensions": anomaly_dimensions,
            "graph_panels": graph_panels,
            "alert_latest_time": self.alert.latest_time,
        }


class RecommendMetricManager(AIOPSManager):
    def is_enable(self):
        return self.ai_setting.metric_recommend.is_enabled

    def generate_predict_args(self, exp_config: Dict) -> Dict:
        """
        基于告警信息构建指标推荐PI Serving的预测参数.
        :param exp_config: 查询表达式配置
        """
        # 查询该业务是否配置有ai设置
        metric_recommend = self.ai_setting.metric_recommend

        return {
            "json_args": json.dumps(
                {
                    "expression": exp_config["expression"],
                    "query_configs": exp_config["query_configs"],
                    "start_time": self.alert.begin_time,
                    "end_time": self.alert.latest_time,
                    "bk_biz_id": self.alert.event["bk_biz_id"],
                    "alert_id": self.alert.id,
                }
            ),
            "reference_table": metric_recommend.result_table_id
            or (
                f"{settings.DEFAULT_BKDATA_BIZ_ID}_"
                f"{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}_"
                f"{self.alert.event['bk_biz_id']}"
            ),
        }

    def fetch_aiops_result(self):
        # 告警指标大于1或者没有告警指标时，则不进行推荐
        if len(self.alert.event["metric"]) != 1:
            return {}

        if not self.is_enable():
            # raise AIOpsDisableError({"func": _("指标推荐")})
            raise AIOpsFunctionAccessedError({"func": _("指标推荐")})

        graph_panel = self.get_graph_panel(self.alert, use_raw_query_config=True)
        processing_id = f'{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}'
        try:
            response = api.bkdata.api_serving_execute(
                timeout=30,
                processing_id=processing_id,
                data={"inputs": [{"timestamp": self.alert.first_anomaly_time * 1000}]},
                config={"predict_args": self.generate_predict_args(copy.deepcopy(graph_panel['targets'][0]['data']))},
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": _("算法无输出")})
        except BKAPIError as e:
            logger.exception(f'failed to call aiops api serving({processing_id}): {e}')

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": _("指标推荐")})
            else:
                raise AIOpsResultError({"err": str(e)})

        recommended_results = response["data"]["data"][0]["output"][0]
        recommended_metric_panels = self.generate_recommended_metric_panels(
            self.alert, graph_panel, recommended_results
        )
        recommended_metrics = self.classify_recommended_metrics(recommended_metric_panels)

        return {
            "info": {
                # 每个panel对应单推荐指标的某个单维度值，因此推荐指标维度数可基于panel来计算，其中主机类指标只有ip单维度。
                "recommended_metric_count": len(recommended_metric_panels),
            },
            "recommended_metrics": recommended_metrics,
        }

    @classmethod
    def generate_recommended_metric_panels(
        cls, alert: AlertDocument, graph_panel: Dict, recommended_results: Dict
    ) -> List[Dict]:
        """
        生成推荐指标的图表配置
        :param alert: 告警信息
        :param graph_panel: 原始告警图表参数
        :param recommended_results: 推荐结果
            {
                "timestamp": 1669003786760,
                "__index__": "",
                "__group_id__": "",
                "__id__": "",
                "target_metric": "bcs_eternal_metrics.mean_rate",
                "recommend_metrics": "[[\"bcs_eternal_metrics.count\", 0.342319397206, \"None\", [\"\\形\\状\\相\\似\"]]]",
                "metric_exist": 1,
                "extra_info":"{\"detail\": \"\\目\\标\\指\\标\\找\\到1\\相\\似\\指\\标\", \"reason\": [\"\\形\\状\\相\\似\"]}"
            }
        :return: 以graph_panel作为模板，基于指标推荐结果构建的panels配置列表
        """
        graph_panels = []

        recommend_metrics = json.loads(recommended_results["recommend_metrics"])

        for recommend_metric in recommend_metrics:
            base_graph_panel = copy.deepcopy(graph_panel)

            # 获取当前推荐指标的详情
            metric_name, dimensions = cls.parse_recommend_metric(recommend_metric[0])
            metric_info = parse_metric_id(metric_name)
            if not metric_info:
                continue
            metric = MetricListCache.objects.filter(**metric_info).first()
            if not metric:
                continue

            recommend_info = {
                "reasons": recommend_metric[3],
                "class": recommend_metric[2],
                "src_metric_id": alert.event["metric"][0],
                "anomaly_points": recommend_metric[4] if isinstance(recommend_metric[4], list) else [],
            }

            # 维度中文名映射
            dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}
            dimension_keys = sorted(dimensions.keys())

            base_graph_panel["id"] = recommend_metric[0]
            base_graph_panel["type"] = "aiops-dimension-lint"
            base_graph_panel["enable_threshold"] = False
            base_graph_panel["title"] = "_".join(
                map(lambda x: f"{dim_mappings.get(x, x)}: {dimensions[x]}", dimension_keys)
            )
            base_graph_panel["subTitle"] = metric_name
            base_graph_panel["bk_biz_id"] = alert.event.bk_biz_id
            base_graph_panel["recommend_info"] = recommend_info
            base_graph_panel["result_table_label"] = metric.result_table_label
            base_graph_panel["result_table_label_name"] = metric.result_table_label_name
            base_graph_panel["metric_name_alias"] = metric.metric_field_name

            base_graph_panel["targets"][0]["data"]["function"] = {}
            base_graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
            base_graph_panel["targets"][0]["alias"] = ""
            base_graph_panel["targets"][0]["data"]["id"] = alert.id

            # 补充维度过滤条件
            where = []
            dimension_keys = sorted(dimensions.keys())
            for condition_key in dimension_keys:
                condition_value = dimensions[condition_key]
                condition = {
                    "key": condition_key,
                    "value": [condition_value] if not isinstance(condition_value, list) else condition_value,
                    "method": "eq",
                }
                if len(where) > 0:
                    condition["condition"] = "and"
                where.append(condition)

            # 因为推荐指标不一定具有告警相同的维度，因此这里不对维度进行任何聚合，只做指标的推荐
            query_configs = base_graph_panel["targets"][0]["data"]["query_configs"]
            for query_config in query_configs:
                query_config["group_by"] = []
                query_config["where"] = where
                query_config["data_source_label"] = metric.data_source_label
                query_config["data_type_label"] = metric.data_type_label
                query_config["table"] = metric.result_table_id
                query_config["functions"] = [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}]
                for query_metric in query_config["metrics"]:
                    query_metric["field"] = metric.metric_field

            graph_panels.append(base_graph_panel)

        return graph_panels

    @classmethod
    def parse_recommend_metric(cls, recommend_metric: str) -> Tuple[str, Dict]:
        """解析推荐的指标及其维度信息.

        :param recommend_metric: 推荐的指标
        """
        metric_tokens = recommend_metric.split('|')
        if len(metric_tokens) <= 1:
            return metric_tokens[0], {}

        dimensions = {key: value[0] for key, value in parse_qs(metric_tokens[1]).items()}

        return metric_tokens[0], dimensions

    @classmethod
    def classify_recommended_metrics(cls, recommended_metric_panels: List[Dict]) -> List[Dict]:
        """把推荐指标进行分类.

        :param recommended_metric_panels: 未分类的推荐指标列表，包含画图的panels信息
        """
        recommended_metrics = {}

        for metric_panel in recommended_metric_panels:
            if metric_panel["result_table_label"] not in recommended_metrics:
                recommended_metrics[metric_panel["result_table_label"]] = {
                    "result_table_label": metric_panel["result_table_label"],
                    "result_table_label_name": metric_panel["result_table_label_name"],
                    "metrics": {},
                }

            if metric_panel["subTitle"] not in recommended_metrics[metric_panel["result_table_label"]]["metrics"]:
                recommended_metrics[metric_panel["result_table_label"]]["metrics"][metric_panel["subTitle"]] = {
                    "metric_name": metric_panel["subTitle"],
                    "metric_name_alias": metric_panel["metric_name_alias"],
                    "panels": [],
                }

            recommended_metrics[metric_panel["result_table_label"]]["metrics"][metric_panel["subTitle"]][
                "panels"
            ].append(metric_panel)

        for label_metrics in recommended_metrics.values():
            label_metrics["metrics"] = list(label_metrics["metrics"].values())
        recommended_metrics = list(recommended_metrics.values())

        return recommended_metrics


class DimensionDrillLightManager(DimensionDrillManager):
    def format_result(self, metric: MetricListCache, serving_output: Dict, graph_panel: Dict):
        root_dimensions = json.loads(serving_output["root_dims"])
        return {
            "info": {
                "anomaly_dimension_count": len(root_dimensions),
                "anomaly_dimension_value_count": sum(map(lambda x: x["root_cnt"], root_dimensions)),
            }
        }


def parse_anomaly(anomaly_str, config):
    """
    解析异常数据，数据源格式：
    [[指标名, 数值, 异常得分]]
    [["system__net__speed_recv", 2812154.0, 0.979932],...]
    """

    def setup_metric_info(_metric_name):
        return {"name": _metric_name, "metric_id": _metric_name, "unit": ""}

    anomalies = json.loads(anomaly_str)
    # 策略配置信息转字典
    metric_map = {m["metric_name"]: m for m in config["metrics"]} if config and "metrics" in config else {}
    result = []
    # 获取指标中文名称
    for item in anomalies:
        metric_name = item[0].replace("__", ".")
        metric_info = metric_map[metric_name] if metric_name in metric_map else setup_metric_info(metric_name)
        # 转为标准metric_id
        item[0] = metric_info["metric_id"]
        # 异常得分只保留标准小数位
        item[2] = round(item[2], settings.POINT_PRECISION)
        # 数据单位转化
        unit = load_unit(metric_info["unit"])
        value, suffix = unit.fn.auto_convert(item[1], decimal=settings.POINT_PRECISION)
        item.append(f"{value}{suffix}")
        # 添加指标名
        item.append(metric_info["name"])
        """
        转化后格式：
        [[指标名, 数值, 异常得分, 带单位的数值, 指标中文名]]
        [["bk_monitor.system.net.speed_recv", 2812154.0, 0.9799, "2812154.0Kbs", "网卡入流量"],...]
        """
        result.append(item)
    return result
