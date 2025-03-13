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
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from django.db.models import Q

from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import Resource
from metadata.models import ResultTable
from monitor_web.data_explorer.event import resources as event_resources
from packages.monitor_web.data_explorer.event.constants import (
    EventLabelOriginMapping,
    EventOriginDefaultValue,
)

from . import serializers
from .utils import is_enabled_metric_tags


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventTimeSeriesResource().perform_request(validated_request_data)


class EventLogsResource(Resource):
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventLogsResource().perform_request(validated_request_data)


class EventViewConfigResource(Resource):
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventViewConfigResource().perform_request(validated_request_data)


class EventTopKResource(Resource):
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return event_resources.EventTopKResource().perform_request(validated_request_data)


class EventTotalResource(Resource):
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return event_resources.EventTotalResource().perform_request(validated_request_data)


class EventTagsResource(Resource):
    RequestSerializer = serializers.EventTagsRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        bk_biz_id = validated_request_data["bk_biz_id"]
        if not is_enabled_metric_tags(bk_biz_id, validated_request_data["app_name"]):
            return {"list": []}

        query_configs = validated_request_data["query_configs"]
        # 用于存储多线程查询出来的 timeseries 数据
        timeseries = {}
        run_threads(
            [
                InheritParentThread(
                    target=self.multi_thread_query_timeseries,
                    args=(event_origin, timeseries_request_data, timeseries),
                )
                for event_origin, timeseries_request_data in self.generate_timeseries_requests(
                    query_configs, validated_request_data, self.get_data_labels_map(query_configs, bk_biz_id)
                ).items()
            ]
        )
        for event_origin, value in timeseries.items():
            domain, source = event_origin
            timeseries[event_origin] = self.process_timeseries(value, domain, source)
        return {"list": self.merge_timeseries(timeseries)}

    @classmethod
    def get_data_labels_map(cls, query_configs: List[Dict[str, Any]], bk_biz_id: int) -> Dict[str, str]:
        data_labels_map = {}
        for query_config in query_configs:
            data_labels = (
                ResultTable.objects.filter(bk_biz_id__in=[0, bk_biz_id])
                .filter(Q(table_id=query_config["table"]) | Q(data_label=query_config["table"]))
                .values("table_id", "data_label")
            )
            for data_label_entry in data_labels:
                data_labels_map[data_label_entry["table_id"]] = data_label_entry["data_label"]
                data_labels_map[data_label_entry["data_label"]] = data_label_entry["data_label"]
        return data_labels_map

    @classmethod
    def generate_timeseries_requests(
        cls,
        query_configs: List[Dict[str, Any]],
        validated_request_data: Dict[str, Any],
        data_labels_map: Dict[str, str],
    ):
        event_requests = {}
        for query_config in query_configs:
            origin = EventLabelOriginMapping.get(data_labels_map.get(query_config["table"], ""), None)
            domain = origin.domain if origin else EventOriginDefaultValue.DEFAULT_DOMAIN.value
            source = origin.source if origin else EventOriginDefaultValue.DEFAULT_SOURCE.value
            event_origin = (domain, source)
            if event_origin not in event_requests:
                event_requests[event_origin] = copy.deepcopy(validated_request_data)
                event_requests[event_origin]["query_configs"] = []
            event_requests[event_origin]["query_configs"].append(query_config)
        return event_requests

    @classmethod
    def process_timeseries(cls, timeseries: List[Dict[str, Any]], domain: str, source: str) -> List[Dict[str, Any]]:
        """
        处理一组时间序列数据并返回经过处理的结果列表。
        :param timeseries: 时序数据列表
        :param domain: 数据所属的域
        :param source: 数据来源
        :return: 处理后的时序数据列表
        格式示例：
        [
            {
                "time": "1741095300000",
                "value": {
                    "domain": K8S,
                    "source": BCS,
                    "count": 10,
                    "statistics": {
                        "Warning": 4,
                        "Normal": 6
                    }
                }
            }
        ]
        """
        # 设置默认的时间戳聚合的数据格式
        timestamp_aggregates = defaultdict(lambda: {"statistics": defaultdict(int)})

        for timeseries_entry in timeseries:
            # 计算不同类型的时间戳数据
            for count, timestamp in timeseries_entry["datapoints"]:
                timestamp_aggregates[timestamp]["statistics"][timeseries_entry["dimensions"]["type"]] += count

        processed_timeseries = []
        for timestamp, aggregated_data in timestamp_aggregates.items():
            # 计算总数
            processed_timeseries.append(
                {
                    "time": timestamp,
                    "value": {
                        "domain": domain,
                        "source": source,
                        "count": sum(aggregated_data["statistics"].values()),
                        "statistics": dict(aggregated_data["statistics"]),
                    },
                }
            )

        return processed_timeseries

    @classmethod
    def merge_timeseries(cls, processed_timeseries: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        转换时序数据的格式，将不同事件来源的数据合并。
        :param processed_timeseries: 不同事件源的时序数据字典
        :return: 处理后的时序数据列表

        aggregated_data 格式示例:
        {
            "1741095300000": [
                {
                    "domain": "K8S",
                    "source": "BCS",
                    "count": 10,
                    "statistics": {
                        "Normal": 5,
                        "Warning": 5
                    }
                },
                {
                    "domain": "SYSTEM",
                    "source": "HOST",
                    "count": 1,
                    "statistics": {
                        "Default": 1
                    }
                }
            ]
        }
        """
        aggregated_data = defaultdict(list)

        for (domain, source), timeseries in processed_timeseries.items():
            for series in timeseries:
                timestamp = series["time"]

                # 获取或创建当前时间戳的项
                item = next(
                    (
                        item
                        for item in aggregated_data[timestamp]
                        if item["domain"] == domain and item["source"] == source
                    ),
                    None,
                )

                if not item:
                    item = {"domain": domain, "source": source, "count": 0, "statistics": defaultdict(int)}
                    aggregated_data[timestamp].append(item)

                # 更新统计信息和总计数
                item["count"] += series["value"]["count"]
                for dimension_type, count in series["value"]["statistics"].items():
                    item["statistics"][dimension_type] += count

        transformed_timeseries = []
        for timestamp, items in aggregated_data.items():
            filtered_items = [item for item in items if item["count"] > 0]
            for item in filtered_items:
                item["statistics"] = dict(item["statistics"])
            if filtered_items:
                transformed_timeseries.append({"time": timestamp, "items": filtered_items})

        return transformed_timeseries

    @classmethod
    def multi_thread_query_timeseries(
        cls,
        event_origin: Tuple[str, str],
        validated_request_data: Dict[str, Any],
        timeseries: Dict[Tuple[str, str], Any],
    ):
        timeseries[event_origin] = EventTimeSeriesResource().perform_request(validated_request_data).get("series", [])
