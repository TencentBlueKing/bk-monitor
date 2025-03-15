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
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.utils.translation import gettext_lazy as _

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

logger = logging.getLogger(__name__)


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
            host_info["ip"]["value"] = host_info["bk_target_ip"]["value"] or host_info["ip"]["value"]
            try:
                host_info["bk_cloud_id"]["value"] = int(
                    host_info["bk_target_cloud_id"]["value"] or host_info["bk_cloud_id"]["value"] or 0
                )
            except ValueError as exc:
                logger.warning("failed to conversion time, err -> %s", exc)
                raise ValueError(_("类型转换失败: 无法将 '{}' 转换为整数").format(host_info["bk_cloud_id"]))

            host_info.update(handler.add_other_fields(origin_data))
            # 生成目标
            target = handler.create_target(host_info)
            processed_event = copy.deepcopy(origin_event)

            # 根据 cloud_id 换取 cloud_name
            bk_cloud_id = host_info["bk_cloud_id"]["value"]
            processed_event["target"] = {
                "alias": "{}[{}] / {}".format(
                    self.system_cluster_context.fetch([{"bk_cloud_id": bk_cloud_id}])
                    .get(bk_cloud_id, {})
                    .get("bk_cloud_name", ""),
                    bk_cloud_id,
                    host_info["ip"]["value"],
                ),
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
        if not host_info["ip"]["value"]:
            return ""
        params = {
            "from": start_time,
            "to": end_time,
        }
        return "{base_url}?bizId={biz_id}#/performance/detail/{ip}-{cloud_id}?{params}".format(
            base_url=settings.BK_MONITOR_HOST,
            biz_id=host_info["bk_biz_id"]["value"],
            ip=host_info["ip"]["value"],
            cloud_id=host_info["bk_cloud_id"]["value"],
            params=urlencode(params),
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
        return _("主机（{}-{}）进程（{}）OOM").format(
            host_info["bk_cloud_id"]["value"], host_info["ip"]["value"], host_info["process"]["value"]
        )

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
        return _("主机（{}-{}）磁盘（{}）已满").format(
            host_info["bk_cloud_id"]["value"], host_info["ip"]["value"], host_info["disk"]["value"]
        )

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
        return _("主机（{}-{}）磁盘（{}）只读，原因：{}").format(
            host_info["bk_cloud_id"]["value"],
            host_info["ip"]["value"],
            host_info["fs"]["value"],
            host_info["type"]["value"],
        )

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
        return _("主机（{}-{}）Ping 不可达").format(host_info["bk_cloud_id"]["value"], host_info["ip"]["value"])

    @classmethod
    def create_detail(cls, host_info) -> Dict[str, Any]:
        return {"target": cls.create_target(host_info)}


class AgentLostHandler(SpecificHostEventHandler):
    @classmethod
    def add_other_fields(cls, origin_data: Dict[str, Any]) -> Dict[str, Any]:
        return create_host_info(origin_data, ["bk_agent_id"])

    @classmethod
    def create_event_content_alias(cls, host_info) -> str:
        return _("主机（{}-{}）Agent 失联").format(host_info["bk_cloud_id"]["value"], host_info["ip"]["value"])

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
        return {
            "target": cls.create_target(host_info),
            "corefile": {"label": host_info["corefile"]["label"], "value": host_info["corefile"]["value"]},
            "executable": {"label": host_info["executable"]["label"], "value": host_info["executable"]["value"]},
        }
