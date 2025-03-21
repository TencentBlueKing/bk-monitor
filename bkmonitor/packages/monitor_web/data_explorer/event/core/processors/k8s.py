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
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.conf import settings
from django.utils.translation import gettext as _

from ...constants import (
    K8S_EVENT_TRANSLATIONS,
    NEVER_REFRESH_INTERVAL,
    DisplayFieldType,
    EventCategory,
    EventDomain,
    EventScenario,
    EventSource,
)
from ...utils import create_workload_info, generate_time_range, get_field_label
from .base import BaseEventProcessor


class K8sEventProcessor(BaseEventProcessor):
    def __init__(self, bcs_cluster_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bcs_cluster_context = bcs_cluster_context

    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == (
            EventDomain.K8S.value,
            EventSource.BCS.value,
        )

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue
            processed_event = copy.deepcopy(origin_event)
            self.set_fields(processed_event)
            processed_events.append(processed_event)

        return processed_events

    def set_fields(self, processed_event: Dict[str, Any]) -> None:
        start_time, end_time = generate_time_range(processed_event["time"]["value"])
        workload_info = create_workload_info(
            processed_event["origin_data"],
            ["bk_biz_id", "event_name", "target", "bcs_cluster_id", "namespace", "name", "kind"],
        )
        # 设置详情字段
        self.set_detail_fields(processed_event, workload_info, start_time, end_time)
        # 设置事件内容
        self.set_event_content(processed_event)
        # 设置目标
        self.set_target(processed_event, workload_info, start_time, end_time)
        # 设置事件名
        self.set_event_name(processed_event, workload_info)

    @classmethod
    def set_event_content(cls, processed_event):
        processed_event["event.content"]["detail"]["event.content"] = {
            "label": get_field_label("event.content", EventCategory.K8S_EVENT.value),
            "value": processed_event["event.content"]["value"],
            "alias": processed_event["event.content"]["alias"],
        }

    @classmethod
    def set_target(cls, processed_event, workload_info, start_time, end_time):
        bcs_cluster_id = workload_info["bcs_cluster_id"]["value"]
        namespace = workload_info["namespace"]["value"]
        name = workload_info["name"]["value"]
        kind = workload_info["kind"]["value"]

        processed_event["target"] = {
            "value": workload_info["target"]["value"],
            "alias": f"{bcs_cluster_id}/{namespace}/{kind}/{name}",
            "url": cls.generate_url("workload", workload_info, start_time, end_time),
            "scenario": EventScenario.CONTAINER_MONITOR.value,
        }

    @classmethod
    def set_event_name(cls, event, workload_info):
        event_name_value = workload_info["event_name"]["value"]
        event_name_alias = K8S_EVENT_TRANSLATIONS.get(workload_info["kind"]["value"], {}).get(
            event_name_value, event_name_value
        )
        event["event_name"] = {
            "value": event_name_value,
            "alias": _("{alias}（{name}）").format(alias=event_name_alias, name=event_name_value),
        }

    def set_detail_fields(
        self,
        processed_event: Dict[str, Any],
        workload_info,
        start_time: int,
        end_time: int,
    ) -> None:
        def create_detail_field(field: str, alias: str, url: str) -> Dict[str, str]:
            field_value = workload_info[field]["value"]
            if not field_value:
                return {}
            return {
                "label": workload_info[field]["label"],
                "value": field_value,
                "alias": alias,
                "type": DisplayFieldType.LINK.value,
                "scenario": EventScenario.CONTAINER_MONITOR.value,
                "url": url,
            }

        # 处理集群信息
        detail = processed_event["event.content"]["detail"]
        bcs_cluster_id = workload_info["bcs_cluster_id"]["value"]
        bk_biz_id = workload_info["bk_biz_id"]["value"]
        namespace = workload_info["namespace"]["value"]
        name = workload_info["name"]["value"]
        kind = workload_info["kind"]["value"]
        if bcs_cluster_id:
            detail["bcs_cluster_id"] = create_detail_field(
                "bcs_cluster_id",
                self.bcs_cluster_context.fetch([{"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id}])
                .get(f"{bk_biz_id}::{bcs_cluster_id}", {})
                .get("bcs_cluster_name", bcs_cluster_id),
                self.generate_url("cluster", workload_info, start_time, end_time),
            )
        # 处理命名空间信息
        if namespace:
            detail["namespace"] = create_detail_field(
                "namespace", namespace, self.generate_url("namespace", workload_info, start_time, end_time)
            )
        # 处理名称信息
        if name:
            detail["name"] = create_detail_field(
                "name",
                f"{kind}/{name}" if kind else name,
                self.generate_url("workload", workload_info, start_time, end_time),
            )

    @classmethod
    def generate_url(cls, level: str, workload_info: Dict[str, Any], start_time: int, end_time: int) -> str:
        kind: str = workload_info["kind"]["value"]
        name: str = workload_info["name"]["value"]
        namespace = workload_info["namespace"]["value"]
        filter_by: Dict[str, List[str]] = {"namespace": [], "workload": [], "pod": [], "container": []}

        if level == "cluster":
            return cls._generate_url(workload_info, start_time, end_time, filter_by, ["namespace"])

        if namespace:
            filter_by["namespace"].append(namespace)

        if level == "namespace":
            return cls._generate_url(workload_info, start_time, end_time, filter_by, ["namespace", "workload"])

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
            return cls._generate_url(workload_info, start_time, end_time, filter_by, ["namespace", "workload", "pod"])

        if kind == "Pod":
            filter_by["pod"].append(name)
            return cls._generate_url(
                workload_info, start_time, end_time, filter_by, ["namespace", "workload", "pod", "container"]
            )

        if kind == "Node":
            return cls._generate_legacy_host_url(workload_info, name, start_time, end_time)

        # TODO(crayon): Service、Endpoints、Ingress 等新版容器监控支持后再完善跳转。
        return ""

    @classmethod
    def _generate_url(cls, workload_info, start_time, end_time, filter_by: Dict[str, Any], group_by: List[str]) -> str:
        params = {
            "from": start_time,
            "to": end_time,
            "refreshInterval": NEVER_REFRESH_INTERVAL,
            "cluster": workload_info["bcs_cluster_id"]["value"],
            "filterBy": json.dumps(filter_by),
            "groupBy": json.dumps(group_by),
        }
        bk_biz_id = workload_info["bk_biz_id"]["value"]
        return f"{settings.BK_MONITOR_HOST}?bizId={bk_biz_id}#/k8s-new?{urlencode(params)}"

    @classmethod
    def _generate_legacy_host_url(cls, workload_info, host: str, start_time, end_time) -> str:
        params = {
            "from": start_time,
            "to": end_time,
            "sceneId": "kubernetes",
            "dashboardId": "node",
            "sceneType": "detail",
            "queryData": json.dumps(
                {"selectorSearch": [{"bcs_cluster_id": workload_info["bcs_cluster_id"]["value"]}, {"name": host}]}
            ),
        }
        bk_biz_id = workload_info["bk_biz_id"]["value"]
        return f"{settings.BK_MONITOR_HOST}?bizId={bk_biz_id}#/k8s?{urlencode(params)}"
