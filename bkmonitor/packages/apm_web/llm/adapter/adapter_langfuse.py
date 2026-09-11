"""Langfuse Observation 转换。"""

from __future__ import annotations

import json
from typing import Any

from .fields import STANDARD_FIELDS
from .utils import (
    CONTENT_FIELDS,
    first,
    nonnegative_int,
    normalize_schema,
    put,
    safe_parse,
    split_system,
    standard_content,
)

OPERATION_MAPPING = {
    "agent": "invoke_agent",
    "embedding": "embeddings",
    "retriever": "retrieval",
    "tool": "execute_tool",
}

ALIASES = {
    "gen_ai.conversation.id": "session.id",
    "gen_ai.request.model": "langfuse.observation.model.name",
    "gen_ai.request.reasoning.level": "langfuse.observation.metadata.reasoningEffort",
}


def _parse(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _text_part(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return {"type": "text", "content": content}


def _message_part(source: Any) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        return _text_part(source)

    part_type = str(source.get("type", "")).lower()
    if part_type in {"text", "reasoning"}:
        if part := _text_part(first(source, "content", "text")):
            part["type"] = part_type
        return part

    if part_type in {"tool_use", "tool_call"}:
        name = source.get("name")
        if name in (None, ""):
            return None
        part: dict[str, Any] = {
            "type": "tool_call",
            "name": str(name),
            "arguments": _parse(first(source, "input", "arguments") or {}),
        }
        if (call_id := first(source, "id", "call_id")) is not None:
            part["id"] = str(call_id)
        return part

    if part_type in {"tool_result", "tool_call_response"}:
        response = first(source, "content", "response")
        if response is None:
            return None
        part = {"type": "tool_call_response", "response": _parse(response)}
        if (call_id := first(source, "tool_use_id", "id", "call_id")) is not None:
            part["id"] = str(call_id)
        return part

    return None


def _message(source: Any, default_role: str) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        part = _text_part(source)
        return {"role": default_role, "parts": [part]} if part else None

    role = str(source.get("role") or default_role).lower()
    content = source.get("content")
    values = content if isinstance(content, list) else [content]
    parts = [part for value in values if (part := _message_part(value))]
    if not parts:
        return None
    if all(part["type"] == "tool_call_response" for part in parts):
        role = "tool"
    return {"role": role, "parts": parts}


def _messages(value: Any, default_role: str) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    return [message for item in values if (message := _message(item, default_role))]


def _definitions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    definitions: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if isinstance(item.get("function"), dict) else item
        if function.get("name") in (None, ""):
            continue
        definitions.append(
            {
                "type": str(item.get("type") or "function"),
                "name": str(function["name"]),
                "description": str(function.get("description", "")),
                "parameters": normalize_schema(safe_parse(function.get("parameters", {}))),
            }
        )
    return definitions


def _add_generation_content(target: dict[str, Any], attrs: dict[str, Any]) -> None:
    source = _parse(attrs.get("langfuse.observation.input"))
    instructions: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []
    messages = None
    if isinstance(source, dict):
        if part := _text_part(source.get("systemPrompt")):
            instructions.append(part)
        messages = source.get("messages")
        if not isinstance(messages, list):
            messages = source.get("lastMessages")
        if isinstance(messages, list):
            inputs = _messages(messages, "user")
        definitions = _definitions(source.get("tools"))
    elif source not in (None, ""):
        inputs = _messages(source, "user")

    put(target, "gen_ai.operation.name", "chat" if isinstance(messages, list) else "text_completion")
    message_instructions, inputs = split_system(inputs)
    instructions.extend(message_instructions)
    put(target, "gen_ai.system_instructions", instructions)
    put(target, "gen_ai.input.messages", inputs)
    put(target, "gen_ai.tool.definitions", definitions)

    output = _parse(attrs.get("langfuse.observation.output"))
    if isinstance(output, list) and not any(isinstance(item, dict) and item.get("role") for item in output):
        parts = [part for item in output if (part := _message_part(item))]
        outputs = [{"role": "assistant", "parts": parts}] if parts else []
    else:
        outputs = _messages(output, "assistant") if output not in (None, "") else []
    put(target, "gen_ai.output.messages", outputs)


def _add_tool_content(target: dict[str, Any], span: dict[str, Any]) -> None:
    attrs = span["attributes"]
    arguments = _parse(attrs.get("langfuse.observation.input"))
    if isinstance(arguments, dict) and isinstance(arguments.get("arguments"), str):
        arguments = {**arguments, "arguments": _parse(arguments["arguments"])}
    put(target, "gen_ai.tool.call.arguments", arguments)
    put(target, "gen_ai.tool.call.result", _parse(attrs.get("langfuse.observation.output")))

    name = span.get("span_name")
    if isinstance(name, str):
        name = name.removeprefix("tool-").removeprefix("subagent-tool-")
        put(target, "gen_ai.tool.name", name)


def _add_root_content(target: dict[str, Any], attrs: dict[str, Any]) -> None:
    for source_key, target_key, role in (
        ("langfuse.observation.input", "gen_ai.input.messages", "user"),
        ("langfuse.observation.output", "gen_ai.output.messages", "assistant"),
    ):
        value = _parse(attrs.get(source_key))
        if value not in (None, ""):
            put(target, target_key, _messages(value, role))


def _add_usage(target: dict[str, Any], attrs: dict[str, Any]) -> None:
    source = _parse(attrs.get("langfuse.observation.usage_details"))
    if not isinstance(source, dict):
        return

    input_tokens = nonnegative_int(source.get("input"))
    output_tokens = nonnegative_int(source.get("output"))
    cache_read_tokens = nonnegative_int(source.get("cache_read_input_tokens"))
    cache_creation_tokens = nonnegative_int(source.get("cache_creation_input_tokens"))
    input_parts = [value for value in (input_tokens, cache_read_tokens, cache_creation_tokens) if value is not None]
    if input_parts:
        put(target, "gen_ai.usage.input_tokens", sum(input_parts))
    put(target, "gen_ai.usage.output_tokens", output_tokens)
    put(target, "gen_ai.usage.cache_read.input_tokens", cache_read_tokens)
    put(target, "gen_ai.usage.cache_creation.input_tokens", cache_creation_tokens)


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {
            key: value
            for key, value in attrs.items()
            if key in STANDARD_FIELDS and key not in CONTENT_FIELDS and value not in (None, "", [])
        }
        attributes.update(standard_content(attrs))
        observation_type = str(attrs.get("langfuse.observation.type", "")).lower()
        put(attributes, "gen_ai.operation.name", OPERATION_MAPPING.get(observation_type))
        for target, source_key in ALIASES.items():
            put(attributes, target, attrs.get(source_key))
        temperature = attrs.get("langfuse.observation.metadata.temperature")
        if isinstance(temperature, str):
            try:
                temperature = float(temperature)
            except ValueError:
                temperature = None
        if isinstance(temperature, int | float) and not isinstance(temperature, bool):
            put(attributes, "gen_ai.request.temperature", temperature)
        if observation_type == "agent":
            put(attributes, "gen_ai.agent.name", span.get("span_name"))
        _add_usage(attributes, attrs)
        if observation_type == "generation":
            _add_generation_content(attributes, attrs)
        elif observation_type == "tool":
            _add_tool_content(attributes, span)
        elif observation_type in {"agent", "chain"} or attrs.get("langfuse.internal.is_app_root") is True:
            _add_root_content(attributes, attrs)
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
