"""把各方言的正文压缩为协议标准中的消息、工具和系统指令字段。"""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .fields import FINISH_REASONS
from .utils import safe_parse


@dataclass
class ContentState:
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    definitions: list[dict[str, Any]] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def build(self) -> dict[str, Any]:
        content = dict(self.attributes)
        for key, values in (
            ("gen_ai.system_instructions", self.instructions),
            ("gen_ai.input.messages", self.inputs),
            ("gen_ai.output.messages", self.outputs),
            ("gen_ai.tool.definitions", self.definitions),
        ):
            if values:
                content[key] = values
        return content


def _normalize_role(value: Any, default: str) -> str:
    return {
        "human": "user",
        "ai": "assistant",
        "model": "assistant",
        "chatgeneration": "assistant",
        "aichunk": "assistant",
    }.get(str(value or default).lower(), str(value or default).lower())


def parse_value(value: Any) -> Any:
    return safe_parse(value)


def _normalize_part(value: Any) -> dict[str, Any] | None:
    """把 OTel Part、Gemini Part 或纯文本归一为 OTel Part。"""
    if not isinstance(value, dict):
        return {"type": "text", "content": str(value)} if value not in (None, "") else None
    match value:
        case {"type": part_type} if part_type:
            part = deepcopy(value)
            if part_type in {"text", "reasoning"} and "content" not in part:
                part["content"] = str(part.pop("text", ""))
            return part
        case {"text": text} if text not in (None, ""):
            return {
                "type": "reasoning" if value.get("thought") is True else "text",
                "content": str(text),
            }
        case {"function_call": dict() as call}:
            arguments = parse_value(call.get("args", call.get("arguments", {})))
            part = {
                "type": "tool_call",
                "name": str(call.get("name", "")),
                "arguments": arguments,
            }
            if call.get("id") not in (None, ""):
                part["id"] = str(call["id"])
            return part
        case {"function_response": dict() as response}:
            result = parse_value(response.get("response", {}))
            part = {"type": "tool_call_response", "response": result}
            if response.get("id") not in (None, ""):
                part["id"] = str(response["id"])
            return part
    return None


def _normalize_message_parts(message: dict[str, Any], role: str) -> list[dict[str, Any]]:
    parts = [part for value in message.get("parts", []) if (part := _normalize_part(value))]
    if parts:
        return parts

    content = message.get("content")
    if content not in (None, ""):
        if role == "tool":
            response = parse_value(content)
            part: dict[str, Any] = {"type": "tool_call_response", "response": response}
            call_id = message.get("tool_call_id", message.get("tool_id"))
            if call_id not in (None, ""):
                part["id"] = str(call_id)
            parts.append(part)
        elif isinstance(content, list):
            parts.extend(part for value in content if (part := _normalize_part(value)))
        else:
            parts.append({"type": "text", "content": str(content)})

    calls = message.get("tool_calls", message.get("tool_call", []))
    if isinstance(calls, dict):
        calls = [calls]
    for call in calls if isinstance(calls, list) else []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        arguments = parse_value(function.get("arguments", function.get("args", {})))
        part = {
            "type": "tool_call",
            "name": str(function.get("name", "")),
            "arguments": arguments,
        }
        if call.get("id") not in (None, ""):
            part["id"] = str(call["id"])
        parts.append(part)
    return parts


def parse_message(value: Any, *, default_role: str, output: bool = False) -> dict[str, Any] | None:
    parsed = parse_value(value)
    if not isinstance(parsed, dict):
        parsed = {"content": parsed}
    envelope_type = str(parsed.get("type", "")).lower()
    if envelope_type in {"system", "human", "ai", "assistant", "tool"} and isinstance(parsed.get("data"), dict):
        message = deepcopy(parsed["data"])
        message.setdefault("role", envelope_type)
    else:
        message = deepcopy(parsed)
    if "tool_calls" not in message and isinstance(message.get("additional_kwargs"), dict):
        message["tool_calls"] = message["additional_kwargs"].get("tool_calls", [])
    role = _normalize_role(message.get("role"), default_role)
    parts = _normalize_message_parts(message, role)
    if any(part.get("type") == "tool_call_response" for part in parts):
        role = "tool"
    if not parts:
        return None
    result: dict[str, Any] = {"role": role, "parts": parts}
    if output and message.get("finish_reason") not in (None, ""):
        reason = str(message["finish_reason"])
        result["finish_reason"] = FINISH_REASONS.get(reason, reason)
    return result


def parse_messages(value: Any, *, output: bool = False) -> list[dict[str, Any]]:
    parsed = parse_value(value)
    if isinstance(parsed, dict):
        for key in ("messages", "input", "output"):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
    values = parsed if isinstance(parsed, list) else [parsed]
    default_role = "assistant" if output else "user"
    return [message for item in values if (message := parse_message(item, default_role=default_role, output=output))]


