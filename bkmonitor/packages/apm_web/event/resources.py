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
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.request import get_request
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import Resource
from monitor_web.data_explorer.event import resources as event_resources
from monitor_web.data_explorer.event.constants import (
    DEFAULT_EVENT_ORIGIN,
    K8S_EVENT_TRANSLATIONS,
    SYSTEM_EVENT_TRANSLATIONS,
    CicdEventName,
    EventDomain,
    EventSource,
    EventType,
)
from monitor_web.data_explorer.event.utils import get_data_labels_map, get_field_label
from packages.monitor_web.data_explorer.event.constants import EVENT_ORIGIN_MAPPING

from ..models import ApmMetaConfig, Application
from . import serializers
from .utils import is_enabled_metric_tags

logger = logging.getLogger(__name__)


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
        sources: List[Dict[str, str]] = []
        for related_source in validated_request_data["related_sources"]:
            sources.append({"value": related_source, "alias": EventSource.from_value(related_source).label})

        view_config: Dict[str, Any] = event_resources.EventViewConfigResource().perform_request(validated_request_data)
        view_config["sources"] = sources
        return view_config


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
        # 用于存储多线程查询出来的 timeseries 数据
        origin_time_series_map = {}
        run_threads(
            [
                InheritParentThread(
                    target=self.multi_thread_query_timeseries,
                    args=(event_origin, req_data, origin_time_series_map),
                )
                for event_origin, req_data in self.get_event_origin_req_data_map(
                    validated_request_data,
                    get_data_labels_map(
                        bk_biz_id, [query_config["table"] for query_config in validated_request_data["query_configs"]]
                    ),
                ).items()
            ]
        )
        for event_origin, time_series in origin_time_series_map.items():
            domain, source = event_origin
            origin_time_series_map[event_origin] = self.process_timeseries(time_series, domain, source)
        return {"list": self.transform_aggregated_data(self.merge_timeseries(origin_time_series_map))}

    @classmethod
    def get_event_origin_req_data_map(
        cls,
        validated_request_data: Dict[str, Any],
        data_labels_map: Dict[str, str],
        exclude_origins: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[Tuple[str, str], Any]:
        exclude_origins = exclude_origins or []
        event_origin_req_data_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for query_config in validated_request_data["query_configs"]:
            event_origin: Tuple[str, str] = EVENT_ORIGIN_MAPPING.get(
                data_labels_map.get(query_config["table"]), DEFAULT_EVENT_ORIGIN
            )
            if event_origin in exclude_origins:
                continue

            if event_origin not in event_origin_req_data_map:
                event_origin_req_data_map[event_origin] = copy.deepcopy(validated_request_data)
                event_origin_req_data_map[event_origin]["query_configs"] = []
            event_origin_req_data_map[event_origin]["query_configs"].append(query_config)
        return event_origin_req_data_map

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
    def merge_timeseries(cls, processed_timeseries: Dict[Tuple[str, str], Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
         将不同事件来源的数据合并。
        :param processed_timeseries: 不同事件源的时序数据字典
        :return: 合并后的时序数据字典

        aggregated_timeseries 格式示例:
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
        aggregated_timeseries = defaultdict(list)
        for (domain, source), timeseries in processed_timeseries.items():
            for datapoint in timeseries:
                value = datapoint["value"]
                aggregated_timeseries[datapoint["time"]].append(
                    {"domain": domain, "source": source, "count": value["count"], "statistics": value["statistics"]}
                )
        return aggregated_timeseries

    @classmethod
    def transform_aggregated_data(cls, aggregated_timeseries: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        tags = []
        for timestamp, items in aggregated_timeseries.items():
            filtered_items = [item for item in items if item["count"] > 0]
            for item in filtered_items:
                item["statistics"] = dict(item["statistics"])
            if filtered_items:
                try:
                    tags.append({"time": int(timestamp), "items": filtered_items})
                except ValueError as exc:
                    logger.warning("failed to conversion time, err -> %s", exc)
                    raise ValueError(_(f"类型转换失败: 无法将 '{timestamp}' 转换为整数"))
        return sorted(tags, key=lambda x: x["time"])

    @classmethod
    def multi_thread_query_timeseries(
        cls,
        event_origin: Tuple[str, str],
        validated_request_data: Dict[str, Any],
        timeseries: Dict[Tuple[str, str], Any],
    ):
        timeseries[event_origin] = EventTimeSeriesResource().perform_request(validated_request_data).get("series", [])


class EventTagDetailResource(Resource):
    RequestSerializer = serializers.EventTagDetailRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        def _collect(_key: str, _req_data: Dict[str, Any]):
            result[_key] = self.get_tag_detail(_req_data)
            pass

        result: Dict[str, Dict[str, Any]] = {}
        req_data_with_warn: Dict[str, str] = copy.deepcopy(validated_request_data)
        for qc in req_data_with_warn["query_configs"]:
            qc.setdefault("where", []).append(
                {"key": "type", "method": "eq", "value": [EventType.Warning.value], "condition": "and"}
            )

        run_threads(
            [
                InheritParentThread(target=_collect, args=(EventType.Warning.value, req_data_with_warn)),
                InheritParentThread(target=_collect, args=("All", validated_request_data)),
            ]
        )
        return result

    @classmethod
    def get_tag_detail(cls, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        # 获取 total
        tag_detail: Dict[str, Any] = {"time": validated_request_data["start_time"], "total": 0}
        try:
            total: int = EventTotalResource().perform_request(validated_request_data).get("total") or 0
        except Exception:  # pylint: disable=broad-except
            return {**tag_detail, "total": 0, "list": []}

        if total == 0:
            tag_detail["list"] = []
            return tag_detail

        if total > 20:
            topk: List[Dict[str, Any]] = cls.fetch_topk(validated_request_data)
            for item in topk:
                item["proportions"] = round((item["count"] / total) * 100, 2)
            tag_detail["topk"] = sorted(topk, key=lambda _t: -_t["count"])[: validated_request_data["limit"]]
        else:
            tag_detail["list"] = cls.fetch_logs(validated_request_data)

        tag_detail["total"] = total
        return tag_detail

    @classmethod
    def fetch_topk(cls, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        data_labels_map: Dict[str, str] = get_data_labels_map(
            validated_request_data["bk_biz_id"],
            [query_config["table"] for query_config in validated_request_data["query_configs"]],
        )
        validated_request_data: Dict[str, Any] = copy.deepcopy(validated_request_data)
        validated_request_data["fields"] = ["event_name"]
        origin_req_data_map: Dict[Tuple[str, str], Dict[str, Any]] = EventTagsResource.get_event_origin_req_data_map(
            validated_request_data, data_labels_map
        )
        event_origin_topk_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        run_threads(
            [
                InheritParentThread(target=cls.query_topk, args=(event_origin, req_data, event_origin_topk_map))
                for event_origin, req_data in origin_req_data_map.items()
            ]
        )

        event_tuple_count_map: Dict[Tuple[str, str, str], int] = defaultdict(int)
        for event_origin, topk in event_origin_topk_map.items():
            domain, source = event_origin
            for item in topk:
                event_tuple_count_map[(domain, source, item["value"])] += item["count"]

        event_name_translations: Dict[str, Dict[str, str]] = {
            EventDomain.SYSTEM.value: SYSTEM_EVENT_TRANSLATIONS,
            EventDomain.CICD.value: {
                CicdEventName.PIPELINE_STATUS_INFO.value: CicdEventName.PIPELINE_STATUS_INFO.label
            },
        }
        for k8s_event_name_translations in K8S_EVENT_TRANSLATIONS.values():
            event_name_translations.setdefault(EventDomain.K8S.value, {}).update(k8s_event_name_translations)

        processed_topk: List[Dict[str, Any]] = []
        for event_tuple, count in event_tuple_count_map.items():
            domain, source, event_name = event_tuple
            processed_topk.append(
                {
                    "domain": {"value": domain, "alias": EventDomain.from_value(domain).label},
                    "source": {"value": source, "alias": EventSource.from_value(source).label},
                    "event_name": {
                        "value": event_name,
                        "alias": _("{alias}（{name}）").format(
                            alias=event_name_translations.get(domain, {}).get(event_name, event_name), name=event_name
                        ),
                    },
                    "count": count,
                }
            )
        return processed_topk

    @classmethod
    def query_topk(
        cls,
        event_origin: Tuple[str, str],
        req_data: Dict[str, Any],
        event_origin_topk_map: Dict[Tuple[str, str], List[Dict[str, Any]]],
    ):
        event_origin_topk_map[event_origin] = EventTopKResource().perform_request(req_data)[0].get("list") or []

    @classmethod
    def fetch_logs(cls, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        validated_request_data: Dict[str, Any] = copy.deepcopy(validated_request_data)
        validated_request_data["offset"] = 0
        return EventLogsResource().perform_request(validated_request_data).get("list") or []


class EventTagStatisticsResource(Resource):
    RequestSerializer = serializers.EventTagStatisticsRequestSerializer

    @classmethod
    def query_topk(cls, req_data: Dict[str, Any], field: str) -> Dict[str, Any]:
        try:
            return EventTopKResource().perform_request(
                {**copy.deepcopy(req_data), "fields": [field], "limit": 10, "need_empty": True}
            )[0]
        except Exception:
            return {"total": 0, "field": field, "distinct_count": 0, "list": []}

    @classmethod
    def query_total(
        cls, event_origin: Tuple[str, str], req_data: Dict[str, Any], event_origin_total_map: Dict[Tuple[str, str], int]
    ):
        event_origin_total_map[event_origin] = EventTotalResource().perform_request(req_data).get("total") or 0

    @classmethod
    def fetch_total(cls, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        event_origin_total_map: Dict[Tuple[str, str], int] = {}
        data_labels_map: Dict[str, str] = get_data_labels_map(
            validated_request_data["bk_biz_id"],
            sorted({query_config["table"] for query_config in validated_request_data["query_configs"]}),
        )
        origin_req_data_map: Dict[Tuple[str, str], Dict[str, Any]] = EventTagsResource.get_event_origin_req_data_map(
            # Default 通过 total 差值计算，减少一次查询
            validated_request_data,
            data_labels_map,
            exclude_origins=[DEFAULT_EVENT_ORIGIN],
        )
        run_threads(
            [
                InheritParentThread(target=cls.query_total, args=(event_origin, req_data, event_origin_total_map))
                for event_origin, req_data in origin_req_data_map.items()
            ]
        )

        return {event_origin[1]: total for event_origin, total in event_origin_total_map.items()}

    @classmethod
    def generate_field_columns(cls, field_metas: Dict[str, Any]) -> List[Dict[str, Any]]:
        field_columns: List[Dict[str, Any]] = []
        for field, meta in field_metas.items():
            field_column = {
                "name": field,
                "alias": get_field_label(field),
                "list": [
                    {"value": value, "alias": meta["enum"].from_value(value).label}
                    for value, _ in meta["enum"].choices()
                ],
            }
            field_columns.append(field_column)

            count_map: Optional[Dict[str, int]] = meta.get("count_map")
            if count_map is None:
                continue

            for option in field_column["list"]:
                option["count"] = meta["count_map"].get(option["value"], 0)

        return field_columns

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        topk: Dict[str, Any] = self.query_topk(validated_request_data, field="type")
        type_count_map: Dict[str, int] = {item["value"]: item["count"] for item in topk.get("list", [])}

        source_count_map: Dict[str, int] = self.fetch_total(validated_request_data)
        source_count_map[EventSource.DEFAULT.value] = topk["total"] - sum(source_count_map.values())

        field_metas: Dict[str, Any] = {
            "type": {"count_map": type_count_map, "enum": EventType},
            "source": {"count_map": source_count_map, "enum": EventSource},
        }
        return {"total": topk["total"], "columns": self.generate_field_columns(field_metas)}


class EventGetTagConfigResource(Resource):
    RequestSerializer = serializers.EventGetTagConfigRequestSerializer

    DEFAULT_TAG_CONFIG: Dict[str, Any] = {
        "is_enabled_metric_tags": False,
        "source": {"is_select_all": True, "list": []},
        "type": {"is_select_all": True, "list": []},
    }

    @classmethod
    def process_key(cls, key: str) -> str:
        return f"event_tag_config:{key}"

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        request = get_request(peaceful=True)
        if not request:
            return {}

        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        app: Application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

        # 序列化器已做存在性判断，此处直接使用。
        app_event_config: Dict[str, Any] = app.event_config

        servie_tag_config: Dict[str, Any] = {}
        servie_config: Optional[ApmMetaConfig] = ApmMetaConfig.get_service_config_value(
            bk_biz_id, app_name, service_name, self.process_key(validated_request_data["key"])
        )
        if servie_config:
            servie_tag_config = servie_config.config_value

        return {
            "columns": EventTagStatisticsResource.generate_field_columns(
                {"type": {"enum": EventType}, "source": {"enum": EventSource}}
            ),
            # 配置优先级：默认 > App > Service
            "config": {**self.DEFAULT_TAG_CONFIG, **app_event_config, **servie_tag_config},
        }


class EventUpdateTagConfigResource(Resource):
    RequestSerializer = serializers.EventUpdateTagConfigRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        ApmMetaConfig.service_config_setup(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            service_name=validated_request_data["service_name"],
            config_key=EventGetTagConfigResource.process_key(validated_request_data["key"]),
            config_value=validated_request_data["config"],
        )
        return {}
