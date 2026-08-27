"""Galileo 固定转换规则。"""

from __future__ import annotations

import json
from typing import Any

from .fields import STANDARD_FIELDS
from .utils import (
    first,
    normalize_schema,
    nonnegative_int,
    present,
    put,
    safe_parse,
    standard_content,
    text_message,
    tool_call_part,
    tool_response_part,
)


def provider(attrs: dict[str, Any]) -> Any:
    # gen_ai.system 是 tRPC Agent 运行时名，不是模型 provider。
    return attrs.get("gen_ai.provider.name")


def aliases() -> dict[str, tuple[str, ...]]:
    return {
        "gen_ai.conversation.id": ("gen_ai.session_id",),
        "user.id": ("gen_ai.user.id",),
        "gen_ai.usage.cache_read.input_tokens": ("gen_ai.usage.cache_read_input_tokens",),
        "gen_ai.usage.cache_creation.input_tokens": ("gen_ai.usage.cache_creation_input_tokens",),
        "gen_ai.usage.reasoning.output_tokens": ("gen_ai.usage.reasoning_tokens",),
        "gen_ai.tool.name": ("tool.name", "traceloop.entity.name"),
        "gen_ai.agent.name": (
            "gen_ai.entity.name",
            "gen_ai.chain.name",
            "agent.info.name",
        ),
        "gen_ai.request.model": ("gen_ai.model_name",),
    }


def extra_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    nested = safe_parse(attrs.get("trpc.python.agent.llm_response"))
    if isinstance(nested, dict):
        extra["gen_ai.response.id"] = nested.get("response_id")
    return extra


def parse_event_detail(detail: Any) -> Any:
    parsed = safe_parse(detail)
    if parsed is not detail or not isinstance(detail, str):
        return parsed
    try:
        return json.loads(detail)
    except json.JSONDecodeError:
        return detail


def parse_event_message(detail: Any, default_role: str) -> dict[str, Any] | None:
    message = parse_event_detail(detail)
    if message in (None, ""):
        return None
    if not isinstance(message, dict):
        parts = (
            [tool_response_part(message)] if default_role == "tool" else text_message(default_role, message)["parts"]
        )
        return {"role": default_role, "parts": parts}

    source_role = str(message.get("role") or default_role).lower()
    role = "assistant" if source_role == "model" else source_role
    parts: list[dict[str, Any]] = []
    sources = message.get("parts") if isinstance(message.get("parts"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            if source not in (None, ""):
                parts.append({"type": "text", "content": str(source)})
            continue
        if source.get("type"):
            part = dict(source)
            if part["type"] in {"text", "reasoning"} and "content" not in part:
                part["content"] = str(part.pop("text", ""))
            parts.append(part)
            if part["type"] == "tool_call_response":
                role = "tool"
        elif source.get("text") not in (None, ""):
            parts.append(
                {
                    "type": "reasoning" if source.get("thought") is True else "text",
                    "content": str(source["text"]),
                }
            )
        elif isinstance(source.get("function_call"), dict):
            parts.append(tool_call_part(source["function_call"]))
        elif isinstance(source.get("function_response"), dict):
            response = source["function_response"]
            parts.append(tool_response_part(response.get("response", {}), response.get("id")))
            role = "tool"

    content = message.get("content")
    if not parts and content not in (None, ""):
        if role == "tool":
            parts.append(tool_response_part(content, message.get("tool_call_id")))
        else:
            parts.extend(text_message(role, content)["parts"])
    return {"role": role, "parts": parts} if parts else None


def parse_event_messages(detail: Any, default_role: str) -> list[dict[str, Any]]:
    parsed = safe_parse(detail)
    values = parsed if isinstance(parsed, list) else [parsed]
    return [message for value in values if (message := parse_event_message(value, default_role))]


def parse_event_definitions(detail: Any) -> list[dict[str, Any]]:
    groups = safe_parse(detail)
    if not isinstance(groups, list):
        return []
    functions: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        declarations = group.get("function_declarations")
        if isinstance(declarations, list):
            functions.extend(item for item in declarations if isinstance(item, dict))
        elif group.get("name") not in (None, ""):
            functions.append(group)
    return [
        {
            "type": "function",
            "name": str(function["name"]),
            "description": str(function.get("description", "")),
            "parameters": normalize_schema(safe_parse(function.get("parameters", {}))),
        }
        for function in functions
        if function.get("name") not in (None, "")
    ]


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    """迁移 Galileo events；gen_ai.choice 按第一版规则丢弃。"""
    content = standard_content(span["attributes"])
    instructions: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []

    for event in span["events"]:
        detail = event["attributes"].get("message.detail")
        if detail is None:
            continue
        match event["name"]:
            case "gen_ai.system.message":
                if message := parse_event_message(detail, "system"):
                    instructions.extend(message["parts"])
            case "gen_ai.user.message":
                if message := parse_event_message(detail, "user"):
                    inputs.append(message)
            case "gen_ai.assistant.message":
                if message := parse_event_message(detail, "assistant"):
                    inputs.append(message)
            case "gen_ai.tool.message":
                if message := parse_event_message(detail, "tool"):
                    inputs.append(message)
            case "gen_ai.invoke_agent_request":
                inputs.extend(parse_event_messages(detail, "user"))
            case "gen_ai.invoke_agent_response":
                outputs.extend(parse_event_messages(detail, "assistant"))
            case "gen_ai.tools":
                definitions.extend(parse_event_definitions(detail))
            case "gen_ai.tool_call_args":
                put(content, "gen_ai.tool.call.arguments", safe_parse(detail))
            case "gen_ai.tool_response":
                put(content, "gen_ai.tool.call.result", safe_parse(detail))

    put(content, "gen_ai.system_instructions", instructions)
    put(content, "gen_ai.input.messages", inputs)
    put(content, "gen_ai.output.messages", outputs)
    put(content, "gen_ai.tool.definitions", definitions)
    return content


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {key: value for key, value in attrs.items() if key in STANDARD_FIELDS and present(value)}
        put(attributes, "gen_ai.provider.name", provider(attrs))
        for target, source_keys in aliases().items():
            value = first(attrs, *source_keys)
            if target.startswith("gen_ai.usage."):
                value = nonnegative_int(value)
            put(attributes, target, value)
        for key, value in extra_attributes(attrs).items():
            put(attributes, key, value)
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
