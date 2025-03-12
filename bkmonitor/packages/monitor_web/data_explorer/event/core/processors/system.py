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
    DEFAULT_BK_TARGET_CLOUD_ID,
    DIMENSION_PREFIX,
    SYSTEM_EVENT_TRANSLATIONS,
    DisplayFieldType,
    EventDomain,
    EventScenario,
    EventSource,
    SystemEventTypeEnum,
    SystemFieldLabel,
)
from ...utils import generate_time_range
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
        for processor in self.get_processors():
            origin_events = processor.process(origin_events)
        return origin_events

    @classmethod
    def generate_url(cls, bk_biz_id, bk_target_ip, ip, bk_target_cloud_id, bk_cloud_id, start_time, end_time):
        base_url = settings.BK_MONITOR_HOST
        ip_param = bk_target_ip or ip
        if not ip_param:
            return ""
        cloud_id_param = bk_target_cloud_id or bk_cloud_id or DEFAULT_BK_TARGET_CLOUD_ID
        params = {
            "from": start_time,
            "to": end_time,
        }
        return f"{base_url}?bizId={bk_biz_id}#/performance/detail/{ip_param}-{cloud_id_param}?{urlencode(params)}"

    def process_event(self, origin_event: Dict[str, Any]) -> Dict[str, Any]:
        processed_event = copy.copy(origin_event)
        event_content = origin_event["event.content"]
        origin_data = origin_event["origin_data"]

        # 生成目标
        target = self.create_target(origin_data)
        # 生成事件别名
        event_content_alias = self.create_event_content_alias(origin_data)
        # 根据 cloud_id 换取 cloud_name
        bk_target_cloud_id = int(
            origin_data.get(f"{DIMENSION_PREFIX}bk_target_cloud_id")
            or origin_data.get(f"{DIMENSION_PREFIX}bk_cloud_id", "")
        )
        bk_cloud_name = self.system_cluster_context.fetch([{"bk_cloud_id": bk_target_cloud_id}])[bk_target_cloud_id][
            "bk_cloud_name"
        ]
        bk_target_ip = origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "") or origin_data.get(
            f"{DIMENSION_PREFIX}ip", ""
        )
        alias = f"{bk_cloud_name}[{bk_target_cloud_id}] / {bk_target_ip}"
        # 生成 detail 内容
        detail = self.create_detail(origin_data, target)

        processed_event["target"] = {
            "alias": alias,
            "value": target["value"],
            "type": target["type"],
            "scenario": target["scenario"],
            "url": target["url"],
        }

        event_name = origin_event["event_name"]
        processed_event["event.content"] = {
            "value": event_content["value"],
            "alias": event_content_alias,
            "detail": detail,
        }

        processed_event["event_name"] = {
            "value": event_name["value"],
            "alias": self.get_event_name_alias(event_name["value"]),
        }
        return processed_event

    def create_target(self, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        start_time, end_time = generate_time_range(origin_data.get("time", ""))
        url = self.generate_url(
            origin_data.get(f"{DIMENSION_PREFIX}bk_biz_id", ""),
            origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", ""),
            origin_data.get(f"{DIMENSION_PREFIX}ip", ""),
            origin_data.get(f"{DIMENSION_PREFIX}bk_target_cloud_id"),
            origin_data.get(f"{DIMENSION_PREFIX}bk_cloud_id", ""),
            start_time,
            end_time,
        )
        return {
            "label": SystemFieldLabel.TARGET.value,
            "value": origin_data.get("target", ""),
            "type": DisplayFieldType.LINK.value,
            "scenario": EventScenario.HOST_MONITOR.value,
            "url": url,
        }

    @classmethod
    def get_event_name_alias(cls, event_name: str) -> str:
        return SYSTEM_EVENT_TRANSLATIONS.get(event_name, event_name)

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        # 需要在子类中重写
        raise NotImplementedError()

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        # 需要在子类中重写
        raise NotImplementedError()

    def get_processors(self):
        return [
            OOMEventProcessor(self.system_cluster_context),
            DiskFullEventProcessor(self.system_cluster_context),
            DiskReadOnlyProcessor(self.system_cluster_context),
            PingUnreachableProcessor(self.system_cluster_context),
            AgentLostProcessor(self.system_cluster_context),
            CoreFileProcessor(self.system_cluster_context),
        ]


class SpecificHostEventProcessor(HostEventProcessor):
    EVENT_NAME = None

    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        if not super()._need_process(origin_event):
            return False
        return origin_event["origin_data"]["event_name"] == cls.EVENT_NAME

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.process_event(event) if self._need_process(event) else event for event in origin_events]

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        raise NotImplementedError()

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()


class OOMEventProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.OOM.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        return (
            f'主机（{origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")}） '
            f'进程（{origin_data.get(f"{DIMENSION_PREFIX}process", "")}） OOM'
        )

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target": target,
            "process": {
                "label": SystemFieldLabel.PROCESS.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}process", ""),
            },
            "task_memcg": {
                "label": SystemFieldLabel.TASK_MEMCG.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}task_memcg", ""),
            },
        }


class DiskFullEventProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.DiskFull.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        return (
            f'主机（{origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")}） '
            f'磁盘（{origin_data[f"{DIMENSION_PREFIX}disk"]}） 已满'
        )

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target": target,
            "fstype": {
                "label": SystemFieldLabel.FSTYPE.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}fstype", ""),
            },
            "file_system": {
                "label": SystemFieldLabel.FILE_SYSTEM.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}file_system", ""),
            },
        }


class DiskReadOnlyProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.DiskReadOnly.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        return (
            f'主机（{origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")}）'
            f'磁盘（{origin_data.get(f"{DIMENSION_PREFIX}fs", "")}）只读，原因：{origin_data.get(f"{DIMENSION_PREFIX}type", "")}'
        )

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target": target,
            "position": {
                "label": SystemFieldLabel.POSITION.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}position", ""),
            },
            "fs": {
                "label": SystemFieldLabel.FS.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}fs", ""),
            },
            "type": {"label": SystemFieldLabel.TYPE.value, "value": origin_data.get(f"{DIMENSION_PREFIX}type", "")},
        }


class PingUnreachableProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.PingUnreachable.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        return f'主机（{origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")}）Ping 不可达'

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {"target": target}


class AgentLostProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.AgentLost.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> str:
        return f'主机（{origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")}）Agent 失联'

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target": target,
            "bk_agent_id": {
                "label": SystemFieldLabel.BK_AGENT_ID.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}bk_agent_id", ""),
            },
        }


class CoreFileProcessor(SpecificHostEventProcessor):
    EVENT_NAME = SystemEventTypeEnum.CoreFile.value

    def create_event_content_alias(self, origin_data: Dict[str, Any]) -> Dict[str, str]:
        bk_target_ip = origin_data.get(f"{DIMENSION_PREFIX}bk_target_ip", "")
        executable = origin_data.get(f"{DIMENSION_PREFIX}executable", "")
        signal = origin_data.get(f"{DIMENSION_PREFIX}signal", "")
        core_file_info = f"产生 corefile（{origin_data.get(f'{DIMENSION_PREFIX}corefile', '')}）"

        if executable and signal:
            alias = f"主机（{bk_target_ip}）进程（{executable}）因异常信号（{signal}）{core_file_info}"
        elif executable:
            alias = f"主机（{bk_target_ip}）进程（{executable}）{core_file_info}"
        elif signal:
            alias = f"主机（{bk_target_ip}）因异常信号（{signal}）{core_file_info}"
        else:
            alias = f"主机（{bk_target_ip}）{core_file_info}"

        return {"alias": alias}

    def create_detail(self, origin_data: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target": target,
            "corefile": {
                "label": SystemFieldLabel.CORE_FILE.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}corefile", ""),
            },
            "executable": {
                "label": SystemFieldLabel.EXECUTABLE.value,
                "value": origin_data.get(f"{DIMENSION_PREFIX}executable", ""),
            },
        }
