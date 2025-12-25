"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rest_framework import serializers

# 1 day in seconds
ONE_DAY_SECONDS = 86400


class TimeSpanValidationPassThroughSerializer(serializers.Serializer):
    """
    透传序列化器，先进行常规字段验证和默认值应用，然后验证时间跨度是否超过1天。
    用于 AI MCP 请求，避免 LLM 上下文超限。
    """

    max_time_span_seconds = ONE_DAY_SECONDS

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        先执行常规序列化（包括字段验证和默认值应用），然后验证时间跨度
        """
        # 先调用父类方法，执行常规的字段验证和默认值应用
        validated_data = super().to_internal_value(data)

        # 然后验证时间跨度
        start_time = validated_data.get("start_time")
        end_time = validated_data.get("end_time")

        if start_time is not None and end_time is not None:
            try:
                time_span = int(end_time) - int(start_time)
                if time_span > self.max_time_span_seconds:
                    raise serializers.ValidationError(
                        {
                            "time_span": "Query time span exceeds 1 day. To avoid LLM context overflow, please split into batch queries."
                        }
                    )
            except serializers.ValidationError:
                raise
            except (TypeError, ValueError):
                raise serializers.ValidationError({"time_span": "start_time and end_time must be valid integers."})

        return validated_data
