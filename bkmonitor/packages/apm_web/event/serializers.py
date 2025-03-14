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
from typing import Any, Dict, List

from django.db.models import Q
from rest_framework import serializers

from apm_web.models import Application, EventServiceRelation
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_explorer.event import serializers as event_serializers
from monitor_web.data_explorer.event.utils import get_q_from_query_config


def process_query_config(
    origin_query_config: Dict[str, Any], event_relations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    base_q: QueryConfigBuilder = get_q_from_query_config(
        {**origin_query_config, "data_type_label": DataTypeLabel.EVENT, "data_source_label": DataSourceLabel.BK_APM}
    )
    for metric in origin_query_config.get("metrics") or []:
        base_q = base_q.metric(**metric)

    if origin_query_config.get("interval"):
        base_q = base_q.interval(origin_query_config["interval"])

    queryset: UnifyQuerySet = UnifyQuerySet().start_time(0).end_time(0)
    for relation in event_relations:
        q: QueryConfigBuilder = base_q.table(relation["table"])
        if relation["relations"]:
            q = q.filter(Q() | reduce(operator.or_, [Q(**cond) for cond in relation["relations"]]))

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
        attrs["query_configs"] = process_query_config(attrs["query_configs"][0], event_relations)
        return attrs


class EventLogsRequestSerializer(event_serializers.EventLogsRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["query_configs"][0], event_relations)
        return attrs


class EventViewConfigRequestSerializer(event_serializers.EventViewConfigRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        data_sources: List[Dict[str, str]] = []
        for relation in EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        ):
            data_sources.append(
                {
                    "table": relation["table"],
                    "data_type_label": DataTypeLabel.EVENT,
                    "data_source_label": DataSourceLabel.BK_APM,
                }
            )

        attrs["data_sources"] = data_sources
        return attrs


class EventTopKRequestSerializer(event_serializers.EventTopKRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["query_configs"][0], event_relations)
        return attrs


class EventTotalRequestSerializer(event_serializers.EventTotalRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        event_relations: List[Dict[str, Any]] = EventServiceRelation.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["query_configs"][0], event_relations)
        return attrs


class EventTagsRequestSerializer(EventTimeSeriesRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["expression"] = "a"
        for query_config in attrs["query_configs"]:
            query_config["metric"] = [{"field": "_index", "method": "SUM", "alias": "a"}]
            query_config["group_by"] = ["type"]
        return attrs
