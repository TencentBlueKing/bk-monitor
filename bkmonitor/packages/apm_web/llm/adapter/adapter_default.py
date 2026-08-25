"""标准 OTel GenAI Span 的保守 fallback。"""

from __future__ import annotations

from typing import Any

from .content import (
    parse_definitions,
    parse_instructions,
    parse_messages,
    parse_value,
    split_system,
)
from .fields import (
    OPERATION_KIND,
    SpanIdentity,
    normalize_operation,
    project_span,
)


def identify_span(span: dict[str, Any]) -> SpanIdentity:
    attrs = span["attributes"]
    operation = normalize_operation(attrs.get("gen_ai.operation.name"))
    if operation:
        return SpanIdentity("otel", OPERATION_KIND.get(operation.lower(), "other"))
    return SpanIdentity("otel", "other", is_ai_step=False)


def convert_content(span: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    attrs = span["attributes"]
    content: dict[str, Any] = {}
    failed = False

    inputs, input_failed = parse_messages(attrs.get("gen_ai.input.messages"))
    outputs, output_failed = parse_messages(attrs.get("gen_ai.output.messages"), output=True)
    system, inputs = split_system(inputs)
    failed = input_failed or output_failed

    if attrs.get("gen_ai.system_instructions") is not None:
        instructions, parse_failed = parse_instructions(attrs["gen_ai.system_instructions"])
        system.extend(instructions)
        failed = failed or parse_failed
    if inputs:
        content["gen_ai.input.messages"] = inputs
    if outputs:
        content["gen_ai.output.messages"] = outputs
    if system:
        content["gen_ai.system_instructions"] = system

    if attrs.get("gen_ai.tool.definitions") is not None:
        definitions, parse_failed = parse_definitions(attrs["gen_ai.tool.definitions"])
        if definitions:
            content["gen_ai.tool.definitions"] = definitions
        failed = failed or parse_failed
    for key in (
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
        "gen_ai.retrieval.documents",
    ):
        if attrs.get(key) is not None:
            content[key], parse_failed = parse_value(attrs[key])
            failed = failed or parse_failed
    if attrs.get("gen_ai.retrieval.query.text") is not None:
        content["gen_ai.retrieval.query.text"] = str(attrs["gen_ai.retrieval.query.text"])
    return content, failed


def convert(
    raw: list[dict[str, Any]],
    *,
    include_content: bool,
    warnings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        identity = identify_span(span)
        if not identity.is_ai_step:
            continue
        attrs = span["attributes"]
        operation = normalize_operation(attrs.get("gen_ai.operation.name"))
        content, failed = convert_content(span) if include_content else ({}, False)
        converted = project_span(
            span,
            identity,
            operation=operation,
            provider=attrs.get("gen_ai.provider.name"),
            aliases={},
            extra={},
            content=content,
            parse_failed=failed,
            warnings=warnings,
        )
        if converted:
            spans.append(converted)
    return spans, {}
