"""把各方言的正文压缩为协议标准中的消息、工具和系统指令字段。"""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from typing import Any

from .fields import FINISH_REASONS
from .utils import safe_parse as _safe_parse


def _role(value: Any, default: str) -> str:
    return {
        "human": "user",
        "ai": "assistant",
        "model": "assistant",
        "chatgeneration": "assistant",
        "aichunk": "assistant",
    }.get(str(value or default).lower(), str(value or default).lower())


def _parsed(value: Any) -> tuple[Any, bool]:
    parsed, failed = _safe_parse(value)
    # plain text 是协议允许的来源形态，不应当被当成 JSON 解析告警。
    structured = isinstance(value, str) and value.lstrip().startswith(("{", "[", "("))
    return (value if failed else parsed), failed and structured


def _part(value: Any) -> dict[str, Any] | None:
    """把 OTel Part、Gemini Part 或纯文本归一为 OTel Part。"""
    if not isinstance(value, dict):
        return {"type": "text", "content": str(value)} if value not in (None, "") else None
    if value.get("type"):
        part = deepcopy(value)
        if part["type"] in {"text", "reasoning"} and "content" not in part:
            part["content"] = str(part.pop("text", ""))
        return part
    if value.get("text") not in (None, ""):
        return {
            "type": "reasoning" if value.get("thought") is True else "text",
            "content": str(value["text"]),
        }
    call = value.get("function_call")
    if isinstance(call, dict):
        arguments, _ = _parsed(call.get("args", call.get("arguments", {})))
        part = {
            "type": "tool_call",
            "name": str(call.get("name", "")),
            "arguments": arguments,
        }
        if call.get("id") not in (None, ""):
            part["id"] = str(call["id"])
        return part
    response = value.get("function_response")
    if isinstance(response, dict):
        result, _ = _parsed(response.get("response", {}))
        part = {"type": "tool_call_response", "response": result}
        if response.get("id") not in (None, ""):
            part["id"] = str(response["id"])
        return part
    return None


def _message_parts(message: dict[str, Any], role: str) -> list[dict[str, Any]]:
    parts = [part for value in message.get("parts", []) if (part := _part(value))]
    content = message.get("content")
    if not parts and content not in (None, ""):
        if role == "tool":
            response, _ = _parsed(content)
            part: dict[str, Any] = {"type": "tool_call_response", "response": response}
            call_id = message.get("tool_call_id", message.get("tool_id"))
            if call_id not in (None, ""):
                part["id"] = str(call_id)
            parts.append(part)
        elif isinstance(content, list):
            parts.extend(part for value in content if (part := _part(value)))
        else:
            parts.append({"type": "text", "content": str(content)})

    calls = message.get("tool_calls", message.get("tool_call", []))
    if isinstance(calls, dict):
        calls = [calls]
    for call in calls if isinstance(calls, list) else []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        arguments, _ = _parsed(function.get("arguments", function.get("args", {})))
        part = {
            "type": "tool_call",
            "name": str(function.get("name", "")),
            "arguments": arguments,
        }
        if call.get("id") not in (None, ""):
            part["id"] = str(call["id"])
        parts.append(part)
    return parts


def _message(value: Any, *, default_role: str, output: bool = False) -> dict[str, Any] | None:
    parsed, _ = _parsed(value)
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
    role = _role(message.get("role"), default_role)
    parts = _message_parts(message, role)
    if any(part.get("type") == "tool_call_response" for part in parts):
        role = "tool"
    if not parts:
        return None
    result: dict[str, Any] = {"role": role, "parts": parts}
    if output and message.get("finish_reason") not in (None, ""):
        reason = str(message["finish_reason"])
        result["finish_reason"] = FINISH_REASONS.get(reason, reason)
    return result


def _messages(value: Any, *, output: bool = False) -> tuple[list[dict[str, Any]], bool]:
    parsed, failed = _parsed(value)
    if isinstance(parsed, dict):
        for key in ("messages", "input", "output"):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
    values = parsed if isinstance(parsed, list) else [parsed]
    default_role = "assistant" if output else "user"
    return [message for item in values if (message := _message(item, default_role=default_role, output=output))], failed


def _indexed(attrs: dict[str, Any], prefix: str, *, output: bool) -> tuple[list[dict[str, Any]], bool]:
    grouped: dict[int, dict[str, Any]] = defaultdict(dict)
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)\.(.+)$")
    for key, value in attrs.items():
        if match := pattern.match(key):
            grouped[int(match.group(1))][match.group(2)] = value
    failed = False
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
                arguments, parse_failed = _parsed(call.get("arguments", {}))
                failed = failed or parse_failed
                source["tool_calls"].append(
                    {
                        "id": call.get("id", ""),
                        "name": call.get("name", ""),
                        "arguments": arguments,
                    }
                )
        if flat.get("tool_call_id") not in (None, ""):
            source["tool_call_id"] = flat["tool_call_id"]
        if message := _message(source, default_role="assistant" if output else "user", output=output):
            messages.append(message)
    return messages, failed


def _split_system(
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


def _instructions(value: Any) -> tuple[list[dict[str, Any]], bool]:
    parsed, failed = _parsed(value)
    if isinstance(parsed, dict) and isinstance(parsed.get("parts"), list):
        values = parsed["parts"]
    elif isinstance(parsed, list):
        values = parsed
    elif isinstance(parsed, dict):
        message = _message(parsed, default_role="system")
        return (message.get("parts", []) if message else []), failed
    else:
        values = [parsed]
    return [part for item in values if (part := _part(item))], failed


def _schema_lower(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (item.lower() if key == "type" and isinstance(item, str) else _schema_lower(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_schema_lower(item) for item in value]
    return value


def _definitions(value: Any) -> tuple[list[dict[str, Any]], bool]:
    parsed, failed = _parsed(value)
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
            definition["parameters"] = _schema_lower(deepcopy(function["parameters"]))
        result.append(definition)
    return result, failed


def _indexed_definitions(attrs: dict[str, Any], prefix: str) -> tuple[list[dict[str, Any]], bool]:
    grouped: dict[int, dict[str, Any]] = defaultdict(dict)
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)\.(.+)$")
    for key, value in attrs.items():
        if match := pattern.match(key):
            grouped[int(match.group(1))][match.group(2)] = value
    failed = False
    result = []
    for index in sorted(grouped):
        item = grouped[index]
        parameters, parse_failed = _parsed(item.get("parameters", {}))
        failed = failed or parse_failed
        if item.get("name") not in (None, ""):
            result.append(
                {
                    "type": "function",
                    "name": str(item["name"]),
                    "description": str(item.get("description", "")),
                    "parameters": _schema_lower(parameters),
                }
            )
    return result, failed


parse_value = _parsed
parse_message = _message
parse_messages = _messages
indexed_messages = _indexed
split_system = _split_system
parse_instructions = _instructions
parse_definitions = _definitions
indexed_definitions = _indexed_definitions


def tool_calls(messages: Any) -> list[dict[str, Any]]:
    """列出标准消息中的工具调用，供 AgentLens TOOL span 回填 call.id。"""
    if not isinstance(messages, list):
        return []
    return [
        part
        for message in messages
        if isinstance(message, dict)
        for part in message.get("parts", [])
        if isinstance(part, dict) and part.get("type") == "tool_call"
    ]
