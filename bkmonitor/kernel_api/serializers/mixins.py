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
from django.conf import settings


class TimeSpanValidationPassThroughSerializer(serializers.Serializer):
    """
    透传序列化器，先进行常规字段验证和默认值应用，然后验证时间跨度是否超过1天。
    用于 AI MCP 请求，避免 LLM 上下文超限。
    """

    @staticmethod
    def _convert_timestamp_to_seconds(timestamp: int) -> float:
        """
        将时间戳统一转换为秒级
        支持秒级（10位）、毫秒级（13位）、纳秒级（19位）时间戳

        Args:
            timestamp: 时间戳（可能是秒、毫秒或纳秒）

        Returns:
            转换为秒级的时间戳
        """
        # 纳秒级：>= 1e18 (19位数字)，除以1e9转换为秒
        if timestamp >= 1e18:
            return timestamp / 1e9
        # 毫秒级：>= 1e12 (13位数字)，除以1000转换为秒
        elif timestamp >= 1e12:
            return timestamp / 1000
        # 秒级：直接返回
        else:
            return float(timestamp)

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        先执行常规序列化（包括字段验证和默认值应用），然后合并未定义的字段，最后验证时间跨度
        """
        # 先调用父类方法，执行常规的字段验证和默认值应用
        validated_data = super().to_internal_value(data)

        # 如果子类定义了字段，validated_data 只包含验证过的字段
        # 如果子类没有定义字段，validated_data 为空字典
        # 需要将原始数据中未被验证的字段也合并进去（透传未定义的字段）
        # 但优先使用已验证的字段值（可能经过类型转换和默认值处理）
        final_data = dict(data)  # 先保留所有原始数据
        final_data.update(validated_data)  # 用验证后的数据覆盖（保留类型转换和默认值）

        # 验证时间跨度（如果存在时间字段）
        start_time = final_data.get("start_time")
        end_time = final_data.get("end_time")

        if start_time is not None and end_time is not None:
            try:
                # 转换为整数进行时间跨度验证（不修改原始字段值，因为子类可能定义为 CharField）
                start_time_int = int(start_time)
                end_time_int = int(end_time)

                # 统一转换为秒级时间戳（支持秒、毫秒、纳秒）
                start_time_seconds = self._convert_timestamp_to_seconds(start_time_int)
                end_time_seconds = self._convert_timestamp_to_seconds(end_time_int)

                time_span = end_time_seconds - start_time_seconds
                if time_span > settings.MCP_MAX_TIME_SPAN_SECONDS:
                    raise serializers.ValidationError(
                        {
                            "time_span": f"Query time span exceeds the limit. To avoid LLM context overflow, please split into batch queries. The limit is {settings.MCP_MAX_TIME_SPAN_SECONDS} seconds."
                        }
                    )
            except serializers.ValidationError:
                raise
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    {
                        "time_span": "start_time and end_time must be valid integers (or string representations of integers)."
                    }
                )

        return final_data
