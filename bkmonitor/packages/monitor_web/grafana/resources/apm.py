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

import logging

from rest_framework import serializers

from apm_web.meta.views import ListApplicationInfoResource  # noqa
from apm_web.trace.views import GetFieldOptionValuesResource  # noqa
from apm_web.trace.views import ListTraceResource as ApmListTraceResource
from apm_web.trace.views import TraceDetailResource as ApmTraceDetailResource
from constants.apm import TraceListQueryMode

logger = logging.getLogger(__name__)


class ListTraceResource(ApmListTraceResource):
    class RequestSerializer(ApmListTraceResource.RequestSerializer):
        min_duration = serializers.CharField(label="trace查询最小duration", default="0ns", required=False)
        max_duration = serializers.CharField(label="trace查询最小duration", default="2h", required=False)

    def perform_request(self, validated_request_data):
        from monitor_web.grafana.utils import convert_to_microseconds

        try:
            min_duration = convert_to_microseconds(validated_request_data["min_duration"])
            max_duration = convert_to_microseconds(validated_request_data["max_duration"])
            if min_duration > max_duration:
                raise serializers.ValidationError("trace查询参数错误: 最小duration不能大于最大duration")
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"trace查询参数解析失败: {e}")
            return {"type": TraceListQueryMode.PRE_CALCULATION, "total": 0, "data": []}
        validated_request_data["filters"].append(
            {"key": "duration", "operator": "between", "value": [min_duration, max_duration]}
        )
        res_data = super().perform_request(validated_request_data)
        trace_list = [
            {
                "trace_id": trace_summary["trace_id"],
                "trace_name": trace_summary.get("root_span_service"),
                "start_time": trace_summary.get("min_start_time"),
                "trace_duration": trace_summary.get("trace_duration"),
            }
            for trace_summary in res_data.get("data", [])
        ]
        res_data["data"] = trace_list
        return res_data


class TraceDetailResource(ApmTraceDetailResource):
    """
    获取统计数据
    """

    class RequestSerializer(ApmTraceDetailResource.RequestSerializer):
        app_name = serializers.CharField(label="应用名称", allow_blank=True, default="")
        trace_id = serializers.CharField(label="Trace ID", allow_blank=True, default="")

    def perform_request(self, validated_request_data):
        if not all([validated_request_data.get("app_name"), validated_request_data.get("trace_id")]):
            return []
        trace_info = super().perform_request(validated_request_data)
        return self.transform_to_jager(trace_info)

    @classmethod
    def transform_to_jager(cls, data):
        formatted_data = data.get("trace_tree", {})
        formatted_data["warnings"] = None
        return [formatted_data]