def parse_indexed_messages(attrs: dict[str, Any], prefix: str, *, output: bool) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = defaultdict(dict)
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)\.(.+)$")
    for key, value in attrs.items():
        if match := pattern.match(key):
            grouped[int(match.group(1))][match.group(2)] = value
    messages: list[dict[str, Any]] = []
    for index in sorted(grouped):
        flat = grouped[index]
        source: dict[str, Any] = {
            "role": flat.get("role", "assistant" if output else "user"),
            "content": flat.get("content", ""),
        }
        if flat.get("finish_reason") not in (None, ""):
            source["finish_reason"] = flat["finish_reason"]
        calls: dict[int, dict[str, Any]] = defaultdict(dict)
        for key, value in flat.items():
            if match := re.match(r"tool_calls\.(\d+)\.(?:function\.)?(.+)", key):
                calls[int(match.group(1))][match.group(2)] = value
        if calls:
            source["tool_calls"] = []
            for call_index in sorted(calls):
                call = calls[call_index]
                arguments = parse_value(call.get("arguments", {}))
                source["tool_calls"].append(
                    {
                        "id": call.get("id", ""),
                        "name": call.get("name", ""),
                        "arguments": arguments,
                    }
                )
        if flat.get("tool_call_id") not in (None, ""):
            source["tool_call_id"] = flat["tool_call_id"]
        if message := parse_message(source, default_role="assistant" if output else "user", output=output):
            messages.append(message)
    return messages


def split_system_messages(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    instructions: list[dict[str, Any]] = []
    regular: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "system":
            instructions.extend(deepcopy(message.get("parts", [])))
        else:
            regular.append(message)
    return instructions, regular


def parse_instructions(value: Any) -> list[dict[str, Any]]:
    parsed = parse_value(value)
    if isinstance(parsed, dict) and isinstance(parsed.get("parts"), list):
        values = parsed["parts"]
    elif isinstance(parsed, list):
        values = parsed
    elif isinstance(parsed, dict):
        message = parse_message(parsed, default_role="system")
        return message.get("parts", []) if message else []
    else:
        values = [parsed]
    return [part for item in values if (part := _normalize_part(item))]


def _normalize_schema_types(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (item.lower() if key == "type" and isinstance(item, str) else _normalize_schema_types(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_schema_types(item) for item in value]
    return value


def parse_definitions(value: Any) -> list[dict[str, Any]]:
    parsed = parse_value(value)
    values = parsed if isinstance(parsed, list) else [parsed]
    flattened: list[Any] = []
    for item in values:
        if isinstance(item, dict) and isinstance(item.get("function_declarations"), list):
            flattened.extend(item["function_declarations"])
        else:
            flattened.append(item)
    result = []
    for item in flattened:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if isinstance(item.get("function"), dict) else item
        if function.get("name") in (None, ""):
            continue
        definition = {
            "type": str(item.get("type", "function")),
            "name": str(function["name"]),
        }
        if function.get("description") is not None:
            definition["description"] = str(function["description"])
        if function.get("parameters") is not None:
            definition["parameters"] = _normalize_schema_types(deepcopy(function["parameters"]))
        result.append(definition)
    return result


def parse_indexed_definitions(attrs: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = defaultdict(dict)
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)\.(.+)$")
    for key, value in attrs.items():
        if match := pattern.match(key):
            grouped[int(match.group(1))][match.group(2)] = value
    result = []
    for index in sorted(grouped):
        item = grouped[index]
        parameters = parse_value(item.get("parameters", {}))
        if item.get("name") not in (None, ""):
            result.append(
                {
                    "type": "function",
                    "name": str(item["name"]),
                    "description": str(item.get("description", "")),
                    "parameters": _normalize_schema_types(parameters),
                }
            )
    return result


def parse_standard_content(attrs: dict[str, Any]) -> ContentState:
    """读取标准 OTel 正文字段，供产品映射在缺失时补充。"""
    state = ContentState()
    inputs = parse_messages(attrs.get("gen_ai.input.messages"))
    outputs = parse_messages(attrs.get("gen_ai.output.messages"), output=True)
    system, inputs = split_system_messages(inputs)
    state.inputs.extend(inputs)
    state.outputs.extend(outputs)

    if attrs.get("gen_ai.system_instructions") is not None:
        state.instructions.extend(parse_instructions(attrs["gen_ai.system_instructions"]))
    else:
        state.instructions.extend(system)

    if attrs.get("gen_ai.tool.definitions") is not None:
        state.definitions.extend(parse_definitions(attrs["gen_ai.tool.definitions"]))
    for key in (
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
        "gen_ai.retrieval.documents",
    ):
        if attrs.get(key) is not None:
            state.attributes[key] = parse_value(attrs[key])
    if attrs.get("gen_ai.retrieval.query.text") is not None:
        state.attributes["gen_ai.retrieval.query.text"] = str(attrs["gen_ai.retrieval.query.text"])
    return state
