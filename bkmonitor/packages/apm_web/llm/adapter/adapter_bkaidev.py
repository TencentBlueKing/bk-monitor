"""BKAIDev 固定转换规则。"""

from __future__ import annotations

from typing import Any

from .content import (
    parse_definitions,
    parse_indexed_messages,
    parse_messages,
    parse_standard_content,
    parse_value,
    split_system_messages,
)
from .fields import normalize_operation, project_span
from .utils import first

REQUEST_OPERATIONS = {
    "chat": "chat",
    "completion": "text_completion",
    "embedding": "embeddings",
    "rerank": "retrieval",
}


def operation(attrs: dict[str, Any], explicit: str | None) -> str | None:
    request_type = str(attrs.get("llm.request.type", "")).lower()
    if request_type:
        return REQUEST_OPERATIONS.get(request_type, request_type)
    return explicit


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


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span["attributes"]
    state = parse_standard_content(attrs)

    if not state.inputs:
        inputs = parse_indexed_messages(attrs, "gen_ai.prompt", output=False)
        input_value = first(attrs, "llm.input", "traceloop.entity.input")
        if input_value is not None:
            inputs = parse_messages(input_value)
        system, inputs = split_system_messages(inputs)
        state.inputs.extend(inputs)
        if not state.instructions:
            state.instructions.extend(system)
    if not state.outputs:
        outputs = parse_indexed_messages(attrs, "gen_ai.completion", output=True)
        output_value = first(attrs, "llm.output", "traceloop.entity.output")
        if output_value is not None:
            outputs = parse_messages(output_value, output=True)
        state.outputs.extend(outputs)

    for target, keys in {
        "gen_ai.tool.call.arguments": ("tool.input", "input.value"),
        "gen_ai.tool.call.result": ("tool.output", "output.value"),
    }.items():
        if target not in state.attributes and (value := first(attrs, *keys)) is not None:
            state.attributes[target] = parse_value(value)
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
            operation=operation(
                attrs,
                normalize_operation(attrs.get("gen_ai.operation.name")),
            ),
            provider=provider(attrs),
            aliases=aliases(),
            extra={},
            content=content,
        )
        if converted:
            spans.append(converted)
    return spans
