"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import operator
from functools import reduce
from typing import Any
from collections.abc import Callable

from django.db.models import Q
from rest_framework import serializers

from apm_web.event.handler import EventHandler
from apm_web.models import Application
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_explorer.event import serializers as event_serializers
from monitor_web.data_explorer.event.constants import (
    DEFAULT_EVENT_ORIGIN,
    EVENT_ORIGIN_MAPPING,
    CicdEventName,
    EventCategory,
    EventDomain,
)
from monitor_web.data_explorer.event.utils import (
    get_data_labels_map,
    get_q_from_query_config,
    get_cluster_table_map,
)


def cicd_cond_handler(cond: dict[str, Any]) -> Q:
    return Q(
        **{
            "pipelineId": cond.get("pipeline_id"),
            "projectId": cond.get("project_id"),
            "event_name": CicdEventName.PIPELINE_STATUS_INFO.value,
        }
    )


def default_cond_handler(cond: dict[str, Any]) -> Q:
    return Q(**cond)


def k8s_cond_handler(cond: dict[str, Any]) -> Q:
    kind: str | None = cond.get("kind")
    name: str | None = cond.get("name")
    namespace: str | None = cond.get("namespace")
    bcs_cluster_id: str | None = cond.get("bcs_cluster_id")
    if not (bcs_cluster_id and namespace and kind and name):
        return default_cond_handler(cond)

    q: Q = Q(**cond)
    kind_pod_reg_map: dict[str, Any] = {
        "Job": f"{name}-[a-z0-9]{{5,10}}",
        "Deployment": f"{name}(-[a-z0-9]{{5,10}}){{1,2}}",
        "DaemonSet": f"{name}-[a-z0-9]{{5}}",
        "StatefulSet": f"{name}-[0-9]+",
    }
    base_cond: dict[str, str] = {"bcs_cluster_id": bcs_cluster_id, "namespace": namespace}
    for workload_kind, pod_name_reg in kind_pod_reg_map.items():
        # 为什么采取模糊匹配？因为有类似 xxxDeployment 的 CRD 存在。
        if kind not in workload_kind:
            continue

        # Workload 事件（例如 Deployment 滚服），实际会触发管控对象（ReplicaSet、Pod）的变更，产生对应级别的 k8s 事件，
        # 即错误事件可能发生在 Workload 所管理的更基础的 k8s 对象，例如 Pod 重启失败、拉取镜像异常等，此处需要一并关联展示。
        q |= Q(**base_cond, kind="Pod", name__req=pod_name_reg)
        if kind in "Deployment":
            q |= Q(**base_cond, kind="HorizontalPodAutoscaler", name=name) | Q(
                **base_cond, kind="ReplicaSet", name__req=f"{name}-[a-z0-9]{{5,10}}"
            )

        # 至多匹配一次
        break
    return q


DOMAIN_CONF_HANDLER_MAP: dict[str, Callable[[dict[str, Any]], Q]] = {
    EventDomain.CICD.value: cicd_cond_handler,
    EventDomain.K8S.value: k8s_cond_handler,
}


def filter_by_relation(
    q: QueryConfigBuilder, relation: dict[str, Any], data_labels_map: dict[str, str], table: str | None = None
) -> QueryConfigBuilder:
    q = q.table(table or relation["table"])
    domain, __ = EVENT_ORIGIN_MAPPING.get(data_labels_map.get(relation["table"]), DEFAULT_EVENT_ORIGIN)
    cond_handler: Callable[[dict[str, Any]], Q] = DOMAIN_CONF_HANDLER_MAP.get(domain, default_cond_handler)
    if relation["relations"]:
        q = q.filter(Q() | reduce(operator.or_, [cond_handler(cond) for cond in relation["relations"]]))
    return q


def process_query_config(
    bk_biz_id: int, origin_query_config: dict[str, Any], event_relations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    filtered_tables: set[str] = {relation["table"] for relation in event_relations}
    data_labels_map: dict[str, str] = get_data_labels_map(bk_biz_id, filtered_tables)

    base_q: QueryConfigBuilder = get_q_from_query_config(
        {**origin_query_config, "data_type_label": DataTypeLabel.EVENT, "data_source_label": DataSourceLabel.BK_APM}
    )
    for metric in origin_query_config.get("metrics") or []:
        base_q = base_q.metric(**metric)

    if origin_query_config.get("interval"):
        base_q = base_q.interval(origin_query_config["interval"])

    queryset: UnifyQuerySet = UnifyQuerySet().start_time(0).end_time(0)
    for relation in event_relations:
        if relation["table"] == EventCategory.CICD_EVENT.value and not relation["relations"]:
            # CICD 事件必须有关联条件才能查询。
            continue

        if relation["table"] == EventCategory.K8S_EVENT.value:
            cluster_conditions_map: dict[str, list[dict[str, Any]]] = {}
            for cond in relation["relations"]:
                cluster_id: str | None = cond.get("bcs_cluster_id")
                if not cluster_id:
                    continue
                cluster_conditions_map.setdefault(cluster_id, []).append(cond)

            cluster_table_map: dict[str, str] = get_cluster_table_map(tuple(sorted(cluster_conditions_map.keys())))
            if not cluster_table_map:
                continue

            for cluster_id, conditions in cluster_conditions_map.items():
                table: str | None = cluster_table_map.get(cluster_id)
                if not table:
                    continue

                # 集群条件已能确定查询 RT，直接指定加快检索速度
                q = filter_by_relation(
                    base_q, {"table": relation["table"], "relations": conditions}, data_labels_map, table
                )
                queryset = queryset.add_query(q)

            continue

        queryset = queryset.add_query(filter_by_relation(base_q, relation, data_labels_map))

    return [
        query_config
        for query_config in queryset.config["query_configs"]
        if "data_type_label" in query_config and "data_source_label" in query_config
    ]


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
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)


class EventLogsRequestSerializer(event_serializers.EventLogsRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)


class EventViewConfigRequestSerializer(event_serializers.EventViewConfigRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        data_sources: list[dict[str, str]] = []
        for relation in EventHandler.fetch_relations(attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]):
            table: str = relation["table"]
            data_sources.append(
                {"table": table, "data_type_label": DataTypeLabel.EVENT, "data_source_label": DataSourceLabel.BK_APM}
            )

        attrs["data_sources"] = data_sources
        return super().validate(attrs)


class EventTopKRequestSerializer(event_serializers.EventTopKRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)


class EventTotalRequestSerializer(event_serializers.EventTotalRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)


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


class EventGetTagConfigRequestSerializer(BaseEventRequestSerializer):
    key = serializers.CharField(label="配置 Key", required=True)


class EventUpdateTagConfigRequestSerializer(EventGetTagConfigRequestSerializer):
    config = serializers.DictField(label="配置", required=True)


class EventDownloadTopKRequestSerializer(
    event_serializers.EventDownloadTopKRequestSerializer, EventTopKRequestSerializer
):
    def validate(self, attrs):
        return super().validate(attrs)


class EventStatisticsGraphRequestSerializer(
    event_serializers.EventStatisticsGraphRequestSerializer, BaseEventRequestSerializer
):
    def validate(self, attrs):
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)


class EventStatisticsInfoRequestSerializer(
    event_serializers.EventStatisticsInfoRequestSerializer, BaseEventRequestSerializer
):
    def validate(self, attrs):
        event_relations: list[dict[str, Any]] = EventHandler.fetch_relations(
            attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
        )
        attrs["query_configs"] = process_query_config(attrs["bk_biz_id"], attrs["query_configs"][0], event_relations)
        return super().validate(attrs)
