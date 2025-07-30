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
import re
from collections import defaultdict
from dataclasses import asdict
from functools import reduce
from itertools import chain
from typing import Any
from collections.abc import Callable
from re import Pattern

import arrow
from django.conf import settings
from django.db.models import Q
from django.forms import model_to_dict
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import (
    FunctionCategories,
    Functions,
    GrafanaFunctions,
    PrometheusTimeSeriesDataSource,
    get_auto_interval,
    load_data_source,
)
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.models import BCSCluster, MetricListCache
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.strategy.new_strategy import get_metric_id
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.time_tools import (
    hms_string,
    parse_time_compare_abbreviation,
    time_interval_align,
)
from constants.data_source import (
    GRAPH_MAX_SLIMIT,
    DataSourceLabel,
    DataTypeLabel,
    UnifyQueryDataSources,
)
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID, UPTIMECHECK_ERROR_CODE_MAP
from core.drf_resource import Resource, api, resource
from core.errors.api import BKAPIError
from core.prometheus.base import OPERATION_REGISTRY
from core.prometheus.metrics import safe_push_to_gateway
from monitor_web.grafana.utils import get_cookies_filter, remove_all_conditions
from monitor_web.statistics.v2.query import unify_query_count
from monitor_web.strategies.constant import CORE_FILE_SIGNAL_LIST

logger = logging.getLogger(__name__)


class TimeCompareProcessor:
    """
    时间对比
    """

    @classmethod
    def process_origin_data(cls, params: dict, data: list) -> list:
        time_compare = params["function"].get("time_compare", [])

        # 兼容单个和多个时间对比
        if not isinstance(time_compare, list):
            time_compare = [time_compare]
        time_compare = set(time_compare)

        for offset_text in time_compare:
            time_offset = parse_time_compare_abbreviation(offset_text)

            if not time_offset:
                continue

            # 查询时间对比数据
            new_params = {}
            new_params.update(params)
            new_params.update(
                {
                    "start_time": new_params["start_time"] * 1000 + time_offset * 1000,
                    "end_time": new_params["end_time"] * 1000 + time_offset * 1000,
                }
            )

            data_sources = []
            for query_config in new_params["query_configs"]:
                data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
                data_sources.append(data_source_class(bk_biz_id=params["bk_biz_id"], **query_config))

            query = UnifyQuery(
                bk_biz_id=params["bk_biz_id"],
                data_sources=data_sources,
                expression=params["expression"],
                functions=params["functions"],
            )
            extra_data = query.query_data(
                start_time=new_params["start_time"],
                end_time=new_params["end_time"],
                limit=new_params["limit"],
                slimit=new_params["slimit"],
                down_sample_range=params["down_sample_range"],
            )

            # 标记时间对比数据
            for record in extra_data:
                record["__time_compare"] = str(offset_text)

            data.extend(extra_data)
        return data

    @classmethod
    def process_formatted_data(cls, params: dict, data: list) -> list:
        time_compare = params["function"].get("time_compare", [])

        # 兼容单个时间对比配置
        if not isinstance(time_compare, list):
            time_compare = [time_compare]
        time_compare = [offset_text for offset_text in time_compare if re.match(r"\d+[mhdwMy]", str(offset_text))]

        # 如果存在对比配置，哪怕为空，也需要补全time_offset维度
        if not time_compare:
            if "time_compare" in params["function"]:
                for record in data:
                    record["time_offset"] = "current"
            return data

        for offset_text in time_compare:
            time_offset: int = parse_time_compare_abbreviation(offset_text)
            if not time_offset:
                continue

            for record in data:
                if not record["dimensions"].get("__time_compare"):
                    if not record.get("time_offset"):
                        record["time_offset"] = "current"
                        record["target"] = f"current-{record['target']}"
                    continue

                if record["dimensions"]["__time_compare"] != offset_text:
                    continue

                # 调整数据描述
                record["target"] = (
                    record["target"]
                    .replace(f"__time_compare={offset_text}, ", "")
                    .replace(f"__time_compare={offset_text}", "")
                )
                record["target"] = f"{offset_text}-{record['target']}"

                # 调整时间对比数据时间
                record["time_offset"] = str(offset_text)
                for point in record["datapoints"]:
                    point[1] -= time_offset * 1000

        for record in data:
            if not record["dimensions"].get("__time_compare"):
                if not record.get("time_offset"):
                    record["time_offset"] = "current"
                    record["target"] = f"current-{record['target']}"
            else:
                del record["dimensions"]["__time_compare"]

        return data


