"""Galileo 固定转换规则。"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from .content import (
    ContentState,
    parse_definitions,
    parse_instructions,
    parse_message,
    parse_messages,
    parse_standard_content,
    parse_value,
)
from .fields import normalize_operation, project_span
from .utils import safe_parse


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


EventHandler = Callable[[ContentState, Any], None]


def handle_system_event(state: ContentState, detail: Any) -> None:
    state.instructions.extend(parse_instructions(parse_value(detail)))


def handle_message_event(
    state: ContentState,
    detail: Any,
    *,
    role: str,
) -> None:
    if message := parse_message(parse_value(detail), default_role=role):
        state.inputs.append(message)


def handle_messages_event(
    state: ContentState,
    detail: Any,
    *,
    target: str,
    output: bool,
) -> None:
    messages = parse_messages(detail, output=output)
    getattr(state, target).extend(messages)


def handle_definitions_event(state: ContentState, detail: Any) -> None:
    state.definitions.extend(parse_definitions(detail))


def handle_value_event(
    state: ContentState,
    detail: Any,
    *,
    target: str,
) -> None:
    state.attributes[target] = parse_value(detail)


EVENT_HANDLERS: dict[str, EventHandler] = {
    "gen_ai.system.message": handle_system_event,
    "gen_ai.user.message": partial(handle_message_event, role="user"),
    "gen_ai.assistant.message": partial(handle_message_event, role="assistant"),
    "gen_ai.tool.message": partial(handle_message_event, role="tool"),
    "gen_ai.invoke_agent_request": partial(
        handle_messages_event,
        target="inputs",
        output=False,
    ),
    "gen_ai.invoke_agent_response": partial(
        handle_messages_event,
        target="outputs",
        output=True,
    ),
    "gen_ai.tools": handle_definitions_event,
    "gen_ai.tool_call_args": partial(
        handle_value_event,
        target="gen_ai.tool.call.arguments",
    ),
    "gen_ai.tool_response": partial(
        handle_value_event,
        target="gen_ai.tool.call.result",
    ),
}
EVENT_TARGETS = {
    "gen_ai.system.message": "instructions",
    "gen_ai.user.message": "inputs",
    "gen_ai.assistant.message": "inputs",
    "gen_ai.tool.message": "inputs",
    "gen_ai.invoke_agent_request": "inputs",
    "gen_ai.invoke_agent_response": "outputs",
    "gen_ai.tools": "definitions",
    "gen_ai.tool_call_args": "gen_ai.tool.call.arguments",
    "gen_ai.tool_response": "gen_ai.tool.call.result",
}


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    """迁移 Galileo events；gen_ai.choice 按第一版规则丢弃。"""
    attrs = span["attributes"]
    state = parse_standard_content(attrs)
    standard_targets = {
        target
        for target, present in (
            ("instructions", bool(state.instructions)),
            ("inputs", bool(state.inputs)),
            ("outputs", bool(state.outputs)),
            ("definitions", bool(state.definitions)),
            ("gen_ai.tool.call.arguments", "gen_ai.tool.call.arguments" in state.attributes),
            ("gen_ai.tool.call.result", "gen_ai.tool.call.result" in state.attributes),
        )
        if present
    }
    for event in span["events"]:
        target = EVENT_TARGETS.get(event["name"])
        if target in standard_targets:
            continue
        detail = event["attributes"].get("message.detail")
        handler = EVENT_HANDLERS.get(event["name"])
        if detail is not None and handler is not None:
            handler(state, detail)

    if not state.definitions and attrs.get("gen_ai.request.tools") is not None:
        state.definitions.extend(parse_definitions(attrs["gen_ai.request.tools"]))
    return state.build()


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        content = convert_content(span)
        converted = project_span(
            span,
            operation=normalize_operation(attrs.get("gen_ai.operation.name")),
            provider=provider(attrs),
            aliases=aliases(),
            extra=extra_attributes(attrs),
            content=content,
        )
        if converted:
            spans.append(converted)
    return spans
