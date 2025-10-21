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
import datetime
from typing import Any, Dict, List

from django.conf import settings

from bkmonitor.utils.time_tools import hms_string

from ...constants import (
    CicdEventName,
    CicdStatus,
    CicdTrigger,
    DisplayFieldType,
    EventDomain,
    EventScenario,
    EventSource,
)
from ...utils import create_cicd_info
from .base import BaseEventProcessor


class CicdEventProcessor(BaseEventProcessor):
    def __init__(self, pipeline_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipeline_context = pipeline_context

    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == (
            EventDomain.CICD.value,
            EventSource.BKCI.value,
        )

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        cicd_infos: List[Dict[str, Any]] = []
        pipeline_entities: List[Dict[str, Any]] = []
        cicd_processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue
            processed_event = copy.deepcopy(origin_event)
            cicd_info = create_cicd_info(
                origin_event["origin_data"],
                [
                    "pipelineName",
                    "projectId",
                    "buildId",
                    "pipelineId",
                    "duration",
                    "event_name",
                    "bk_biz_id",
                    "time",
                    "trigger",
                    "triggerUser",
                    "status",
                    "startTime",
                ],
            )
            cicd_infos.append(cicd_info)

            if not cicd_info["pipelineName"]["value"]:
                pipeline_entities.append(
                    {
                        "pipeline_id": cicd_info["pipelineId"]["value"],
                        "bk_biz_id": cicd_info["bk_biz_id"]["value"],
                        "time": cicd_info["time"]["value"],
                    }
                )

            detail = processed_event["event.content"]["detail"]
            # 设置存在字段
            detail.update(self.set_detail_with_cicd_info(cicd_info))
            # 设置 target
            processed_event["target"] = self.set_target(cicd_info)
            # 设置 event_name 别名
            processed_event["event_name"]["alias"] = CicdEventName.from_value(cicd_info["event_name"]["value"]).label
            if detail.get("trigger"):
                detail["trigger"]["alias"] = CicdTrigger.from_value(cicd_info["trigger"]["value"]).label
            if detail.get("status"):
                detail["status"]["alias"] = CicdStatus.from_value(cicd_info["status"]["value"]).label
            # 设置 startTime 别名
            if detail.get("startTime"):
                detail["startTime"]["alias"] = self.set_start_time_alias(cicd_info)
            # 设置 duration 别名
            if detail.get("duration"):
                detail["duration"]["alias"] = self.set_duration_alias(cicd_info)
            cicd_processed_events.append(processed_event)

        if cicd_processed_events:
            # 设置 pipelineName
            pipelines = self.pipeline_context.fetch(pipeline_entities)
            for cicd_processed_event in cicd_processed_events:
                cicd_processed_event["event.content"]["detail"]["pipelineName"] = self.set_pipeline_name(
                    create_cicd_info(
                        cicd_processed_event["origin_data"],
                        ["pipelineName", "projectId", "buildId", "pipelineId", "bk_biz_id", "time"],
                    ),
                    pipelines,
                )
                # 设置 target 别名
                cicd_processed_event["target"]["alias"] = cicd_processed_event["event.content"]["detail"][
                    "pipelineName"
                ]["alias"]
            processed_events.extend(cicd_processed_events)
        return processed_events

    @classmethod
    def set_detail_with_cicd_info(cls, cicd_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            field: cicd_info[field]
            for field in ["trigger", "triggerUser", "status", "startTime", "duration"]
            if cicd_info[field]["value"]
        }

    @classmethod
    def generate_url(cls, cicd_info):
        return "{base_url}/console/pipeline/{project_id}/{pipeline_id}/detail/{build_id}/executeDetail".format(
            base_url=settings.BK_CI_URL.rstrip("/"),
            project_id=cicd_info["projectId"]["value"],
            pipeline_id=cicd_info["pipelineId"]["value"],
            build_id=cicd_info["buildId"]["value"],
        )

    @classmethod
    def set_start_time_alias(cls, cicd_info: Dict[str, Any]) -> str:
        return datetime.datetime.fromtimestamp(int(cicd_info["startTime"]["value"]) // 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    @classmethod
    def set_duration_alias(cls, cicd_info):
        return hms_string(int(cicd_info["duration"]["value"]) // 1000)

    @classmethod
    def set_target(cls, cicd_info):
        return {
            "value": cicd_info["pipelineId"]["value"],
            "alias": cicd_info["pipelineId"]["alias"],
            "scenario": EventScenario.BKCI.value,
            "url": cls.generate_url(cicd_info),
        }

    @classmethod
    def set_pipeline_name(cls, cicd_info, pipelines):
        pipeline_name = cicd_info["pipelineName"]["value"]
        # 流水线 Stage 执行，需要获取流水线名称
        if not pipeline_name:
            pipeline_name = pipelines.get(cicd_info["pipelineId"]["value"], {}).get("pipeline_name", "")
        return {
            "type": DisplayFieldType.LINK.value,
            "label": cicd_info["pipelineName"]["label"],
            "value": pipeline_name,
            "alias": "{projectId} / {pipelineName}".format(
                projectId=cicd_info["projectId"]["value"], pipelineName=pipeline_name
            )
            if pipeline_name
            else "{projectId} / {pipelineId}".format(
                projectId=cicd_info["projectId"]["value"], pipelineId=cicd_info["pipelineId"]["value"]
            ),
            "scenario": EventScenario.BKCI.value,
            "url": cls.generate_url(cicd_info),
        }
