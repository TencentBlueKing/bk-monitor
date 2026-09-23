"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import ast
import json
from typing import Any

from apm_web.llm.constants import STANDARD_FIELDS
from constants.apm import LLMProduct

from . import adapter_default
from .fields import OPERATION_NAME_ALIASES
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

ROLE_MAP = {
    "human": "user",
    "humanmessage": "user",
    "ai": "assistant",
    "aimessage": "assistant",
    "chatgeneration": "assistant",
    "aichunk": "assistant",
    "systemmessage": "system",
    "toolmessage": "tool",
}
ALIASES = {
    "gen_ai.provider.name": ("gen_ai.system",),
    "gen_ai.agent.name": (
        "gen_ai.entity.name",
        "gen_ai.chain.name",
        "agent.info.name",
    ),
    "gen_ai.conversation.id": ("agent.session.session_code",),
    "user.id": ("agent.session.caller_executor",),
    "user.name": ("agent.session.caller_executor",),
    "gen_ai.agent.id": ("agent.info.id",),
    "gen_ai.usage.input_tokens": ("gen_ai.usage.prompt_tokens",),
    "gen_ai.usage.output_tokens": ("gen_ai.usage.completion_tokens",),
    "gen_ai.usage.cache_read.input_tokens": ("gen_ai.usage.cache_read_input_tokens",),
    "gen_ai.usage.cache_write.input_tokens": (
        "gen_ai.usage.cache_creation.input_tokens",
        "gen_ai.usage.cache_creation_input_tokens",
        "gen_ai.usage.cache_write_input_tokens",
    ),
    "gen_ai.usage.reasoning.output_tokens": ("gen_ai.usage.reasoning_tokens",),
    "gen_ai.tool.name": ("tool.name",),
    "gen_ai.request.model": ("gen_ai.model_name",),
}


def parse_nested(value: Any) -> Any:
    """Parse nested JSON strings emitted by Traceloop without changing plain text."""
    original: Any = value
    for _ in range(3):
        if not isinstance(value, str):
            return value
        try:
            parsed: Any = json.loads(value)
        except ValueError:
            parsed = safe_parse(value)
        if isinstance(parsed, dict | list):
            return parsed
        if not isinstance(parsed, str) or parsed == value:
            break
        value = parsed
    return original


def traceloop_payload(value: Any, wrapper: str) -> Any:
    """Unwrap Traceloop's inputs/outputs and LangChain message containers."""
    payload = parse_nested(value)
    if isinstance(payload, dict) and wrapper in payload:
        payload = parse_nested(payload[wrapper])
    if isinstance(payload, dict) and "messages" in payload:
        payload = parse_nested(payload["messages"])
    if isinstance(payload, dict):
        kwargs = parse_nested(payload.get("kwargs"))
        if isinstance(kwargs, dict) and "messages" in kwargs:
            payload = parse_nested(kwargs["messages"])
    return payload


def traceloop_tool_value(value: Any, *, output: bool) -> Any:
    """Unwrap the arguments/result carried by a Traceloop tool span."""
    payload: Any = parse_nested(value)
    if not isinstance(payload, dict):
        return payload
    if output:
        # LangChain 回调同时上报结果和 kwargs；装饰器直接上报业务结果。
        if isinstance(payload.get("kwargs"), dict) and ("output" in payload or "outputs" in payload):
            return parse_nested(first(payload, "output", "outputs"))
        return payload
    if isinstance(payload.get("args"), list) and isinstance(payload.get("kwargs"), dict):
        # 位置参数没有参数名，保留 args/kwargs 结构以免丢失信息。
        return payload if payload["args"] else payload["kwargs"]
    arguments: Any = first(payload, "inputs", "input_str")
    return parse_nested(arguments) if arguments is not None else payload


