"""AgentLens 转换，并兼容同一 Trace 内的标准 OTel 子 Span。"""

from __future__ import annotations

from typing import Any

from .content import (
    parse_definitions,
    parse_indexed_definitions,
    parse_indexed_messages,
    parse_messages,
    parse_standard_content,
    parse_value,
    split_system_messages,
)
from .fields import normalize_operation, project_span
from .utils import first


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


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span["attributes"]
    state = parse_standard_content(attrs)

    if not state.inputs:
        inputs = parse_indexed_messages(attrs, "gen_ai.prompts", output=False)
        if not inputs and attrs.get("input.value") is not None:
            inputs = parse_messages(attrs["input.value"])
        system, inputs = split_system_messages(inputs)
        state.inputs.extend(inputs)
        if not state.instructions:
            state.instructions.extend(system)
    if not state.outputs:
        outputs = parse_indexed_messages(attrs, "gen_ai.completion", output=True)
        if not outputs and attrs.get("output.value") is not None:
            outputs = parse_messages(attrs["output.value"], output=True)
        state.outputs.extend(outputs)
    if not state.definitions:
        if attrs.get("gen_ai.request.tools") is not None:
            state.definitions.extend(parse_definitions(attrs["gen_ai.request.tools"]))
        if not state.definitions:
            state.definitions.extend(parse_indexed_definitions(attrs, "gen_ai.request.functions"))
    for target, keys in {
        "gen_ai.tool.call.arguments": ("tool.input", "traceloop.entity.input"),
        "gen_ai.tool.call.result": ("tool.output", "traceloop.entity.output"),
    }.items():
        if target not in state.attributes and (value := first(attrs, *keys)) is not None:
            state.attributes[target] = parse_value(value)
    return state.build()


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """转换 AgentLens，以及混合在同一 Trace 内的标准 OTel Span。"""
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        content = convert_content(span)
        converted = project_span(
            span,
            operation=normalize_operation(attrs.get("gen_ai.operation.name")),
            provider=provider(attrs),
            aliases=aliases(),
            extra={},
            content=content,
        )
        if converted:
            spans.append(converted)
    return spans
