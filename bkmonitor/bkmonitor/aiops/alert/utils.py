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
import copy
import json
import logging
from itertools import chain
from typing import Dict, List, Tuple
from urllib.parse import parse_qs

from django.conf import settings

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.documents import AlertDocument
from bkmonitor.models import NO_DATA_TAG_DIMENSION, MetricListCache
from bkmonitor.strategy.new_strategy import parse_metric_id
from bkmonitor.utils.range import load_agg_condition_instance
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SPLIT_DIMENSIONS
from core.drf_resource import api
from core.errors.alert import AIOpsFunctionAccessedError, AIOpsResultError
from core.errors.api import BKAPIError
from core.unit import load_unit

logger = logging.getLogger("bkmonitor")


class AIOPSManager(object):
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
    def get_graph_panel(cls, alert: AlertDocument):
        """
        获取图表配置
        :param alert: 告警对象
        """
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

        raw_query_config = query_config.get("raw_query_config", {})
        query_config.update(raw_query_config)

        unify_query_params = {
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
                raw_query_config = query_config.get("raw_query_config", {})
                query_config.update(raw_query_config)

                dimensions = {}
                dimension_fields = query_config.get("agg_dimension", [])
                try:
                    dimensions = alert.event.extra_info.origin_alarm.data.dimensions.to_dict()
                    dimension_fields = alert.event.extra_info.origin_alarm.data.dimension_fields
                    dimension_fields = [field for field in dimension_fields if not field.startswith("bk_task_index_")]
                except Exception:  # NOCC:broad-except(设计如此:)
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


class DimensionDrillManager(AIOPSManager):
    def generate_predict_args(self, alert: AlertDocument, metric: MetricListCache, query_configs: List[dict]) -> Dict:
        """基于告警信息构建维度下钻API Serving的预测参数.

        :param alert: 告警信息
        :parma metric: 告警指标详情
        :param query_configs: 告警指标默认查询参数
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
                    "target_time": alert.latest_time * 1000,
                    "bk_biz_id": alert.event["bk_biz_id"],
                    "alert_id": alert.id,
                }
            ),
        }

    def fetch_aiops_result(self, alert):
        graph_panel = self.get_graph_panel(alert)
        query_configs = copy.deepcopy(graph_panel["targets"][0]["data"]["query_configs"])
        metric_info = parse_metric_id(alert.event["metric"][0])
        metric = MetricListCache.objects.filter(**metric_info).first()

        processing_id = settings.BK_DATA_DIMENSION_DRILL_PROCESSING_ID
        try:
            response = api.bkdata.api_serving_execute(
                timeout=30,
                processing_id=processing_id,
                data={
                    "inputs": [
                        {
                            "timestamp": alert.latest_time * 1000,
                        }
                    ]
                },
                config={"predict_args": self.generate_predict_args(alert, metric, query_configs)},
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": "算法无输出"})
        except BKAPIError as e:
            logger.exception(f"failed to call aiops api serving({processing_id}): {e}")

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": "维度下钻"})
            else:
                raise AIOpsResultError({"err": str(e)})
        serving_output = response["data"]["data"][0]["output"][0]
        root_dimensions = json.loads(serving_output["root_dims"])
        return {
            "info": {
                "anomaly_dimension_count": len(root_dimensions),
                "anomaly_dimension_value_count": sum(map(lambda x: x["root_cnt"], root_dimensions)),
            }
        }


class RecommendMetricManager(AIOPSManager):
    def generate_predict_args(self, alert: AlertDocument, exp_config: Dict) -> Dict:
        """基于告警信息构建指标推荐PI Serving的预测参数.

        :param alert: 告警信息
        :param exp_config: 查询表达式配置
        """
        # 查询该业务是否配置有ai设置
        ai_setting = AiSetting(bk_biz_id=alert.event["bk_biz_id"])
        metric_recommend = ai_setting.metric_recommend

        return {
            "json_args": json.dumps(
                {
                    "expression": exp_config["expression"],
                    "query_configs": exp_config["query_configs"],
                    "start_time": alert.begin_time,
                    "end_time": alert.latest_time,
                    "bk_biz_id": alert.event["bk_biz_id"],
                    "alert_id": alert.id,
                }
            ),
            "reference_table": metric_recommend.result_table_id
            or (
                f"{settings.DEFAULT_BKDATA_BIZ_ID}_"
                f"{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}_"
                f"{alert.event['bk_biz_id']}"
            ),
        }

    def fetch_aiops_result(self, alert):
        graph_panel = self.get_graph_panel(alert)
        # 告警指标大于1或者没有告警指标时，则不进行推荐
        if len(alert.event["metric"]) != 1:
            return {}

        processing_id = f'{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}'
        try:
            response = api.bkdata.api_serving_execute(
                timeout=30,
                processing_id=processing_id,
                data={
                    "inputs": [
                        {
                            "timestamp": alert.first_anomaly_time * 1000,
                        }
                    ]
                },
                config={
                    "predict_args": self.generate_predict_args(alert, copy.deepcopy(graph_panel['targets'][0]['data']))
                },
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": "算法无输出"})
        except BKAPIError as e:
            logger.exception(f'failed to call aiops api serving({processing_id}): {e}')

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": "指标推荐"})
            else:
                raise AIOpsResultError({"err": str(e)})

        recommended_results = response["data"]["data"][0]["output"][0]
        recommended_metric_panels = self.generate_recommended_metric_panels(alert, graph_panel, recommended_results)
        recommended_metrics = self.classify_recommended_metrics(recommended_metric_panels)

        return {
            "info": {
                # 每个panel对应单推荐指标的某个单维度值，因此推荐指标维度数可基于panel来计算，其中主机类指标只有ip单维度。
                "recommended_metric_count": len(recommended_metric_panels),
            },
            "recommended_metrics": recommended_metrics,
        }

    def generate_recommended_metric_panels(
        self, alert: AlertDocument, graph_panel: Dict, recommended_results: Dict
    ) -> List[Dict]:
        """生成推荐指标的图表配置.

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
            metric_name, dimensions = self.parse_recommend_metric(recommend_metric[0])
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

    def parse_recommend_metric(self, recommend_metric: str) -> Tuple[str, Dict]:
        """解析推荐的指标及其维度信息.

        :param recommend_metric: 推荐的指标
        """
        metric_tokens = recommend_metric.split('|')
        if len(metric_tokens) <= 1:
            return metric_tokens[0], {}

        dimensions = {key: value[0] for key, value in parse_qs(metric_tokens[1]).items()}

        return metric_tokens[0], dimensions

    def classify_recommended_metrics(self, recommended_metric_panels: List[Dict]) -> List[Dict]:
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


def parse_anomaly(anomaly_str, config):
    """
    解析异常数据，数据源格式：
    [[指标名, 数值, 异常得分]]
    [["system__net__speed_recv", 2812154.0, 0.979932],...]
    """

    def setup_metric_info(metric_name):
        return {"name": metric_name, "metric_id": metric_name, "unit": ""}

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