def tool_result(value: Any) -> Any:
    """Parse JSON and the LangChain ToolMessage repr emitted by AIDev."""
    parsed = parse_nested(value)
    if not isinstance(parsed, str) or not parsed.startswith("content="):
        return parsed

    content_and_name, separator, tool_call_id = parsed.rpartition(" tool_call_id=")
    if not separator:
        return parsed
    content, separator, name = content_and_name.rpartition(" name=")
    if not separator:
        return parsed
    try:
        # Validate all three repr fragments before accepting this known envelope.
        ast.literal_eval(name)
        ast.literal_eval(tool_call_id)
        content = ast.literal_eval(content.removeprefix("content="))
    except (SyntaxError, ValueError):
        return parsed
    return parse_nested(content)


def traceloop_context(attrs: dict[str, Any]) -> dict[str, Any]:
    """Read conversation and user context nested in a Traceloop workflow input."""
    root = parse_nested(attrs.get("traceloop.entity.input"))
    if not isinstance(root, dict):
        return {}
    inputs = parse_nested(root.get("inputs"))
    metadata = parse_nested(root.get("metadata"))
    execute_kwargs = parse_nested(inputs.get("execute_kwargs")) if isinstance(inputs, dict) else None
    if not isinstance(execute_kwargs, dict):
        execute_kwargs = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "conversation_id": first(execute_kwargs, "session_code", "thread_id") or first(metadata, "thread_id"),
        "user_id": first(execute_kwargs, "caller_executor", "executor"),
    }


def operation(span: dict[str, Any]) -> str | None:
    attrs = span["attributes"]
    if standard_operation := attrs.get("gen_ai.operation.name"):
        return str(standard_operation).lower()

    request_type = str(attrs.get("llm.request.type", "")).lower()
    if request_type:
        return OPERATION_NAME_ALIASES[LLMProduct.AIDEV.value].get(request_type, request_type)

    span_name = str(span.get("span_name", ""))
    traceloop_kind = str(attrs.get("traceloop.span.kind", "")).lower()
    if span_name == "chain.workflow" or attrs.get("chain.type") == "workflow" or traceloop_kind == "workflow":
        return "invoke_workflow"
    if span_name == "agent.execution" or traceloop_kind == "agent":
        return "invoke_agent"
    if span_name in {"chat_model.generate", "ChatModel.chat"} or traceloop_kind == "llm":
        return "chat"
    if (
        attrs.get("tool.name")
        or traceloop_kind == "tool"
        or span_name == "tool.execution"
        or span_name.endswith(".tool")
    ):
        return "execute_tool"
    return None


def standard_messages(value: Any) -> list[dict[str, Any]] | None:
    """Return messages only when the value already has the standard shape."""
    messages = parse_nested(value)
    if not isinstance(messages, list) or not messages:
        return None
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str):
            return None
        parts = message.get("parts")
        if not isinstance(parts, list):
            return None
        if any(not isinstance(part, dict) or not isinstance(part.get("type"), str) for part in parts):
            return None
    return messages


def flatten_message_envelopes(value: Any) -> list[Any]:
    """Flatten AIDev's batches while leaving message payloads untouched."""
    items = parse_nested(value)
    if items in (None, ""):
        return []
    if not isinstance(items, list):
        return [items]

    flattened: list[Any] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(flatten_message_envelopes(item))
        else:
            flattened.append(item)
    return flattened


