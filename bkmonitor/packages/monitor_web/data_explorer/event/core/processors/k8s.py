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
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.utils.translation import gettext as _

from ...constants import (
    K8S_EVENT_TRANSLATIONS,
    NEVER_REFRESH_INTERVAL,
    ContainerMonitorMetricsType,
    ContainerMonitorTabType,
    DisplayFieldType,
    EventCategory,
    EventDomain,
    EventScenario,
    EventSource,
)
from ...utils import create_k8s_info, generate_time_range, get_field_label
from .base import BaseEventProcessor


class K8sEventProcessor(BaseEventProcessor):
    def __init__(self, bcs_cluster_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bcs_cluster_context = bcs_cluster_context

    @classmethod
    def _need_process(cls, origin_event: dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == (
            EventDomain.K8S.value,
            EventSource.BCS.value,
        )

    def process(self, origin_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        processed_events: list[dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue
            processed_event = copy.deepcopy(origin_event)
            self.set_fields(processed_event)
            processed_events.append(processed_event)

        return processed_events

    def set_fields(self, processed_event: dict[str, Any]) -> None:
        start_time, end_time = generate_time_range(processed_event["time"]["value"])
        k8s_info = create_k8s_info(
            processed_event["origin_data"],
            ["bk_biz_id", "event_name", "target", "bcs_cluster_id", "namespace", "name", "kind", "host"],
        )
        # 设置详情字段
        self.set_detail_fields(processed_event, k8s_info, start_time, end_time)
        # 设置事件内容
        self.set_event_content(processed_event)
        # 设置目标
        self.set_target(processed_event, k8s_info, start_time, end_time)
        # 设置事件名
        self.set_event_name(processed_event, k8s_info)

    @classmethod
    def set_event_content(cls, processed_event):
        processed_event["event.content"]["detail"]["event.content"] = {
            "label": get_field_label("event.content", EventCategory.K8S_EVENT.value),
            "value": processed_event["event.content"]["value"],
            "alias": processed_event["event.content"]["alias"],
        }

    @classmethod
    def set_target(cls, processed_event, k8s_info, start_time, end_time):
        bcs_cluster_id = k8s_info["bcs_cluster_id"]["value"]
        namespace = k8s_info["namespace"]["value"]
        name = k8s_info["name"]["value"]
        kind = k8s_info["kind"]["value"]

        processed_event["target"] = {
            "value": k8s_info["target"]["value"],
            "alias": f"{bcs_cluster_id}/{namespace}/{kind}/{name}",
            "url": cls.generate_url("workload", k8s_info, start_time, end_time),
            "scenario": EventScenario.CONTAINER_MONITOR.value,
        }

    @classmethod
    def set_event_name(cls, event, k8s_info):
        event_name_value = k8s_info["event_name"]["value"]
        event_name_alias = K8S_EVENT_TRANSLATIONS.get(k8s_info["kind"]["value"], {}).get(event_name_value)
        event["event_name"] = {
            "value": event_name_value,
            "alias": _("{alias}（{name}）").format(alias=event_name_alias, name=event_name_value)
            if event_name_alias
            else event_name_value,
        }

    def set_detail_fields(
        self,
        processed_event: dict[str, Any],
        k8s_info,
        start_time: int,
        end_time: int,
    ) -> None:
        def create_detail_field(field: str, alias: str, url: str) -> dict[str, str]:
            field_value = k8s_info[field]["value"]
            if not field_value:
                return {}
            return {
                "label": k8s_info[field]["label"],
                "value": field_value,
                "alias": alias,
                "type": DisplayFieldType.LINK.value,
                "scenario": EventScenario.CONTAINER_MONITOR.value,
                "url": url,
            }

        # 处理集群信息
        detail = processed_event["event.content"]["detail"]
        bcs_cluster_id = k8s_info["bcs_cluster_id"]["value"]
        bk_biz_id = k8s_info["bk_biz_id"]["value"]
        namespace = k8s_info["namespace"]["value"]
        name = k8s_info["name"]["value"]
        host = k8s_info["host"]["value"]
        kind = k8s_info["kind"]["value"]
        if bcs_cluster_id:
            detail["bcs_cluster_id"] = create_detail_field(
                "bcs_cluster_id",
                self.bcs_cluster_context.fetch([{"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id}])
                .get(f"{bk_biz_id}::{bcs_cluster_id}", {})
                .get("bcs_cluster_name", bcs_cluster_id),
                self.generate_url("cluster", k8s_info, start_time, end_time),
            )
        # 处理命名空间信息
        if namespace:
            detail["namespace"] = create_detail_field(
                "namespace", namespace, self.generate_url("namespace", k8s_info, start_time, end_time)
            )
        # 处理名称信息
        if name:
            detail["name"] = create_detail_field(
                "name",
                f"{kind}/{name}" if kind else name,
                # 统一使用 kind 表示不同监控指标的名称所在层级
                self.generate_url("kind", k8s_info, start_time, end_time),
            )
        # 如果有 host 字段，补充容器监控容量界面的 url 到 detail 内
        if host:
            detail["host"] = create_detail_field(
                "host",
                host,
                self._generate_capacity_url(k8s_info, start_time, end_time, host),
            )

    @classmethod
    def generate_url(cls, level: str, k8s_info: dict[str, Any], start_time: int, end_time: int) -> str:
        kind: str = k8s_info["kind"]["value"]
        name: str = k8s_info["name"]["value"]
        namespace = k8s_info["namespace"]["value"]
        # TODO(yamltdg): 等后续容器监控支持存储等新功能再完善对应的跳转。
        # Node 跳转容器监控容量界面
        if kind == "Node":
            return cls._generate_capacity_url(k8s_info, start_time, end_time, name)
        if kind in ["Service", "Endpoints", "Ingress"]:
            return cls._generate_network_url(level, k8s_info, start_time, end_time, namespace, name, kind)
        # 先默认走容器监控性能页面
        return cls._generate_performance_url(level, k8s_info, start_time, end_time, namespace, name, kind)

    @classmethod
    def _generate_url(
        cls,
        k8s_info: dict[str, Any],
        start_time,
        end_time,
        filter_by: dict[str, Any],
        group_by: list[str],
        tab_info: dict[str, str],
    ) -> str:
        params = {
            "from": start_time,
            "to": end_time or "now",
            "refreshInterval": NEVER_REFRESH_INTERVAL,
            "cluster": k8s_info["bcs_cluster_id"]["value"],
            "filterBy": json.dumps(filter_by),
            "groupBy": json.dumps(group_by),
            "scene": tab_info["scene"],
            "activeTab": tab_info["activeTab"],
        }
        bk_biz_id = k8s_info["bk_biz_id"]["value"]
        return f"{settings.BK_MONITOR_HOST}?bizId={bk_biz_id}#/k8s-new?{urlencode(params)}"

    @classmethod
    def _generate_performance_url(
        cls, level: str, k8s_info: dict[str, Any], start_time, end_time, namespace, name, kind
    ) -> str:
        """
        生成容器监控性能界面url
        """
        filter_by = {"namespace": [], "workload": [], "pod": [], "container": []}
        tab_info = {
            "scene": ContainerMonitorMetricsType.PERFORMANCE.value,
            "activeTab": ContainerMonitorTabType.LIST.value,
        }
        if level == "cluster":
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, ["namespace"], tab_info)

        if namespace:
            filter_by["namespace"].append(namespace)

        if level == "namespace":
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, ["namespace", "workload"], tab_info)

        if not (name and kind):
            return ""

        for workload_type in [
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "Job",
            "CronJob",
            "ReplicaSet",
            "HorizontalPodAutoscaler",
        ]:
            # 模糊匹配，从而支持更多类似 GameDeployment 的 CRD workload。
            if workload_type not in kind:
                continue

            # ReplicaSet 是 Deployment 的版本控制器，一个 Pod 由 {DeploymentName}-{ReplicaSetId}-{PodId} 组成，其中
            # {DeploymentName}-{ReplicaSetId} 为 ReplicaSet Name，由于 ReplicaSet 非可见资源，截断取 Deployment 生成链接。
            if workload_type == "ReplicaSet":
                kind = "Deployment"
                name = "-".join(name.split("-")[:-1])

            if workload_type == "HorizontalPodAutoscaler":
                kind = "Deployment"

            # case 1：workload 类型
            filter_by["workload"].append(f"{kind}:{name}")
            return cls._generate_url(
                k8s_info, start_time, end_time, filter_by, ["namespace", "workload", "pod"], tab_info
            )

        if kind == "Pod":
            filter_by["pod"].append(name)
            return cls._generate_url(
                k8s_info, start_time, end_time, filter_by, ["namespace", "workload", "pod", "container"], tab_info
            )

        return ""

    @classmethod
    def _generate_network_url(
        cls, level: str, k8s_info: dict[str, Any], start_time, end_time, namespace, name, kind
    ) -> str:
        """ "
        生成容器监控网络界面url
        """
        tab_info: dict[str, str] = {
            "scene": ContainerMonitorMetricsType.NETWORK.value,
            "activeTab": ContainerMonitorTabType.LIST.value,
        }
        filter_by: dict[str, list[str]] = {"namespace": [], "ingress": [], "service": [], "pod": []}
        group_by = ["namespace", "pod"]
        if level == "cluster":
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, ["namespace"], tab_info)

        if namespace:
            filter_by["namespace"].append(namespace)

        if level == "namespace":
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, group_by, tab_info)

        if not (name and kind):
            return ""

        if kind == "Ingress":
            filter_by["ingress"].append(name)
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, group_by, tab_info)

        if kind in ["Service", "Endpoints"]:
            filter_by["service"].append(name)
            return cls._generate_url(k8s_info, start_time, end_time, filter_by, group_by, tab_info)

    @classmethod
    def _generate_capacity_url(cls, k8s_info: dict[str, Any], start_time, end_time, name) -> str:
        """
        生成容器监控容量界面url
        """
        tab_info: dict[str, str] = {
            "scene": ContainerMonitorMetricsType.CAPACITY.value,
            "activeTab": ContainerMonitorTabType.LIST.value,
        }
        return cls._generate_url(k8s_info, start_time, end_time, {"node": [name]}, ["node"], tab_info)
