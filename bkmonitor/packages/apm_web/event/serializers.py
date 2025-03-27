# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import operator
from functools import reduce
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from django.db.models import Q
from rest_framework import serializers

from apm_web.models import Application, EventServiceRelation
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_explorer.event import serializers as event_serializers
from monitor_web.data_explorer.event.constants import (
    DEFAULT_EVENT_ORIGIN,
    EVENT_ORIGIN_MAPPING,
    CicdEventName,
    EventDomain,
    EventSource,
    Operation,
)
from monitor_web.data_explorer.event.utils import (
    get_data_labels_map,
    get_q_from_query_config,
)


def cicd_cond_handler(cond: Dict[str, Any]) -> Q:
    return Q(**{**cond, "event_name": CicdEventName.PIPELINE_STATUS_INFO.value})


def default_cond_handler(cond: Dict[str, Any]) -> Q:
    return Q(**cond)


def k8s_cond_handler(cond: Dict[str, Any]) -> Q:
    return Q(**cond)


def filter_tables_by_source(
    bk_biz_id: int,
    source_cond: Optional[Dict[str, Any]],
    tables: Iterable[str],
    data_labels_map: Optional[Dict[str, str]] = None,
) -> Set[str]:
    if source_cond is None:
        return set(tables)

    filtered_tables: Set[str] = set()
    if data_labels_map is None:
        data_labels_map = get_data_labels_map(bk_biz_id, tables)

    for table in tables:
        if table in filtered_tables:
            continue

        __, source = EVENT_ORIGIN_MAPPING.get(data_labels_map.get(table), DEFAULT_EVENT_ORIGIN)
        if source_cond["method"] == Operation.EQ["value"]:
            if source in source_cond.get("value") or []:
                filtered_tables.add(table)
        elif source_cond["method"] == Operation.NE["value"]:
            if source not in source_cond.get("value") or []:
                filtered_tables.add(table)

    return filtered_tables


def process_query_config(
    bk_biz_id: int, origin_query_config: Dict[str, Any], event_relations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    where: List[Dict[str, Any]] = []
    source_cond: Optional[Dict[str, Any]] = None
    for cond in origin_query_config.get("where") or []:
        if cond.get("key") == "source":
            source_cond = cond
            continue
        where.append(cond)

    origin_query_config["where"] = where
    filtered_tables: Set[str] = {relation["table"] for relation in event_relations}
    data_labels_map: Dict[str, str] = get_data_labels_map(bk_biz_id, filtered_tables)
    if source_cond:
        filtered_tables = filter_tables_by_source(bk_biz_id, source_cond, filtered_tables, data_labels_map)

    base_q: QueryConfigBuilder = get_q_from_query_config(
        {**origin_query_config, "data_type_label": DataTypeLabel.EVENT, "data_source_label": DataSourceLabel.BK_APM}
    )
    for metric in origin_query_config.get("metrics") or []:
        base_q = base_q.metric(**metric)

    if origin_query_config.get("interval"):
        base_q = base_q.interval(origin_query_config["interval"])

    domain_cond_handler_map: Dict[str, Callable[[Dict[str, Any]], Q]] = {EventDomain.CICD.value: cicd_cond_handler}
    queryset: UnifyQuerySet = UnifyQuerySet().start_time(0).end_time(0)
    for relation in event_relations:
        if relation["table"] not in filtered_tables:
            continue

        q: QueryConfigBuilder = base_q.table(relation["table"])
        domain, __ = EVENT_ORIGIN_MAPPING.get(data_labels_map.get(relation["table"]), DEFAULT_EVENT_ORIGIN)
        cond_handler: Callable[[Dict[str, Any]], Q] = domain_cond_handler_map.get(domain, default_cond_handler)
        if relation["relations"]:
            q = q.filter(Q() | reduce(operator.or_, [cond_handler(cond) for cond in relation["relations"]]))

        queryset = queryset.add_query(q)

    return queryset.config["query_configs"]


class BaseEventRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称", required=False)

    def validate(self, attrs):
        if not Application.objects.filter(bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]).exists():
            raise ValueError(f"应用: ({attrs['bk_biz_id']}){attrs['app_name']} 不存在")
        return attrs


class EventTimeSeriesRequestSerializer(event_serializers.EventTimeSeriesRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return attrs


class EventLogsRequestSerializer(event_serializers.EventLogsRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return attrs


class EventViewConfigRequestSerializer(event_serializers.EventViewConfigRequestSerializer, BaseEventRequestSerializer):
    # 不传 / 为空代表全部
    sources = serializers.ListSerializer(
        child=serializers.ChoiceField(label="事件来源", choices=EventSource.choices()), required=False, default=[]
    )

    # 校验层
    related_sources = serializers.ListSerializer(
        child=serializers.ChoiceField(label="服务关联事件来源", choices=EventSource.choices()), required=False, default=[]
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        source_cond: Optional[Dict[str, Any]] = None
        if attrs.get("sources"):
            source_cond = {"method": Operation.EQ["value"], "value": attrs["sources"]}

        bk_biz_id: int = attrs["bk_biz_id"]
        relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            bk_biz_id, attrs["app_name"], attrs["service_name"]
        )
        filtered_tables: Set[str] = {relation["table"] for relation in relations}
        data_labels_map: Dict[str, str] = get_data_labels_map(bk_biz_id, filtered_tables)
        filtered_tables = filter_tables_by_source(bk_biz_id, source_cond, filtered_tables, data_labels_map)

        related_sources: Set[str] = set()
        data_sources: List[Dict[str, str]] = []
        for relation in relations:
            table: str = relation["table"]
            __, source = EVENT_ORIGIN_MAPPING.get(data_labels_map.get(table), DEFAULT_EVENT_ORIGIN)
            related_sources.add(source)
            if table not in filtered_tables:
                continue

            data_sources.append(
                {"table": table, "data_type_label": DataTypeLabel.EVENT, "data_source_label": DataSourceLabel.BK_APM}
            )

        attrs["data_sources"] = data_sources
        attrs["related_sources"] = list(related_sources)
        return attrs


class EventTopKRequestSerializer(event_serializers.EventTopKRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return attrs


class EventTotalRequestSerializer(event_serializers.EventTotalRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return attrs


class EventTagsRequestSerializer(EventTimeSeriesRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["expression"] = "a"
        for query_config in attrs["query_configs"]:
            query_config["metrics"] = [{"field": "_index", "method": "SUM", "alias": "a"}]
            query_config["group_by"] = ["type"]
        return attrs


class EventTagDetailRequestSerializer(EventTimeSeriesRequestSerializer):
    limit = serializers.IntegerField(label="数量限制", required=False, default=5)
    interval = serializers.IntegerField(label="汇聚周期（秒）", required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        attrs["expression"] = "a"
        for query_config in attrs["query_configs"]:
            attrs["interval"] = query_config.get("interval") or 60

        attrs["end_time"] = attrs["start_time"] + attrs["interval"]

        return attrs


class EventTagStatisticsRequestSerializer(EventTotalRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["expression"] = "a"
        return attrs


class EventGetTagConfigRequestSerializer(BaseEventRequestSerializer):
    key = serializers.CharField(label="配置 Key", required=True)


class EventUpdateTagConfigRequestSerializer(EventGetTagConfigRequestSerializer):
    config = serializers.DictField(label="配置", required=True)


class EventDownloadTopKRequestSerializer(
    event_serializers.EventDownloadTopKRequestSerializer, EventTopKRequestSerializer
):
    def validate(self, attrs):
        return super().validate(attrs)
