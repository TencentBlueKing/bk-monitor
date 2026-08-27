"""AgentLens 转换，并兼容同一 Trace 内的标准 OTel 子 Span。"""

from __future__ import annotations

import json
from typing import Any

from .fields import STANDARD_FIELDS
from .utils import (
    first,
    indexed,
    normalize_schema,
    present,
    put,
    safe_parse,
    split_system,
    standard_content,
    text_message,
    tool_call_part,
    tool_response_part,
)


def provider(attrs: dict[str, Any]) -> Any:
    return attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system")


def aliases() -> dict[str, tuple[str, ...]]:
    return {
        "gen_ai.conversation.id": ("gen_ai.session.id",),
        "user.id": ("gen_ai.user.id",),
        "gen_ai.tool.name": ("tool.name", "traceloop.entity.name"),
        "gen_ai.agent.name": (
            "gen_ai.entity.name",
            "gen_ai.chain.name",
            "agent.info.name",
        ),
        "gen_ai.request.model": ("gen_ai.model_name",),
    }


def parse_text_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return parsed if isinstance(parsed, str) else value


def parse_indexed_messages(
    attrs: dict[str, Any],
    prefix: str,
    *,
    output: bool = False,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for item in indexed(attrs, prefix):
        role = str(item.get("role") or ("assistant" if output else "user"))
        content = item.get("content")
        parts: list[dict[str, Any]] = []
        if role == "tool" and content not in (None, ""):
            parts.append(tool_response_part(content, item.get("tool_call_id")))
        elif content not in (None, ""):
            parts.append({"type": "text", "content": str(content)})
        parts.extend(tool_call_part(call) for call in indexed(item, "tool_calls"))
        if not parts:
            continue
        message: dict[str, Any] = {"role": role, "parts": parts}
        if output and item.get("finish_reason") not in (None, ""):
            reason = str(item["finish_reason"])
            message["finish_reason"] = "tool_call" if reason in {"tool_call", "tool_calls"} else reason
        messages.append(message)
    return messages


def parse_indexed_definitions(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": str(item["name"]),
            "description": str(item.get("description", "")),
            "parameters": normalize_schema(safe_parse(item.get("parameters", {}))),
        }
        for item in indexed(attrs, "gen_ai.request.functions")
        if item.get("name") not in (None, "")
    ]


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span["attributes"]
    content = standard_content(attrs)
    inputs = parse_indexed_messages(attrs, "gen_ai.prompts")
    instructions, inputs = split_system(inputs)
    put(content, "gen_ai.system_instructions", instructions)
    put(content, "gen_ai.input.messages", inputs)
    put(content, "gen_ai.output.messages", parse_indexed_messages(attrs, "gen_ai.completion", output=True))
    put(content, "gen_ai.tool.definitions", parse_indexed_definitions(attrs))

    span_kind = str(attrs.get("gen_ai.span.kind", "")).upper()
    if span_kind == "AGENT":
        input_value = attrs.get("input.value")
        output_value = attrs.get("output.value")
        if input_value not in (None, ""):
            put(content, "gen_ai.input.messages", [text_message("user", parse_text_value(input_value))])
        if output_value not in (None, ""):
            put(content, "gen_ai.output.messages", [text_message("assistant", parse_text_value(output_value))])
    elif span_kind == "TOOL":
        arguments = first(attrs, "tool.input", "traceloop.entity.input", "input.value")
        result = first(attrs, "tool.output", "traceloop.entity.output", "output.value")
        put(content, "gen_ai.tool.call.arguments", safe_parse(arguments))
        put(content, "gen_ai.tool.call.result", safe_parse(result))
    return content


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """转换 AgentLens，以及混合在同一 Trace 内的标准 OTel Span。"""
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {key: value for key, value in attrs.items() if key in STANDARD_FIELDS and present(value)}
        put(attributes, "gen_ai.provider.name", provider(attrs))
        for target, source_keys in aliases().items():
            put(attributes, target, first(attrs, *source_keys))
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