def parse_langchain_messages(value: Any, default_role: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for envelope in flatten_message_envelopes(value):
        if not isinstance(envelope, dict):
            messages.append(text_message(default_role, envelope))
            continue
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
        kwargs = parse_nested(envelope.get("kwargs"))
        if isinstance(kwargs, dict):
            data = kwargs
        source_role = str(data.get("role") or data.get("type") or envelope.get("type") or default_role).lower()
        if source_role == "constructor" and isinstance(envelope.get("id"), list) and envelope["id"]:
            source_role = str(envelope["id"][-1]).lower()
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
    messages = []
    for item in indexed(attrs, prefix):
        if item.get("content") in (None, ""):
            continue
        role = str(item.get("role") or default_role).lower()
        if role == "unknown":
            role = default_role
        messages.append(text_message(ROLE_MAP.get(role, role), item["content"]))
    return messages


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

    standard_inputs = standard_messages(attrs.get("gen_ai.input.messages"))
    if standard_inputs is not None:
        content["gen_ai.input.messages"] = standard_inputs
    else:
        content.pop("gen_ai.input.messages", None)
        inputs = parse_langchain_messages(attrs.get("gen_ai.input.messages"), "user")
        if not inputs:
            inputs = parse_indexed_messages(attrs, "gen_ai.prompt", "user")
            if (input_value := first(attrs, "llm.input", "agent.session.input")) is not None:
                inputs = parse_langchain_messages(input_value, "user")
            elif operation(span) and (input_value := attrs.get("traceloop.entity.input")) is not None:
                inputs = parse_langchain_messages(traceloop_payload(input_value, "inputs"), "user")
        instructions, inputs = split_system(inputs)
        put(content, "gen_ai.system_instructions", instructions)
        put(content, "gen_ai.input.messages", inputs)

    standard_outputs = standard_messages(attrs.get("gen_ai.output.messages"))
    if standard_outputs is not None:
        content["gen_ai.output.messages"] = standard_outputs
    else:
        content.pop("gen_ai.output.messages", None)
        outputs = parse_langchain_messages(attrs.get("gen_ai.output.messages"), "assistant")
        if not outputs:
            outputs = parse_indexed_messages(attrs, "gen_ai.completion", "assistant")
            if (output_value := first(attrs, "llm.output", "agent.session.output")) is not None:
                outputs = parse_langchain_messages(output_value, "assistant")
            elif operation(span) and (output_value := attrs.get("traceloop.entity.output")) is not None:
                outputs = parse_langchain_messages(traceloop_payload(output_value, "outputs"), "assistant")
        put(content, "gen_ai.output.messages", outputs)
    put(content, "gen_ai.tool.definitions", parse_definitions(attrs.get("gen_ai.request.tools")))
    arguments = safe_parse(first(attrs, "tool.input", "input.value"))
    result = tool_result(first(attrs, "tool.output", "output.value"))
    if operation(span) == "execute_tool":
        if arguments is None and (value := attrs.get("traceloop.entity.input")) is not None:
            arguments = traceloop_tool_value(value, output=False)
        if result is None and (value := attrs.get("traceloop.entity.output")) is not None:
            result = traceloop_tool_value(value, output=True)
    put(content, "gen_ai.tool.call.arguments", arguments)
    put(content, "gen_ai.tool.call.result", result)
    return content


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """先按标准 OTel 转换；带 operation.name 的视为新语义，其余再走存量规则。"""
    standard_by_span_id: dict[str, dict[str, Any]] = {}
    for converted in adapter_default.convert(raw):
        operation_name = converted["attributes"].get("gen_ai.operation.name")
        if isinstance(operation_name, str) and operation_name.strip():
            standard_by_span_id[converted["span_id"]] = converted

    leftover = [span for span in raw if span["span_id"] not in standard_by_span_id]
    legacy_by_span_id = {span["span_id"]: span for span in _convert_legacy(leftover)}

    spans: list[dict[str, Any]] = []
    for span in raw:
        converted = standard_by_span_id.get(span["span_id"]) or legacy_by_span_id.get(span["span_id"])
        if converted is not None:
            spans.append(converted)
    return spans


def _convert_legacy(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        span_operation = operation(span)
        if not span_operation:
            continue
        attributes = {
            key: value for key, value in attrs.items() if key in STANDARD_FIELDS and value not in (None, "", [])
        }
        put(attributes, "gen_ai.operation.name", span_operation)
        for target, source_keys in ALIASES.items():
            value = first(attrs, *source_keys)
            if target.startswith("gen_ai.usage."):
                value = nonnegative_int(value)
            elif target == "gen_ai.agent.id" and value is not None:
                value = str(value)
            put(attributes, target, value)
        if span_operation == "execute_tool":
            put(attributes, "gen_ai.tool.name", attrs.get("traceloop.entity.name"))
        elif span_operation in {"invoke_agent", "invoke_workflow"}:
            put(attributes, "gen_ai.agent.name", attrs.get("traceloop.entity.name"))
        if span_operation:
            context = traceloop_context(attrs)
            put(attributes, "gen_ai.conversation.id", context.get("conversation_id"))
            put(attributes, "user.id", context.get("user_id"))
            put(attributes, "user.name", context.get("user_id"))
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
