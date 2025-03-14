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
from typing import Any, Dict, List
from urllib.parse import urlencode

import settings

from ...constants import (
    DisplayFieldType,
    EventCategory,
    EventDomain,
    EventScenario,
    EventSource,
    SystemEventTypeEnum,
)
from ...utils import create_host_info, generate_time_range, get_field_label
from .base import BaseEventProcessor


class HostEventProcessor(BaseEventProcessor):
    def __init__(self, systme_cluster_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.system_cluster_context = systme_cluster_context

    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == (
            EventDomain.SYSTEM.value,
            EventSource.HOST.value,
        )

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            handler = {
                SystemEventTypeEnum.OOM.value: OOMHandler,
                SystemEventTypeEnum.DiskFull.value: DiskFullHandler,
                SystemEventTypeEnum.DiskReadOnly.value: DiskReadOnlyHandler,
                SystemEventTypeEnum.PingUnreachable.value: PingUnreachableHandler,
                SystemEventTypeEnum.CoreFile.value: CoreFileHandler,
                SystemEventTypeEnum.AgentLost.value: AgentLostHandler,
            }.get(origin_event["event_name"]["value"])
            if handler is None:
                processed_events.append(origin_event)
                continue
            origin_data = origin_event["origin_data"]
            host_info = create_host_info(
                origin_data,
                [
                    "event.content",
                    "target",
                    "bk_biz_id",
                    "bk_target_cloud_id",
                    "bk_cloud_id",
                    "bk_target_ip",
                    "ip",
                    "time",
                ],
            )
            host_info.update(handler.add_other_fields(origin_data))
            # 生成目标
            target = handler.create_target(host_info)
            processed_event = copy.deepcopy(origin_event)

            # 根据 cloud_id 换取 cloud_name
            bk_target_cloud_id = int(host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"] or 0)
            bk_cloud_name = (
                self.system_cluster_context.fetch([{"bk_cloud_id": bk_target_cloud_id}])
                .get(bk_target_cloud_id, {})
                .get("bk_cloud_name", "")
            )
            bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]

            processed_event["target"] = {
                "alias": f"{bk_cloud_name}[{bk_target_cloud_id}] / {bk_target_ip}",
                "value": target["value"],
                "type": target["type"],
                "scenario": target["scenario"],
                "url": target["url"],
            }

            event_name = origin_event["event_name"]
            processed_event["event.content"] = {
                "value": origin_event["event.content"]["value"],
                "alias": handler.create_event_content_alias(host_info),
                "detail": handler.create_detail(host_info),
            }

            processed_event["event_name"] = {
                "value": event_name["value"],
                "alias": get_field_label(event_name["value"], EventCategory.SYSTEM_EVENT.value),
            }
            processed_events.append(processed_event)
        return processed_events


class SpecificHostEventHandler:
    @classmethod
    def add_other_fields(cls, host_info: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def create_event_content_alias(cls, host_info: Dict[str, Any]) -> str:
        raise NotImplementedError()

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def create_target(cls, host_info) -> Dict[str, Any]:
        return {
            "label": host_info["target"]["label"],
            "value": host_info["target"]["value"],
            "type": DisplayFieldType.LINK.value,
            "scenario": EventScenario.HOST_MONITOR.value,
            "url": cls.generate_url(host_info),
        }

    @classmethod
    def generate_url(cls, host_info):
        start_time, end_time = generate_time_range(host_info["time"]["value"])
        ip_param = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        if not ip_param:
            return ""
        cloud_id_param = int(host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]) or 0
        params = {
            "from": start_time,
            "to": end_time,
        }
        bk_biz_id = host_info["bk_biz_id"]["value"]
        return (
            f"{settings.BK_MONITOR_HOST}?bizId={bk_biz_id}#/performance/detail/{ip_param}-"
            f"{cloud_id_param}?{urlencode(params)}"
        )


class OOMHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["process", "task_memcg"])

    @classmethod
    def create_event_content_alias(
        cls,
        host_info: Dict[str, Any],
    ) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        process = host_info["process"]["value"]
        return f"主机（{bk_target_cloud_id}-{bk_target_ip}）进程（{process}）OOM"

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "target": cls.create_target(host_info),
            "process": {
                "label": host_info["process"]["label"],
                "value": host_info["process"]["value"],
            },
            "task_memcg": {
                "label": host_info["task_memcg"]["label"],
                "value": host_info["task_memcg"]["value"],
            },
        }


class DiskFullHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["disk", "fstype", "file_system"])

    @classmethod
    def create_event_content_alias(cls, host_info: Dict[str, Any]) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        disk = host_info["disk"]["value"]
        return f"主机（{bk_target_cloud_id}-{bk_target_ip}）磁盘（{disk}）已满"

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "target": cls.create_target(host_info),
            "fstype": {"label": host_info["fstype"]["label"], "value": host_info["fstype"]["value"]},
            "file_system": {
                "label": host_info["file_system"]["label"],
                "value": host_info["file_system"]["value"],
            },
        }


class DiskReadOnlyHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["fs", "position", "type"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        fs = host_info["fs"]["value"]
        dimension_type = host_info["type"]["value"]
        return f"主机（{bk_target_cloud_id}-{bk_target_ip}）磁盘（{fs}）只读，原因：{dimension_type}"

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "target": cls.create_target(host_info),
            "position": {"label": host_info["position"]["label"], "value": host_info["position"]["value"]},
            "fs": {"label": host_info["fs"]["label"], "value": host_info["fs"]["value"]},
            "type": {"label": host_info["type"]["label"], "value": host_info["type"]["value"]},
        }


class PingUnreachableHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, [])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        return f"主机（{bk_target_cloud_id}-{bk_target_ip}）Ping 不可达"

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {"target": cls.create_target(host_info)}


class AgentLostHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["bk_agent_id"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        return f"主机（{bk_target_cloud_id}-{bk_target_ip}）Agent 失联"

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "target": cls.create_target(host_info),
            "bk_agent_id": {"label": host_info["bk_agent_id"]["label"], "value": host_info["bk_agent_id"]["value"]},
        }


class CoreFileHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["executable", "signal", "corefile"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        bk_target_ip = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
        bk_target_cloud_id = host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"]
        executable = host_info["executable"]["value"]
        signal = host_info["signal"]["value"]
        core_file = host_info["corefile"]["value"]
        core_file_info = f"产生 corefile（{core_file}）"

        if executable and signal:
            alias = f"主机（{bk_target_cloud_id}-{bk_target_ip}）进程（{executable}）因异常信号（{signal}）{core_file_info}"
        elif executable:
            alias = f"主机（{bk_target_cloud_id}-{bk_target_ip}）进程（{executable}）{core_file_info}"
        elif signal:
            alias = f"主机（{bk_target_cloud_id}-{bk_target_ip}）因异常信号（{signal}）{core_file_info}"
        else:
            alias = f"主机（{bk_target_cloud_id}-{bk_target_ip}）{core_file_info}"
        return alias

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "target": cls.create_target(host_info),
            "corefile": {"label": host_info["corefile"]["label"], "value": host_info["corefile"]["value"]},
            "executable": {"label": host_info["executable"]["label"], "value": host_info["executable"]["value"]},
        }