class AddNullDataProcessor:
    """
    根据时间范围和周期补全空数据点
    """

    @classmethod
    def process_formatted_data(cls, params: dict, data: list) -> list:
        if params["type"] == "instant" or params["format"] != "time_series":
            return data

        if params.get("step"):
            interval = -parse_time_compare_abbreviation(params["step"])
        else:
            interval = 0
            for query_config in params.get("query_configs", []):
                if query_config["interval"]:
                    interval = min(query_config["interval"], interval) if interval else query_config["interval"]

        if not interval:
            return data

        # 获取降采样周期
        interval *= 1000
        if params.get("down_sample_range"):
            sampling_interval = -parse_time_compare_abbreviation(params["down_sample_range"]) * 1000
        else:
            sampling_interval = 0

        # 计算空点判断阈值
        if interval < sampling_interval:
            null_threshold = 2.2 * sampling_interval
        else:
            null_threshold = 2 * interval

        # 起止时间周期对齐
        start_time = time_interval_align(params["start_time"], interval // 1000) * 1000
        end_time = time_interval_align(params["end_time"], interval // 1000) * 1000

        # 日志、事件场景在部分展示场景下不进行时间对齐，避免 drop 掉不完整周期的数据点，从而保证数据统计准确性。
        time_alignment: bool = params.get("time_alignment", True)
        if not time_alignment:
            if start_time > params["start_time"] * 1000:
                start_time -= interval
            if end_time < params["end_time"] * 1000:
                end_time += interval

        for row in data:
            time_to_value = defaultdict(lambda: None)
            for point in row["datapoints"]:
                time_to_value[point[1]] = point[0]

            row["datapoints"] = []
            last_datapoint_timestamp = None
            for timestamp in range(start_time, end_time, interval):
                if time_to_value[timestamp] is None:
                    if params.get("null_as_zero"):
                        # 补 0 代替补 Null
                        row["datapoints"].append([0, timestamp])
                        last_datapoint_timestamp = timestamp
                        continue

                    # 如果当前点没有值且和开始时间相同，则补充空点
                    if timestamp == start_time:
                        row["datapoints"].append([None, timestamp])
                else:
                    # 如果当前点和上一个点的时间差大于阈值，则补充空点
                    if last_datapoint_timestamp and timestamp - last_datapoint_timestamp >= null_threshold:
                        row["datapoints"].append([None, timestamp - interval])
                    row["datapoints"].append([time_to_value[timestamp], timestamp])
                    last_datapoint_timestamp = timestamp

            # 如果最后一个点和结束时间不同，则补充空点
            if row["datapoints"] and row["datapoints"][-1][1] != end_time - interval:
                row["datapoints"].append([None, end_time - interval])
        return data


class RankProcessor:
    """
    维度排序处理
    """

    @classmethod
    def process_params(cls, params: dict) -> dict:
        for query_config in params["query_configs"]:
            if not query_config["functions"]:
                continue

            for f in query_config["functions"]:
                if f["id"] in ["top", "bottom"]:
                    function = f
                    break
            else:
                continue

            # 过滤排序函数
            query_config["functions"] = [f for f in query_config["functions"] if f["id"] not in ["top", "bottom"]]

            n = int(function["params"][0]["value"])

            # 按均值查出所有维度的值
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_source = data_source_class(bk_biz_id=params["bk_biz_id"], **query_config)
            for i in [43200, 7200, 3600, 600, 300, 120, 60]:
                if i < data_source.interval:
                    break

                if (params["end_time"] - params["start_time"]) / 20 > i:
                    data_source.interval = i
                    break
            data_source.metrics = [data_source.metrics[0].copy()]
            query = UnifyQuery(
                bk_biz_id=params["bk_biz_id"],
                data_sources=[data_source],
                expression=query_config["metrics"][0]["alias"],
            )

            points = query.query_data(
                start_time=params["start_time"] * 1000,
                end_time=params["end_time"] * 1000,
                limit=1000,
                slimit=params["slimit"],
            )

            metric_field = data_source.metrics[0].get("alias") or data_source.metrics[0]["field"]
            # 按维度将值合并后进行排序
            dimension_values = defaultdict(int)
            for point in points:
                dimensions = tuple(
                    (key, value) for key, value in point.items() if key not in ["_time_", "_result_", metric_field]
                )
                if point["_result_"] is not None:
                    dimension_values[dimensions] += point["_result_"]
            dimension_value_list = [(dimensions, value) for dimensions, value in dimension_values.items()]
            dimension_value_list.sort(key=lambda x: x[1], reverse=function["id"] == "top")

            # 取前n个维度进行过滤
            rank_filter = []
            for dimension_value in dimension_value_list:
                # 存在维度值为空的情况，跳过
                if not dimension_value[0]:
                    continue
                rank_filter.append({key: value for key, value in dimension_value[0]})
                if len(rank_filter) >= n:
                    break

            if rank_filter:
                query_config["filter_dict"]["rank"] = rank_filter

            # 去除目标过滤
            if "target" in data_source.filter_dict:
                del data_source.filter_dict["target"]

        return params

    @classmethod
    def process_formatted_data(cls, params: dict, data: list) -> list:
        rank_dimensions = []
        for query_config in params["query_configs"]:
            if query_config["filter_dict"].get("rank", []):
                rank_dimensions = query_config["filter_dict"]["rank"]
                break

        if not rank_dimensions:
            return data

        sort_index = {
            tuple((key, str(value)) for key, value in sorted(dimension.items(), key=lambda x: x[0])): index
            for index, dimension in enumerate(rank_dimensions)
        }

        if not sort_index:
            return data

        data.sort(
            key=lambda x: sort_index.get(
                tuple((key, str(value)) for key, value in sorted(x["dimensions"].items(), key=lambda d: d[0])), -1
            )
        )

        return data


class HeatMapProcessor:
    @staticmethod
    def get_dimension_tuple(dimensions: dict):
        """
        维度元组化
        """
        dimension_tuple = []
        for key, value in dimensions.items():
            # 如果值为数值型，则解析为数值型进行排序
            try:
                value = int(value)
            except (ValueError, TypeError):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = str(value)
            dimension_tuple.append((key, value))
        return tuple(sorted(dimension_tuple))

    @classmethod
    def process_formatted_data(cls, params: dict, data: list) -> list:
        """
        为了适配histogram指标在heatmap中的显示排序问题，这里对维度进行统一排序。
        所有能转换为数值的维度在转换后再进行排序，排序为从大到小。
        """
        if params["format"] != "heatmap":
            return data

        # 如果有使用rank排序则不进行重排
        for query_config in params.get("query_configs", []):
            if query_config["filter_dict"].get("rank", []):
                return data

        # 讲维度转换为数值后排序
        data = sorted(data, key=lambda x: cls.get_dimension_tuple(x["dimensions"]))

        # 获取周期
        if params.get("step"):
            interval = -parse_time_compare_abbreviation(params["step"])
        else:
            interval = 0
            for query_config in params.get("query_configs", []):
                if query_config["interval"]:
                    interval = min(query_config["interval"], interval) if interval else query_config["interval"]
        interval *= 1000
        if not interval:
            return data

        # 获取时间范围
        start_time = time_interval_align(params["start_time"], interval // 1000) * 1000
        end_time = time_interval_align(params["end_time"], interval // 1000) * 1000

        # 将数据转换为以时间戳为key的字典
        for row in data:
            datapoints = row.pop("datapoints", [])
            row["time_to_value"] = {point[1]: point[0] for point in datapoints}
            row["datapoints"] = []

        # 在heatmap模式下，前端会以第一个维度的时间列表为准，因此所有的维度都需要补充完整的时间范围，否则会导致数据错位
        # 按照完整的时间范围进行数据生成，确保每个周期都有数据
        for timestamp in range(start_time, end_time, interval):
            for index, row in enumerate(data):
                # 如果当前维度没有数据，则补充空值
                if timestamp not in row["time_to_value"]:
                    row["datapoints"].append([None, timestamp])

                # 如果当前维度有数据，则进行差值计算
                if data[index]["time_to_value"].get(timestamp) is not None:
                    if index == 0:
                        # 第一条数据，直接取值
                        row["datapoints"].append([row["time_to_value"][timestamp], timestamp])
                    else:
                        # 非第一条数据，取当前值减去上一条数据的值
                        previous_value = data[index - 1]["time_to_value"].get(timestamp) or 0
                        row["datapoints"].append([row["time_to_value"][timestamp] - previous_value, timestamp])
                else:
                    row["datapoints"].append([None, timestamp])

        # 删除time_to_value
        for row in data:
            del row["time_to_value"]

        return data


class QueryTypeProcessor:
    @classmethod
    def process_params(cls, params: dict) -> dict:
        """
        调整查询周期及时间范围模拟instant query
        """
        if params["type"] != "instant":
            return params

        for query_config in params["query_configs"]:
            if query_config["data_source_label"] == DataSourceLabel.PROMETHEUS:
                # promql查询时锁定step
                query_config["interval"] = 60
            params["start_time"] = max(params["end_time"] - query_config["interval"] * 5, params["start_time"])

        return params

    @classmethod
    def process_formatted_data(cls, params: dict, data: list) -> list:
        """
        取每个维度的最后一个点
        """
        if params["type"] != "instant":
            return data

        # 取最后一个值，并将时间设置为end_time
        new_data = []
        for record in data:
            for datapoint in reversed(record["datapoints"]):
                if datapoint[0] is not None and datapoint[1] > params["start_time"] * 1000:
                    record["datapoints"] = [[datapoint[0], params["end_time"] * 1000]]
                    new_data.append(record)
                    break
        return new_data


class UnifyQueryRawResource(ApiAuthResource):
    """
    统一查询接口 (原始数据)
    """

    re_down_sample = re.compile(r"^\d+[mshdw]$")

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
            group_by = serializers.ListField(label="聚合字段", default=[])
            interval_unit = serializers.ChoiceField(label="聚合周期单位", choices=("s", "m"), default="s")
            interval = serializers.CharField(label="时间间隔", default="auto")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)
            promql = serializers.CharField(label="PromQL", allow_blank=True, required=False)

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

        target = serializers.ListField(default=[], label="监控目标")
        target_filter_type = serializers.ChoiceField(
            label="监控目标过滤方法", default="auto", choices=["auto", "query", "post-query"]
        )
        post_query_filter_dict = serializers.DictField(label="后置查询过滤条件", default={})
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", allow_empty=False, child=QueryConfigSerializer())
        expression = serializers.CharField(label="查询表达式", allow_blank=True)
        stack = serializers.CharField(label="堆叠标识", required=False, allow_blank=True)
        function = serializers.DictField(label="功能函数", default={})
        # 表达式计算函数
        functions = serializers.ListField(
            label="计算函数", default=[], child=QueryConfigSerializer.FunctionSerializer()
        )

        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        limit = serializers.IntegerField(label="限制每个维度点数", default=settings.SQL_MAX_LIMIT)
        slimit = serializers.IntegerField(label="限制维度数量", default=settings.SQL_MAX_LIMIT)
        down_sample_range = serializers.CharField(label="降采样周期", default="", allow_blank=True)
        format = serializers.ChoiceField(choices=("time_series", "heatmap", "table"), default="time_series")
        type = serializers.ChoiceField(choices=("instant", "range"), default="range")
        series_num = serializers.IntegerField(label="查询多少条数据", required=False)
        time_alignment = serializers.BooleanField(label="是否保留最后一个数据点", required=False, default=True)
        null_as_zero = serializers.BooleanField(label="是否将空值转换为0", required=False, default=False)
        query_method = serializers.CharField(label="查询方法", required=False, default="query_data")
        unit = serializers.CharField(label="单位", default="", allow_blank=True)
        with_metric = serializers.BooleanField(label="是否返回metric信息", default=True)

        @classmethod
        def to_str(cls, value):
            if isinstance(value, dict):
                return {k: cls.to_str(v) for k, v in value.items() if v or not isinstance(v, dict | list)}
            elif isinstance(value, list):
                return [cls.to_str(v) for v in value if v or not isinstance(v, dict | list)]
            elif isinstance(value, dict):
                return {k: cls.to_str(v) for k, v in value.items() if v or not isinstance(v, dict | list)}
            else:
                return str(value)

        def validate(self, attrs):
            for query_config in attrs["query_configs"]:
                # 图表查询周期检查
                interval = query_config["interval"]
                if interval != "auto":
                    query_config["interval"] = int(query_config["interval"])
                # 过滤条件字符串化
                query_config["filter_dict"] = self.to_str(query_config["filter_dict"])

                if not UnifyQueryRawResource.re_down_sample.match(attrs["down_sample_range"]):
                    attrs["down_sample_range"] = ""

                query_config["filter_dict"] = self.process_filter_dict(attrs["bk_biz_id"], query_config["filter_dict"])
            return attrs

        def validate_target(self, target: list):
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

        def process_filter_dict(self, bk_biz_id: int, value):
            if value:
                delete_fields = []
                for k, v in value.items():
                    if v == "undefined":
                        delete_fields.append(k)
                for field in delete_fields:
                    del value[field]

            # 过滤主机监控图表的targets过滤字段
            targets = value.get("targets")
            if targets:
                for target in targets:
                    if is_ipv6_biz(bk_biz_id):
                        target.pop("bk_target_ip", None)
                        target.pop("bk_target_cloud_id", None)
                    else:
                        target.pop("bk_host_id", None)
            return value

    @classmethod
    def get_metric_info(cls, params: dict) -> list:
        metric_queries = []
        for query_config in params["query_configs"]:
            metric_fields = [metric["field"] for metric in query_config["metrics"]]
            if not metric_fields:
                continue

            if query_config["data_source_label"] != DataSourceLabel.BK_LOG_SEARCH:
                if query_config.get("data_label"):
                    metric_queries.append(Q(data_label=query_config["data_label"], metric_field__in=metric_fields))
                else:
                    metric_queries.append(Q(result_table_id=query_config["table"], metric_field__in=metric_fields))
            else:
                metric_queries.append(Q(related_id=query_config["index_set_id"], metric_field__in=metric_fields))

        if not metric_queries:
            return []

        metrics = MetricListCache.objects.filter(
            reduce(lambda x, y: x | y, metric_queries), bk_tenant_id=get_request_tenant_id()
        )
        metric_infos = cls.transfer_metric(metrics=metrics, bk_biz_id=params["bk_biz_id"])
        return metric_infos

    @staticmethod
    def transfer_metric(bk_biz_id, metrics):
        metric_infos = []
        for metric in metrics:
            metric_info = model_to_dict(metric)
            metric_info.pop("bk_biz_id", None)

            if is_ipv6_biz(bk_biz_id) and "bk_target_ip" in metric_info["default_dimensions"]:
                metric_info["default_dimensions"] = ["bk_host_id"]
            else:
                metric_info["default_dimensions"] = ["bk_target_ip", "bk_target_cloud_id"]

            metric_info["metric_id"] = get_metric_id(
                data_source_label=metric.data_source_label,
                data_type_label=metric.data_type_label,
                result_table_id=metric.result_table_id,
                index_set_id=metric.related_id,
                metric_field=metric.metric_field,
                custom_event_name=metric.extend_fields.get("custom_event_name", ""),
            )
            metric_infos.append(metric_info)
        return metric_infos

    @staticmethod
    def handle_special_uptime_check_metric(query_configs: list[dict]):
        """
        处理拨测响应内容及响应码查询配置
        """
        for query_config in query_configs:
            if not query_config["metrics"]:
                continue

            field = query_config["metrics"][0]["field"]
            if not query_config["table"].startswith("uptimecheck.") or field not in UPTIMECHECK_ERROR_CODE_MAP:
                continue

            query_config["metrics"][0]["field"] = "available"
            query_config["filter_dict"]["error_code"] = str(UPTIMECHECK_ERROR_CODE_MAP[field])

    @staticmethod
    def get_target_instance(params) -> bool:
        """
        查询目标实例
        当返回为False时，代表存在目标但值为空
        """
        dimension_fields = set()
        for query_config in params["query_configs"]:
            dimension_fields.update(query_config["group_by"])
        if not params["target"] or not params["target"][0]:
            return True

        # 将节点解析为实例
        target_instances = resource.cc.parse_topo_target(params["bk_biz_id"], list(dimension_fields), params["target"])

        # 如果为None，则代表目标不为空，但结果为空
        if not target_instances:
            return target_instances is not None

        # 如果主机过滤模式为query或模式为auto且目标实例数量小于100，则将目标实例作为查询条件
        if params["target_filter_type"] == "query" or (
            params["target_filter_type"] == "auto" and len(target_instances) < 100
        ):
            for query_config in params["query_configs"]:
                query_config["filter_dict"]["target"] = target_instances
        else:
            params["post_query_filter_dict"]["target"] = target_instances
        return True

    def get_dimension_combination(self, data_source, params):
        """获取指定数量的topk维度组合"""

        if not (
            (
                data_source.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
                and data_source.data_type_label == DataTypeLabel.TIME_SERIES
            )
            or (
                data_source.data_source_label == DataSourceLabel.BK_DATA
                and data_source.data_type_label == DataTypeLabel.TIME_SERIES
            )
        ):
            return

        series_num = params.get("series_num", None)
        if series_num is None:
            return

        # 加上topk函数，以获取指定数量的维度组合
        if not data_source.functions:
            data_source.functions.append({"id": "topk", "params": [{"id": "k", "value": series_num}]})
        else:
            for function in data_source.functions:
                if function["id"] == "topk":
                    function["params"][0]["value"] = series_num
                    break
            else:
                data_source.functions.append({"id": "topk", "params": [{"id": "k", "value": series_num}]})
        query = UnifyQuery(
            bk_biz_id=params["bk_biz_id"],
            data_sources=[data_source],
            expression=data_source.metrics[0].get("alias") or "a",
            functions=params["functions"],
        )
        points = query.query_data(
            start_time=(params["end_time"] - 5 * 60) * 1000,
            end_time=params["end_time"] * 1000,
            limit=params["limit"],
            slimit=params["slimit"],
            down_sample_range=params["down_sample_range"],
        )

        # 去掉排序函数topk
        data_source.functions = [f for f in data_source.functions if f["id"] != "topk"]

        # 提取topk维度组合
        dimension_tuples_set: set[tuple[tuple]] = set()
        for point in points:
            dimension_tuples: list[tuple] = []
            for key in data_source.group_by:
                if key in point:
                    dimension_tuples.append((key, point[key]))
            dimension_tuples_set.add(tuple(dimension_tuples))

        # 将topk维度组合条件拼接回第一个指标的查询条件中
        data_source.filter_dict["series"] = [
            {key: value for key, value in dimension_tuple}
            for dimension_tuple in list(dimension_tuples_set)[:series_num]
        ]

    def perform_request(self, params):
        # cookies filter
        cookies_filter = get_cookies_filter()
        if cookies_filter:
            for query_config in params["query_configs"]:
                query_config["filter_dict"]["cookies"] = cookies_filter

        # 拨测指标处理
        self.handle_special_uptime_check_metric(params["query_configs"])

        # 指标信息查询
        metrics = self.get_metric_info(params)

        # 配置预处理
        for query_config in params["query_configs"]:
            query_config.pop("time_field", None)

            # 补全时间字段
            for metric in metrics:
                if not query_config["metrics"]:
                    continue

                metric_field = query_config["metrics"][0]["field"]
                if (
                    (
                        metric["result_table_id"] == query_config.get("table", "")
                        or metric["data_label"] == query_config.get("data_label", "")
                        or metric["related_id"] == str(query_config.get("index_set_id", ""))
                    )
                    and metric_field == metric["metric_field"]
                    and metric["data_source_label"] == query_config["data_source_label"]
                    and metric["data_type_label"] == query_config["data_type_label"]
                ):
                    query_config["time_field"] = metric["extend_fields"].get("time_field")
                    break

            if query_config["interval"] == "auto":
                query_config["interval"] = get_auto_interval(60, params["start_time"], params["end_time"])
            # 删除全选条件
            query_config["where"] = remove_all_conditions(query_config["where"])

        # 查询目标实例
        if not self.get_target_instance(params):
            return {"series": [], "metrics": metrics}

        # 维度top/bottom排序
        params = RankProcessor.process_params(params)
        params = QueryTypeProcessor.process_params(params)

        # 数据查询
        data_sources = []
        time_alignment: bool = params.get("time_alignment", True)
        for query_config_index, query_config in enumerate(params["query_configs"]):
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            if not time_alignment:
                query_config["time_alignment"] = time_alignment
            data_source = data_source_class(bk_biz_id=params["bk_biz_id"], **query_config)
            if hasattr(data_source, "group_by"):
                query_config["group_by"] = data_source.group_by

            # 先获取指定数量的topk维度组合条件，后续将基于这些维度组合条件进行查询
            # 目前只支持ui数据源的指标，如果有多个指标，只获取第一个指标的topk数量的维度组合条件，并将这些条件拼接回第一个指标的查询条件中
            # 计算平台数据不参与
            if query_config_index == 0 and query_config["data_source_label"] != DataSourceLabel.BK_DATA:
                self.get_dimension_combination(data_source, params)

            data_sources.append(data_source)

            try:
                unify_query_count(
                    data_type_label=query_config["data_type_label"],
                    bk_biz_id=params["bk_biz_id"],
                    data_source_label=query_config["data_source_label"],
                )
            except Exception:
                logger.exception("failed to count unify query")
                continue

        query = UnifyQuery(
            bk_biz_id=params["bk_biz_id"],
            data_sources=data_sources,
            expression=params["expression"],
            functions=params["functions"],
        )
        safe_push_to_gateway(registry=OPERATION_REGISTRY)

        query_method_map: dict[str, Callable[[Any], list[dict]]] = {
            "query_data": query.query_data,
            "query_reference": query.query_reference,
        }
        query_method: Callable[[Any], list[dict]] = query_method_map.get(params.get("query_method"), query.query_data)

        points = query_method(
            start_time=params["start_time"] * 1000,
            end_time=params["end_time"] * 1000,
            limit=params["limit"],
            slimit=params["slimit"],
            down_sample_range=params["down_sample_range"],
            time_alignment=time_alignment,
        )

        # 如果存在数据后过滤条件，则进行过滤
        if params.get("post_query_filter_dict"):
            condition_filter = load_agg_condition_instance(params["post_query_filter_dict"])
            points = [point for point in points if condition_filter.is_match(point)]

        # 数据预处理
        points = TimeCompareProcessor.process_origin_data(params, points)
        metrics = metrics if params["with_metric"] else []
        return {
            "series": points,
            "metrics": metrics,
        }


class GraphUnifyQueryResource(UnifyQueryRawResource):
    """
    统一查询接口 (适配图表展示)
    """

    def get_unit(self, metrics: list[dict], params: dict) -> str:
        """
        获取单位信息
        """
        # 如果查询配置中指定了单位，则直接返回
        if params.get("unit"):
            return params["unit"]

        # 多指标无单位
        if len(params["query_configs"]) > 1 or not metrics:
            return ""

        for metric in params["query_configs"][0]["metrics"]:
            if metric.get("method", "").lower() in ["count", "count_without_time"]:
                return ""

        return metrics[0].get("unit", "")

    def data_format(self, params, data):
        """
        转换为Grafana TimeSeries的格式
        :param params: 请求参数
        :param data: [{
            "metric_field": 32960991004.444443,
            "bk_target_ip": "127.0.0.1",
            "minute60": 1581350400000,
            "time": 1581350400000
        }]
        :type data: list
        :return:
        :rtype: list
        """

        dimension_fields = set(chain(*(query_config["group_by"] for query_config in params["query_configs"])))

        formatted_data = defaultdict(dict)

        # 表达式翻译
        expression: str = params["expression"]
        stack: str = params.get("stack")
        data_source_label = ""
        is_bar = False
        for query_config in params["query_configs"]:
            data_source_label = query_config.get("data_source_label")
            for metric in query_config["metrics"]:
                if metric.get("alias"):
                    expression = expression.replace(metric["alias"], f"{metric['method']}({metric['field']})")
                is_bar = (query_config.get("data_source_label"), query_config.get("data_type_label")) in (
                    (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
                    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),
                    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
                    (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
                    (DataSourceLabel.BK_APM, DataTypeLabel.LOG),
                    (DataSourceLabel.BK_APM, DataTypeLabel.EVENT),
                    (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
                    (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
                )

        for record in data:
            dimensions = tuple(
                sorted(
                    (key, value)
                    for key, value in record.items()
                    if key in dimension_fields
                    or key == "__time_compare"
                    or (data_source_label == DataSourceLabel.PROMETHEUS and key not in ["_result_", "_time_"])
                )
            )

            if record.get("_result_") is not None:
                if isinstance(record["_result_"], int | float):
                    record["_result_"] = round(record["_result_"], settings.POINT_PRECISION)

                # 查询结果取值
                formatted_data[dimensions].setdefault(("_result_", expression), []).append(
                    [record.get("_result_"), record["_time_"]]
                )

            # 其他指标取值
            for query_config in params["query_configs"]:
                for metric in query_config["metrics"]:
                    # 只展示需要展示的指标
                    if not metric.get("display"):
                        continue

                    if metric.get("alias"):
                        alias = metric["alias"]
                        display_dimension = f"{metric['field']}({alias})"
                    else:
                        alias = metric["field"]
                        display_dimension = alias

                    alias = metric.get("alias") or metric["field"]
                    if record.get(alias) is not None:
                        value = record[alias]
                        if isinstance(value, int | float):
                            value = round(value, settings.POINT_PRECISION)
                        formatted_data[dimensions].setdefault((alias, display_dimension), []).append(
                            [value, record["_time_"]]
                        )

        # 构造图表数据结构
        result = []
        for dimensions, metric_to_data_point in formatted_data.items():
            dimension_string = ", ".join(f"{dimension[0]}={dimension[1]}" for dimension in dimensions)
            for metric_tuple, value in metric_to_data_point.items():
                target = metric_tuple[1]
                if dimension_string:
                    target += f"{{{dimension_string}}}"
                if not target:
                    target = "value"

                item = {
                    "dimensions": {dimension[0]: dimension[1] for dimension in dimensions},
                    "target": target,
                    "metric_field": metric_tuple[0],
                    "datapoints": value,
                    "alias": metric_tuple[0],
                    "type": "bar" if is_bar else "line",
                }
                if stack:
                    item["stack"] = stack
                result.append(item)

        return result

    def translate_dimensions(self, params: dict, data: list):
        """
        维度翻译
        """
        if not data:
            return data

        # 主机ID
        host_id_list = {row["dimensions"]["bk_host_id"] for row in data if row["dimensions"].get("bk_host_id")}
        if host_id_list:
            try:
                hosts = api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=host_id_list)
            except BKAPIError:
                hosts = []
        else:
            hosts = []
        host_id_to_name = {str(host.bk_host_id): host.display_name for host in hosts}

        service_instance_id_list = set()  # 服务实例
        bcs_cluster_id_list = set()  # BCS集群
        for row in data:
            if row["dimensions"].get("bk_service_instance_id"):
                service_instance_id_list.add(row["dimensions"]["bk_service_instance_id"])
            if row["dimensions"].get("bk_target_service_instance_id"):
                service_instance_id_list.add(row["dimensions"]["bk_target_service_instance_id"])
            if row["dimensions"].get("bcs_cluster_id"):
                bcs_cluster_id_list.add(row["dimensions"]["bcs_cluster_id"])
        if service_instance_id_list:
            try:
                service_instances = api.cmdb.get_service_instance_by_id(
                    bk_biz_id=params["bk_biz_id"], service_instance_ids=service_instance_id_list
                )
            except BKAPIError:
                service_instances = []
        else:
            service_instances = []
        service_instance_id_to_name = {
            str(service_instance.service_instance_id): service_instance.name for service_instance in service_instances
        }

        # 节点类型、节点名称
        bk_obj_id_to_name = {}
        bk_inst_id_to_name = {}
        topo_tree = None
        all_nodes = None
        for row in data:
            bk_obj_id = row["dimensions"].get("bk_obj_id")
            bk_inst_id = row["dimensions"].get("bk_inst_id")
            if bk_obj_id and bk_inst_id:
                if topo_tree is None or all_nodes is None:
                    topo_tree = api.cmdb.get_topo_tree(bk_biz_id=params["bk_biz_id"])
                    all_nodes = topo_tree.get_all_nodes_with_relation()
                node_key = f"{bk_obj_id}|{bk_inst_id}"
                node = all_nodes.get(node_key)
                if node:
                    bk_obj_id_to_name[bk_obj_id] = node.bk_obj_name
                    bk_inst_id_to_name[bk_inst_id] = node.bk_inst_name

        # BCS集群
        if bcs_cluster_id_list:
            bcs_clusters = BCSCluster.objects.filter(
                bk_biz_id=params["bk_biz_id"], bcs_cluster_id__in=bcs_cluster_id_list
            ).only("bcs_cluster_id", "name")
            bcs_cluster_to_name = {cluster.bcs_cluster_id: cluster.name for cluster in bcs_clusters}
        else:
            bcs_cluster_to_name = {}

        # 字段映射
        field_mapper = {
            "bk_host_id": host_id_to_name,
            "service_instance_id": service_instance_id_to_name,
            "bk_target_service_instance_id": service_instance_id_to_name,
            "bk_obj_id": bk_obj_id_to_name,
            "bk_inst_id": bk_inst_id_to_name,
            "bcs_cluster_id": bcs_cluster_to_name,
        }
        for row in data:
            dimensions_translation = {}
            for field, mapper in field_mapper.items():
                if row["dimensions"].get(field) and mapper.get(row["dimensions"][field]):
                    dimensions_translation[field] = mapper.get(row["dimensions"][field])
            row["dimensions_translation"] = dimensions_translation
        return data

    def perform_request(self, params):
        raw_query_result = super().perform_request(params)
        points = raw_query_result["series"]
        if not points:
            return raw_query_result

        metrics = raw_query_result["metrics"]

        # 数据格式化
        series = self.data_format(params, points)

        # 数据后处理
        series = TimeCompareProcessor.process_formatted_data(params, series)
        series = RankProcessor.process_formatted_data(params, series)
        series = AddNullDataProcessor.process_formatted_data(params, series)
        series = HeatMapProcessor.process_formatted_data(params, series)
        series = QueryTypeProcessor.process_formatted_data(params, series)
        series = self.translate_dimensions(params, series)

        # 补充单位信息
        unit = self.get_unit(metrics, params)
        for row in series:
            row["unit"] = unit
        return {
            "series": series,
            "metrics": metrics,
        }


class GraphTraceQueryResource(ApiAuthResource):
    """
    trace信息查询
    """

    operator_mapping = {
        "reg": "req",
        "nreg": "nreq",
        "include": "req",
        "exclude": "nreq",
        "eq": "contains",
        "neq": "ncontains",
    }

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()

            bk_biz_id = serializers.CharField(label="业务ID")
            where = serializers.ListField(label="查询条件", default=[])
            table = serializers.CharField(label="结果表ID", allow_blank=True)
            data_label = serializers.CharField(label="结果表ID", allow_blank=True, default="")
            metrics = serializers.ListField(label="查询指标", allow_empty=False, child=MetricSerializer())
            data_source_label = serializers.CharField(label="数据来源")
            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )

        query_configs = serializers.ListField(child=QueryConfigSerializer(), label="查询参数", required=True)
        down_sample_range = serializers.CharField(label="降采样周期", default="1m", allow_blank=True)
        start_time = serializers.CharField(label="开始时间")
        end_time = serializers.CharField(label="结束时间")

    def to_query_list(self, query_config):
        query_item = {
            "table_id": query_config.get("data_label", "") or query_config["table"],
            "field_name": query_config["metrics"][0]["field"],
            "field_list": ["bk_trace_id", "bk_span_id", "bk_trace_value", "bk_trace_timestamp"],
            "conditions": {
                "field_list": [
                    {
                        "field_name": field["key"],
                        "value": [str(val) for val in field["value"]]
                        if isinstance(field["value"], list)
                        else str(field["value"]),
                        "op": self.operator_mapping.get(field["method"], field["method"]),
                    }
                    for field in query_config["where"]
                ],
                "condition_list": [field.get("condition", "and") for field in query_config["where"]],
            },
        }

        query_item["conditions"]["field_list"].append(
            {"field_name": "bk_biz_id", "value": [str(query_config["bk_biz_id"])], "op": "contains"}
        )

        return query_item

    @staticmethod
    def is_valid_data_source(query_config):
        return (query_config["data_source_label"], query_config["data_type_label"]) in UnifyQueryDataSources

    def validate_request_data(self, request_data):
        validated_request_data = super().validate_request_data(request_data)
        query_configs = validated_request_data.pop("query_configs", [])
        if not (query_configs and self.is_valid_data_source(query_configs[0])):
            raise ValidationError("not supported data source")
        validated_request_data["query_list"] = [self.to_query_list(query_config) for query_config in query_configs]
        bk_biz_id = query_configs[0]["bk_biz_id"]
        validated_request_data["space_uid"] = bk_biz_id_to_space_uid(bk_biz_id)
        logger.info("alert trace query params %s", dict(validated_request_data))
        return validated_request_data

    def perform_request(self, params):
        data = api.unify_query.query_data_by_exemplar(params)
        for item in data.get("series") or []:
            item["data_points"] = item.pop("values", [])
        return data


class GraphPromqlQueryResource(Resource):
    """
    通过PromQL查询图表数据
    """

    ALL_REPLACE_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*\s*(=|=~)\s*['\"]__BKMONITOR_ALL__['\"]\s*,?")
    SURPLUS_COMMA_PATTERN = re.compile(r",\s*}$")

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        promql = serializers.CharField(label="PromQL", allow_blank=True)
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        step = serializers.CharField(default="1m")
        format = serializers.ChoiceField(choices=("time_series", "heatmap", "table"), default="time_series")
        type = serializers.ChoiceField(choices=("instant", "range"), default="range")
        down_sample_range = serializers.CharField(label="降采样周期", default="", allow_blank=True)
        time_alignment = serializers.BooleanField(label="是否保留最后一个数据点", required=False, default=True)

        def validate(self, attrs):
            if attrs["step"] == "auto":
                attrs["step"] = hms_string(get_auto_interval(60, attrs["start_time"], attrs["end_time"]))

            if attrs["step"].isdigit():
                attrs["step"] += "s"

            return attrs

    @classmethod
    def format_data(cls, data: list) -> list:
        """
        图表数据格式化
        """
        result = []
        for s in data:
            series = {
                "alias": "_result_",
                "metric_field": "_result_",
                "unit": "",
                "target": ",".join(
                    f'{key}="{value}"' for key, value in sorted(zip(s["group_keys"], s["group_values"]))
                ),
                "dimensions": dict(zip(s["group_keys"], s["group_values"])),
                "datapoints": [[v[1], v[0]] for v in s["values"]],
            }
            result.append(series)
        return result

    @classmethod
    def remove_all_conditions(cls, promql: str) -> str:
        """
        去除promql中的全选条件
        """
        promql = promql.strip()
        promql = cls.ALL_REPLACE_PATTERN.sub("", promql)
        promql = cls.SURPLUS_COMMA_PATTERN.sub("}", promql)
        return promql

    def perform_request(self, params):
        # cookies filter
        cookies_filter = PrometheusTimeSeriesDataSource.filter_dict_to_promql_match(get_cookies_filter())
        interval = -parse_time_compare_abbreviation(params["step"])

        # instant模式查询最近五分钟
        if params["type"] == "instant":
            params["start_time"] = params["end_time"] - 5 * interval

        if not params["promql"]:
            return {"metrics": [], "series": []}

        params["promql"] = self.remove_all_conditions(params["promql"])

        start_time, end_time = params["start_time"], params["end_time"]
        if params["time_alignment"]:
            start_time, end_time = time_interval_align(start_time, interval), time_interval_align(end_time, interval)

        request_params = dict(
            promql=params["promql"],
            match=cookies_filter,
            start=start_time,
            end=end_time,
            step=params["step"],
            bk_biz_ids=[params["bk_biz_id"]],
            timezone=timezone.get_current_timezone_name(),
            down_sample_range=params["down_sample_range"],
            reference=not params["time_alignment"],
        )

        result = api.unify_query.query_data_by_promql(**request_params)["series"] or []
        series = self.format_data(result)
        series = HeatMapProcessor.process_formatted_data(params, series)
        series = QueryTypeProcessor.process_formatted_data(params, series)
        series = AddNullDataProcessor.process_formatted_data(params, series)
        return {"metrics": [], "series": series}


class DimensionPromqlQueryResource(Resource):
    re_label_value = re.compile(r"label_values\(\s*(([a-zA-Z0-9_:]*(\{.*\})?)\s*,)?\s*([a-zA-Z0-9_]+)\)\s*")
    re_query_result = re.compile(r"query_result\((.*)\)")
    re_label_names = re.compile(r"label_names\(\s*([a-zA-Z0-9_:]+)\s*\)")

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        promql = serializers.CharField(label="PromQL")
        start_time = serializers.CharField(required=False)
        end_time = serializers.CharField(required=False)

    @classmethod
    def get_query_result(cls, bk_biz_id: int, promql: str) -> list[str]:
        """
        查询query_result函数
        """
        match = cls.re_query_result.match(promql)
        if match:
            promql = match.group(1)

        # 只查询最近15分钟维度
        end_time = arrow.now().timestamp
        start_time = end_time - 900

        graph_data = resource.grafana.graph_promql_query(
            bk_biz_id=bk_biz_id, promql=promql, start_time=start_time, end_time=end_time
        )

        result = []
        for row in graph_data["series"]:
            if not row["datapoints"]:
                continue
            point = row["datapoints"][-1]
            result.append(f"{row['target']} {point[0]} {point[1]}")

        return result

    @classmethod
    def get_label_values(cls, bk_biz_id: int, promql: str, start_time: str, end_time: str) -> list[str]:
        """
        查询label_values函数
        """
        cookies_filter = PrometheusTimeSeriesDataSource.filter_dict_to_promql_match(get_cookies_filter())

        match = cls.re_label_value.match(promql)
        promql = match.group(2)
        label = match.group(4)
        try:
            match_promql = [promql]
            if cookies_filter:
                match_promql.append(cookies_filter)

            params = {
                "bk_biz_ids": [bk_biz_id],
                "match": match_promql,
                "label": label,
            }

            if start_time and end_time:
                params["start"] = start_time
                params["end"] = end_time

            result = api.unify_query.get_promql_label_values(params)
            return result["values"].get(label, [])
        except Exception as e:
            logger.exception(e)
        return []

    @classmethod
    def get_label_names(cls, bk_biz_id: int, promql: str) -> list[str]:
        """
        查询label_names函数
        """
        match = cls.re_label_names.match(promql)
        label = match.group(1)

        split_items = label.split(":")
        params = {
            "bk_biz_ids": [bk_biz_id],
            "metric_name": split_items[-1],
        }

        if len(split_items) == 2:
            params["table_id"] = split_items[0]
        elif len(split_items) == 3:
            params["table_id"] = split_items[1]
            params["data_source"] = split_items[0]
        else:
            return []

        try:
            return api.unify_query.get_tag_keys(**params)
        except BKAPIError as e:
            logger.exception(e)
        return []

    def perform_request(self, params):
        promql = params["promql"].strip()

        if self.re_label_value.match(promql):
            return self.get_label_values(params["bk_biz_id"], promql, params.get("start_time"), params.get("end_time"))
        elif self.re_query_result.match(promql):
            return self.get_query_result(params["bk_biz_id"], promql)
        elif self.re_label_names.match(promql):
            return self.get_label_names(params["bk_biz_id"], promql)
        else:
            # 默认query_result模式
            return self.get_query_result(params["bk_biz_id"], promql)


class DimensionUnifyQuery(Resource):
    """
    统一维度查询
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()
                method = serializers.CharField()
                alias = serializers.CharField(required=False)
                display = serializers.BooleanField(default=False)

            data_source_label = serializers.CharField(label="数据来源")
            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )
            data_label = serializers.CharField(label="数据标签", allow_blank=True, required=False)
            metrics = serializers.ListField(label="查询指标", allow_empty=False, child=MetricSerializer())
            table = serializers.CharField(label="结果表名", required=False, allow_blank=True)
            group_by = serializers.ListField(label="聚合字段", required=False, default=[])
            where = serializers.ListField(label="过滤条件")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
            index_set_id = serializers.IntegerField(required=False, label="索引集ID")

            def validate(self, attrs: dict) -> dict:
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")
                return attrs

            def validate_filter_dict(self, value):
                if value:
                    for k, v in value.items():
                        if v == "undefined":
                            value.pop(k)
                return value

        dimension_field = serializers.CharField(label="查询字段")
        target = serializers.ListField(default=[], label="监控目标")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", allow_empty=False, child=QueryConfigSerializer())

        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        slimit = serializers.IntegerField(label="限制维度数量", default=GRAPH_MAX_SLIMIT)

    @classmethod
    def query_dimensions(cls, params) -> list:
        # 1、支持多维度字段值的查询
        # 与GetVariableValue.query_dimension接口一样
        fields = params["dimension_field"].split("|")

        # 2、如果是要查询"拓扑节点名称(bk_inst_id)"，则需要把"拓扑节点类型(bk_obj_id)"一并带上
        # 与GetVariableValue.query_dimension接口一样
        if "bk_inst_id" in fields:
            # 确保bk_obj_id在bk_inst_id之前，为后面的dimensions翻译做准备
            fields = [f for f in fields if f != "bk_obj_id"]
            fields.insert(0, "bk_obj_id")

        # 3、数据查询
        data_sources = []
        for query_config in params["query_configs"]:
            metric = query_config["metrics"][0]

            # 3.1 http拨测，响应码和响应消息指标转换
            # 与GetVariableValue.query_dimension接口一样
            if str(query_config["table"]).startswith("uptimecheck."):
                query_config["where"] = []
                if metric["field"] in ["response_code", "message"]:
                    metric["field"] = "available"

            # 3.2 事件型指标特殊处理
            # 比GetVariableValue.query_dimension接口少了指标字段为系统时间主机重启、进程端口、PING不可达、自定义字符型的处理
            if query_config["table"] == SYSTEM_EVENT_RT_TABLE_ID:
                # 特殊处理corefile signal的维度可选值
                if metric["field"] == "corefile-gse" and params["dimension_field"] == "signal":
                    return [{"value": item, "label": item} for item in CORE_FILE_SIGNAL_LIST]
                else:
                    return []

            # 3.3 如果指标与待查询维度相同，则返回空
            # 与GetVariableValue.query_dimension接口一样
            if metric["field"] == params["dimension_field"]:
                return []

            # 3.4 聚合字段设置为待查询字段
            # 与GetVariableValue.query_dimension接口一样
            query_config["group_by"] = fields
            # 3.5 扩大聚合周期
            # GetVariableValue.query_dimension中时间间隔根据传入的参数 interval 确定，
            # 如果没有传入，则时间间隔基于开始时间和结束时间的范围而定
            query_config["interval"] = 600

            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_sources.append(data_source_class(bk_biz_id=params["bk_biz_id"], **query_config))

        # 3.6 查询维度的值，会先调用UnifyQuery的query_dimensions方法
        # 3.6.1 当只有一个data_source对象时，实际上与GetVariableValue.query_dimension中调用查询方法一样，
        # 都是调用对应data_source的query_dimensions方法查询
        # 3.6.2 比GetVariableValue.query_dimension多支持有多个data_source对象的查询
        # 3.6.3 GetVariableValue.query_dimension查询时没有传expression参数
        expression = "+".join(q["metrics"][0]["alias"] for q in params["query_configs"])
        query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=data_sources, expression=expression)
        points = query.query_dimensions(
            dimension_field=fields,
            limit=params["slimit"],
            start_time=params["start_time"] * 1000,
            end_time=params["end_time"] * 1000,
            interval=600,
        )

        # 4、 处理数据，支持多字段查找
        # 与GetVariableValue.query_dimension调用的接口一样
        dimensions = resource.grafana.get_variable_value.assemble_dimensions(fields, points)

        return list(dimensions)

    def perform_request(self, request_params):
        query_configs = request_params["query_configs"]
        if not query_configs:
            return []

        query_config = query_configs[0]
        params = {
            "bk_biz_id": request_params["bk_biz_id"],
            "type": "dimension",
            "scenario": "os",
            "params": {
                # query_config 未必都有这个字段： data_label
                "data_label": query_config.get("data_label", ""),
                "data_source_label": query_config["data_source_label"],
                "data_type_label": query_config["data_type_label"],
                "result_table_id": query_config["table"],
                "where": query_config["where"],
                "start_time": request_params["start_time"],
                "end_time": request_params["end_time"],
                "interval": 600,
                "field": request_params["dimension_field"],
                "metric_field": query_config["metrics"][0]["field"],
                "index_set_id": query_config.get("index_set_id", None),
                "query_string": query_config.get("query_string", ""),
                "filter_dict": query_config.get("filter_dict", {}),
            },
        }
        return resource.grafana.get_variable_value(params)


class DimensionCountUnifyQuery(DimensionUnifyQuery):
    """
    维度数量查询
    """

    def perform_request(self, params):
        params["slimit"] = settings.SQL_MAX_LIMIT
        return len(self.query_dimensions(params))


class GetFunctionsResource(Resource):
    """
    获取统一查询模块可用计算函数
    """

    class RequestSerializer(serializers.Serializer):
        type = serializers.CharField(label="类型", allow_blank=True, default="")

    def perform_request(self, params):
        category_functions = defaultdict(list)
        functions = list(Functions.values())

        # 增加grafana专用函数
        if params["type"] == "grafana":
            functions += list(GrafanaFunctions.values())

        for function in functions:
            category_functions[function.category].append(asdict(function))

        # 按函数分类展示函数
        result = []
        for category in FunctionCategories:
            if category.id not in category_functions:
                continue
            result.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "children": category_functions[category.id],
                }
            )

        return result


class ConvertGrafanaPromqlDashboardResource(Resource):
    """
    转换原生PromQL仪表盘
    TODO: by()语句中的instance等关键词替换
    TODO: 别名变量中的instance等关键词替换
    """

    re_builtin_labels = {
        (re.compile(r"(?<![a-zA-Z0-9_])cluster_id(?=(!=|=~|!~|=|\))\")"), "bcs_cluster_id"),
    }

    re_legend = re.compile(r"(\{\{\s*([a-zA-Z_]+)\s*\}\})")

    class RequestSerializer(serializers.Serializer):
        dashboard = serializers.JSONField(label="原生仪表盘配置")
        bk_biz_id = serializers.IntegerField()
        metric_mapping = serializers.DictField(default={})

    @classmethod
    def convert_metric_id(cls, promql: str, metric_mapping: list[tuple[Pattern, str]]) -> str:
        """
        指标转换
        """
        for re_old, new in metric_mapping:
            promql = re_old.sub(new, promql)
        for re_field, new_field in cls.re_builtin_labels:
            promql = re_field.sub(new_field, promql)
        return promql

    @classmethod
    def convert_legend(cls, legend: str, dimension_map=None):
        """
        别名处理
        """
        field_set = set()
        if legend.startswith("__"):
            return "", field_set
        for match, field in cls.re_legend.findall(legend):
            if dimension_map:
                field = dimension_map.get(field, field)
            legend = legend.replace(match, f"$tag_{field}")
            field_set.add(field)

        return legend, field_set

    def perform_request(self, params):
        old_dashboard = params["dashboard"]

        # 去除无用字段
        old_dashboard.pop("__inputs", None)
        old_dashboard.pop("__requires", None)

        # 指标映射配置
        metric_mapping = [
            (re.compile(rf"(?<![a-zA-Z0-9_:]){old}(?![a-zA-Z0-9_:])"), new)
            for old, new in params["metric_mapping"].items()
        ]

        # 图表配置转换
        for row in old_dashboard.get("rows", old_dashboard.get("panels", [])):
            if row.get("type") == "row" or "rows" in old_dashboard:
                row["datasource"] = None
                panels = row.get("panels", [])
            else:
                panels = [row]

            new_panels = []
            for panel in panels:
                panel["datasource"] = None
                for target in panel.get("targets", []):
                    target["only_promql"] = True
                    target["source"] = self.convert_metric_id(target["expr"], metric_mapping)
                    target["alias"] = self.convert_legend(target.get("legendFormat", ""))[0]
                    target.pop("expr")
                    target.pop("legendFormat", None)
                new_panels.append(panel)

            if "rows" in old_dashboard:
                row["rows"] = new_panels
            elif row.get("type") == "row":
                row["panels"] = new_panels

        # 处理变量配置转换
        for variable in old_dashboard["templating"].get("list", []):
            if variable.get("type") == "query":
                variable["datasource"] = None
                promql = variable["query"]
                if isinstance(promql, dict):
                    promql = promql["query"]

                variable["query"] = {
                    "promql": self.convert_metric_id(promql, metric_mapping),
                    "queryType": "prometheus",
                }

        # 清理annotations配置
        old_dashboard["annotations"] = {}

        return old_dashboard
