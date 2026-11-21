"""Accept chat-helper message fields and preserve the platform write schema."""

from copy import deepcopy

from rest_framework import serializers


class SessionContentSerializer(serializers.Serializer):
    session_code = serializers.CharField(max_length=64)
    role = serializers.CharField()
    input = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    content = serializers.JSONField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=("pending", "streaming", "complete", "error", "loading", "fail"), required=False
    )
    property = serializers.DictField(required=False)
    message_id = serializers.CharField(required=False, max_length=255)
    tool_calls = serializers.ListField(child=serializers.DictField(), required=False)
    tool_call_id = serializers.CharField(required=False)
    duration = serializers.FloatField(required=False, min_value=0)
    error = serializers.BooleanField(required=False)

    def validate(self, attrs):
        attrs = deepcopy(attrs)
        prop = attrs.get("property", {})
        builtin = prop.get("builtin_property") or {}
        if not isinstance(builtin, dict):
            raise serializers.ValidationError({"property": "builtin_property 必须是对象"})
        for key in ("message_id", "tool_calls", "tool_call_id", "error"):
            if key in attrs:
                value = attrs.pop(key)
                if key in builtin and builtin[key] != value:
                    raise serializers.ValidationError({key: "与 property.builtin_property 不一致"})
                builtin[key] = value
        if "duration" in attrs:
            extra = builtin.get("additional_kwargs") or {}
            if not isinstance(extra, dict):
                raise serializers.ValidationError({"property": "additional_kwargs 必须是对象"})
            extra["duration"] = attrs.pop("duration")
            builtin["additional_kwargs"] = extra
        if builtin:
            prop["builtin_property"] = builtin
            attrs["property"] = prop
        calls = builtin.get("tool_calls", [])
        if not isinstance(calls, list):
            raise serializers.ValidationError({"tool_calls": "必须是数组"})
        ids = set()
        for call in calls:
            function = call.get("function") if isinstance(call, dict) else None
            if (
                not isinstance(call, dict)
                or not isinstance(call.get("id"), str)
                or not call["id"]
                or call["id"] in ids
                or call.get("type") != "function"
                or not isinstance(function, dict)
                or not isinstance(function.get("name"), str)
                or not function["name"]
                or not isinstance(function.get("arguments"), str)
            ):
                raise serializers.ValidationError({"tool_calls": "工具调用须包含唯一 id 及合法 function"})
            ids.add(call["id"])
        role = attrs.get("role")
        if calls and role not in (None, "assistant", "ai"):
            raise serializers.ValidationError({"tool_calls": "仅 assistant 消息支持工具调用"})
        if not self.partial and role == "tool" and not builtin.get("tool_call_id"):
            raise serializers.ValidationError({"tool_call_id": "tool 消息需要关联调用 ID"})
        user_input = attrs.pop("input", None)
        if user_input:
            attrs["content"] = user_input
        if "content" in attrs:
            content = attrs["content"]
            if content is None:
                content = attrs["content"] = ""
            if not isinstance(content, str | dict | list) or (
                isinstance(content, list) and not all(isinstance(item, dict) for item in content)
            ):
                raise serializers.ValidationError({"content": "仅支持字符串、对象或对象列表"})
        if not self.partial and not attrs.get("content"):
            if not ((role in ("assistant", "ai") and calls) or (role == "tool" and builtin.get("tool_call_id"))):
                raise serializers.ValidationError({"content": "正文不能为空（结构化工具消息除外）"})
            attrs["content"] = ""
        return attrs


class UpdateSessionContentSerializer(SessionContentSerializer):
    id = serializers.CharField()
    session_code = serializers.CharField(required=False, max_length=64)
    role = serializers.CharField(required=False)

    def __init__(self, *args, **kwargs):
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        if not attrs.get("id"):
            raise serializers.ValidationError({"id": "必须提供内容 ID"})
        return super().validate(attrs)
