"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from datetime import datetime

from django.conf import settings
from rest_framework import serializers

from core.drf_resource import Resource

logger = logging.getLogger(__name__)


class GetMCPHelperInfoResource(Resource):
    """
    获取 MCP Agent 辅助信息 -- 通用工具MCP

    提供当前时间戳、时间跨度限制等信息，帮助 Agent 构造合理的查询请求
    """

    class RequestSerializer(serializers.Serializer):
        # 可选参数：是否需要建议的查询时间范围
        include_suggestions = serializers.BooleanField(
            required=False, default=True, label="是否包含查询建议（默认为True）"
        )

    def perform_request(self, validated_request_data):
        include_suggestions = validated_request_data.get("include_suggestions", True)

        # 获取当前时间戳（秒级）
        current_timestamp = int(time.time())
        current_datetime = datetime.fromtimestamp(current_timestamp)

        # 基础信息
        result = {
            "current_timestamp": current_timestamp,
            "current_datetime": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "max_time_span_seconds": settings.MCP_MAX_TIME_SPAN_SECONDS,
        }

        # 添加查询建议
        if include_suggestions:
            max_span = settings.MCP_MAX_TIME_SPAN_SECONDS
            result["query_suggestions"] = {
                "recommended_ranges": [
                    {
                        "name": "最近5分钟",
                        "start_time": current_timestamp - 300,
                        "end_time": current_timestamp,
                        "step": "30s",
                    },
                    {
                        "name": "最近15分钟",
                        "start_time": current_timestamp - 900,
                        "end_time": current_timestamp,
                        "step": "60s",
                    },
                    {
                        "name": "最近1小时",
                        "start_time": current_timestamp - 3600,
                        "end_time": current_timestamp,
                        "step": "60s",
                    },
                    {
                        "name": "最近6小时",
                        "start_time": current_timestamp - 21600,
                        "end_time": current_timestamp,
                        "step": "300s",
                    },
                    {
                        "name": f"最大允许跨度（{max_span}秒）",
                        "start_time": current_timestamp - max_span,
                        "end_time": current_timestamp,
                        "step": "auto",
                        "note": "请根据实际数据量选择合适的步长",
                    },
                ],
                "step_guidelines": {
                    "short_range": {"range": "< 1小时", "suggested_step": "30s-60s"},
                    "medium_range": {"range": "1-6小时", "suggested_step": "60s-300s"},
                    "long_range": {"range": "6-24小时", "suggested_step": "300s-600s"},
                },
                "best_practices": [
                    f"Time span must not exceed {settings.MCP_MAX_TIME_SPAN_SECONDS} seconds per query",
                    "Split large time ranges into multiple queries to avoid context overflow",
                    "Use larger step values for longer time ranges to reduce data volume",
                ],
            }

        logger.info("GetMCPHelperInfoResource: return helper info, current_timestamp->[%s]", current_timestamp)
        return result
