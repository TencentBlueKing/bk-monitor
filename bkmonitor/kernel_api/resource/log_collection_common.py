"""日志采集 MCP 资源共享的校验和响应处理。"""

import json
from collections.abc import Mapping
from typing import Any

from rest_framework import serializers


class StrictMCPSerializer(serializers.Serializer):
    """拒绝 MCP 未声明字段，避免参数被下游静默忽略。"""

    unsupported_api_name = "MCP API"
    unsupported_field_message = "This field is not supported by this {api_name}."

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {
                        field: [self.unsupported_field_message.format(api_name=self.unsupported_api_name)]
                        for field in sorted(unknown_fields)
                    }
                )
        return super().to_internal_value(data)


def normalize_task_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list | tuple | set):
        values = value
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


def normalize_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []
