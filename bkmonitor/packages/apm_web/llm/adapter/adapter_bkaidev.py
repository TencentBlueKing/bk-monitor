"""BKAIDev 固定转换规则。"""

from __future__ import annotations

from typing import Any

from .fields import STANDARD_FIELDS
from .utils import (
    first,
    indexed,
    normalize_schema,
    nonnegative_int,
    put,
    safe_parse,
    split_system,
    standard_content,
    text_message,
    tool_call_part,
    tool_response_part,
)

REQUEST_OPERATIONS = {
    "chat": "chat",
    "completion": "text_completion",
    "embedding": "embeddings",
    "rerank": "retrieval",
}
ROLE_MAP = {
    "human": "user",
    "ai": "assistant",
    "chatgeneration": "assistant",
    "aichunk": "assistant",
}


def operation(attrs: dict[str, Any]) -> str | None:
    request_type = str(attrs.get("llm.request.type", "")).lower()
    if request_type:
        return REQUEST_OPERATIONS.get(request_type, request_type)
    return None


def provider(attrs: dict[str, Any]) -> Any:
    return attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system")


def aliases() -> dict[str, tuple[str, ...]]:
    return {
        "gen_ai.agent.name": (
            "gen_ai.entity.name",
            "gen_ai.chain.name",
            "agent.info.name",
        ),
        "gen_ai.conversation.id": ("agent.session.session_code",),
        "user.name": ("agent.session.caller_executor",),
        "gen_ai.agent.id": ("agent.info.id",),
        "gen_ai.usage.input_tokens": ("gen_ai.usage.prompt_tokens",),
        "gen_ai.usage.output_tokens": ("gen_ai.usage.completion_tokens",),
        "gen_ai.tool.name": ("tool.name", "traceloop.entity.name"),
        "gen_ai.request.model": ("gen_ai.model_name",),
    }


def parse_langchain_messages(value: Any, default_role: str) -> list[dict[str, Any]]:
    items = safe_parse(value)
    if items in (None, ""):
        return []
    if not isinstance(items, list):
        items = [items]

    messages: list[dict[str, Any]] = []
    for envelope in items:
        if not isinstance(envelope, dict):
            messages.append(text_message(default_role, envelope))
            continue
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
        source_role = str(envelope.get("type") or data.get("role") or default_role).lower()
        role = ROLE_MAP.get(source_role, source_role)
        content = data.get("content")
        parts: list[dict[str, Any]] = []
        if role == "tool" and content not in (None, ""):
            parts.append(tool_response_part(content, data.get("tool_call_id")))
        elif content not in (None, ""):
            parts.append({"type": "text", "content": str(content)})

        calls = data.get("tool_calls") or data.get("tool_call") or []
        if isinstance(calls, dict):
            calls = [calls]
        if isinstance(calls, list):
            parts.extend(tool_call_part(call) for call in calls if isinstance(call, dict))
        if not parts:
            continue

        message: dict[str, Any] = {"role": role, "parts": parts}
        if data.get("finish_reason") not in (None, ""):
            message["finish_reason"] = str(data["finish_reason"])
        messages.append(message)
    return messages


def parse_indexed_messages(attrs: dict[str, Any], prefix: str, default_role: str) -> list[dict[str, Any]]:
    return [
        text_message(str(item.get("role") or default_role), item["content"])
        for item in indexed(attrs, prefix)
        if item.get("content") not in (None, "")
    ]


def parse_definitions(value: Any) -> list[dict[str, Any]]:
    items = safe_parse(value)
    if not isinstance(items, list):
        return []
    definitions: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if isinstance(item.get("function"), dict) else item
        if function.get("name") in (None, ""):
            continue
        definitions.append(
            {
                "type": "function",
                "name": str(function["name"]),
                "description": str(function.get("description", "")),
                "parameters": normalize_schema(safe_parse(function.get("parameters", {}))),
            }
        )
    return definitions


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span["attributes"]
    content = standard_content(attrs)

    inputs = parse_indexed_messages(attrs, "gen_ai.prompt", "user")
    if (input_value := first(attrs, "llm.input", "traceloop.entity.input")) is not None:
        inputs = parse_langchain_messages(input_value, "user")
    instructions, inputs = split_system(inputs)
    put(content, "gen_ai.system_instructions", instructions)
    put(content, "gen_ai.input.messages", inputs)

    outputs = parse_indexed_messages(attrs, "gen_ai.completion", "assistant")
    if (output_value := first(attrs, "llm.output", "traceloop.entity.output")) is not None:
        outputs = parse_langchain_messages(output_value, "assistant")
    put(content, "gen_ai.output.messages", outputs)
    put(content, "gen_ai.tool.definitions", parse_definitions(attrs.get("gen_ai.request.tools")))
    put(content, "gen_ai.tool.call.arguments", safe_parse(first(attrs, "tool.input", "input.value")))
    put(content, "gen_ai.tool.call.result", safe_parse(first(attrs, "tool.output", "output.value")))
    return content


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {
            key: value for key, value in attrs.items() if key in STANDARD_FIELDS and value not in (None, "", [])
        }
        put(attributes, "gen_ai.operation.name", operation(attrs))
        put(attributes, "gen_ai.provider.name", provider(attrs))
        for target, source_keys in aliases().items():
            value = first(attrs, *source_keys)
            if target.startswith("gen_ai.usage."):
                value = nonnegative_int(value)
            elif target == "gen_ai.agent.id" and value is not None:
                value = str(value)
            put(attributes, target, value)
        attributes.update(convert_content(span))
        if not attributes:
            continue
        spans.append(
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span["parent_span_id"],
                "span_name": span["span_name"],
                "start_time": span["start_time"],
                "end_time": span["end_time"],
                "elapsed_time": span["elapsed_time"],
                "status": span["status"],
                "resource": span["resource"],
                "attributes": attributes,
            }
        )
    return spans
