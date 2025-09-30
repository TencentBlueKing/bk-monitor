# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import logging
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from ...constants import (
    DIMENSION_PREFIX,
    SYSTEM_EVENT_TRANSLATIONS,
    DisplayFieldType,
    EventDomain,
    EventScenario,
    EventSource,
    SystemEventTypeEnum,
)
from ...utils import create_host_info, generate_time_range, get_field_label
from .base import BaseEventProcessor

logger = logging.getLogger(__name__)


class HostEventProcessor(BaseEventProcessor):
    def __init__(self, system_cluster_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.system_cluster_context = system_cluster_context

    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return any(f"{DIMENSION_PREFIX}{field}" in origin_event["origin_data"] for field in ["bk_target_ip", "ip"]) or (
            origin_event["_meta"]["__domain"],
            origin_event["_meta"]["__source"],
        ) == (
            EventDomain.SYSTEM.value,
            EventSource.HOST.value,
        )

    @classmethod
    def _generate_url(cls, host_info):
        start_time, end_time = generate_time_range(host_info["time"]["value"])
        if not host_info["ip"]["value"]:
            return ""
        params = {
            "from": start_time,
            "to": end_time or "now",
        }
        return "{base_url}?bizId={biz_id}#/performance/detail/{ip}-{cloud_id}?{params}".format(
            base_url=settings.BK_MONITOR_HOST,
            biz_id=host_info["bk_biz_id"]["value"],
            ip=host_info["ip"]["value"],
            cloud_id=host_info["bk_cloud_id"]["value"],
            params=urlencode(params),
        )

    def _get_target_alias(self, host_info: Dict[str, Dict[str, Any]]) -> str:
        bk_cloud_id: int = host_info["bk_cloud_id"]["value"]
        return "{}[{}] / {}".format(
            self.system_cluster_context.fetch([{"bk_cloud_id": bk_cloud_id}])
            .get(bk_cloud_id, {})
            .get("bk_cloud_name", ""),
            bk_cloud_id,
            host_info["ip"]["value"],
        )

    def create_target(self, host_info) -> Dict[str, Any]:
        return {
            "label": host_info["target"]["label"],
            "value": host_info["target"]["value"],
            "alias": self._get_target_alias(host_info),
            "type": DisplayFieldType.LINK.value,
            "scenario": EventScenario.HOST_MONITOR.value,
            "url": self._generate_url(host_info),
        }

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue
            handler = {
                SystemEventTypeEnum.OOM.value: OOMHandler,
                SystemEventTypeEnum.DiskFull.value: DiskFullHandler,
                SystemEventTypeEnum.DiskReadOnly.value: DiskReadOnlyHandler,
                SystemEventTypeEnum.PingUnreachable.value: PingUnreachableHandler,
                SystemEventTypeEnum.CoreFile.value: CoreFileHandler,
                SystemEventTypeEnum.AgentLost.value: AgentLostHandler,
            }.get(origin_event["event_name"]["value"], DefaultHostHandler)
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
            host_info["ip"]["value"] = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
            try:
                host_info["bk_cloud_id"]["value"] = int(
                    host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"] or 0
                )
            except ValueError:
                # 不符合预期的事件也需要展示，以默认值的形式代替报错。
                host_info["bk_cloud_id"]["value"] = 0

            host_info.update(handler.add_other_fields(origin_data))

            processed_event = copy.deepcopy(origin_event)
            processed_event["target"] = self.create_target(host_info)

            event_content_alias = handler.create_event_content_alias(host_info)
            processed_event["event.content"] = {
                "value": origin_event["event.content"]["value"],
                "alias": event_content_alias,
                "detail": {
                    **handler.create_detail(host_info),
                    "target": processed_event["target"],
                    "event.content": {
                        "label": get_field_label("event.content"),
                        "value": origin_event["event.content"]["value"],
                        "alias": event_content_alias,
                    },
                },
            }

            event_name_value = origin_event["event_name"]["value"]
            processed_event["event_name"] = {
                "value": event_name_value,
                "alias": _("{alias}（{name}）").format(
                    alias=SYSTEM_EVENT_TRANSLATIONS.get(event_name_value), name=event_name_value
                )
                if SYSTEM_EVENT_TRANSLATIONS.get(event_name_value)
                else event_name_value,
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


class OOMHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["process", "task_memcg"])

    @classmethod
    def create_event_content_alias(
        cls,
        host_info: Dict[str, Any],
    ) -> str:
        return _("主机（{}-{}）进程（{}）OOM").format(
            host_info["bk_cloud_id"]["value"], host_info["ip"]["value"], host_info["process"]["value"]
        )

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "process": host_info["process"],
            "task_memcg": host_info["task_memcg"],
        }


class DiskFullHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["disk", "fstype", "file_system"])

    @classmethod
    def create_event_content_alias(cls, host_info: Dict[str, Any]) -> str:
        return _("主机（{}-{}）磁盘（{}）已满").format(
            host_info["bk_cloud_id"]["value"], host_info["ip"]["value"], host_info["disk"]["value"]
        )

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {
            "fstype": host_info["fstype"],
            "file_system": host_info["file_system"],
        }


class DiskReadOnlyHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["fs", "position", "type"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        return _("主机（{}-{}）磁盘（{}）只读，原因：{}").format(
            host_info["bk_cloud_id"]["value"],
            host_info["ip"]["value"],
            host_info["fs"]["value"],
            host_info["type"]["value"],
        )

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {"position": host_info["position"], "fs": host_info["fs"], "type": host_info["type"]}


class PingUnreachableHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, [])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        return _("主机（{}-{}）Ping 不可达").format(host_info["bk_cloud_id"]["value"], host_info["ip"]["value"])

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {}


class AgentLostHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["bk_agent_id"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        return _("主机（{}-{}）Agent 失联").format(host_info["bk_cloud_id"]["value"], host_info["ip"]["value"])

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {"bk_agent_id": host_info["bk_agent_id"]}


class CoreFileHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["executable", "signal", "corefile"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        ip = host_info["ip"]["value"]
        bk_cloud_id = host_info["bk_cloud_id"]["value"]
        executable = host_info["executable"]["value"]
        signal = host_info["signal"]["value"]
        core_file = _("产生 corefile（{}）").format(host_info["corefile"]["value"])

        if executable and signal:
            alias = _("主机（{}-{}）进程（{}）因异常信号（{}）{}").format(bk_cloud_id, ip, executable, signal, core_file)
        elif executable:
            alias = _("主机（{}-{}）进程（{}）{}").format(bk_cloud_id, ip, executable, core_file)
        elif signal:
            alias = _("主机（{}-{}）因异常信号（{}）{}").format(bk_cloud_id, ip, signal, core_file)
        else:
            alias = _("主机（{}-{}）{}").format(bk_cloud_id, ip, core_file)
        return alias

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {"corefile": host_info["corefile"], "executable": host_info["executable"]}


class DefaultHostHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, [])

    @classmethod
    def create_event_content_alias(cls, host_info: Dict[str, Any]) -> str:
        return host_info["event.content"]["alias"]

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {}
