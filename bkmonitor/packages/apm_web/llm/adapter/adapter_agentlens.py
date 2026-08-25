"""AgentLens 转换，并兼容同一 Trace 内的标准 OTel 子 Span。"""

from __future__ import annotations

from typing import Any

from .content import (
    indexed_definitions,
    indexed_messages,
    parse_definitions,
    parse_instructions,
    parse_messages,
    parse_value,
    split_system,
)
from .fields import (
    KIND_OPERATIONS,
    OPERATION_KIND,
    SpanIdentity,
    normalize_operation,
    project_span,
)
from .utils import first


def identify_span(span: dict[str, Any]) -> SpanIdentity:
    attrs = span["attributes"]
    name = span["span_name"].lower()
    operation = str(attrs.get("gen_ai.operation.name", "")).lower()
    span_kind = str(attrs.get("gen_ai.span.kind", "")).lower()

    if span_kind in {"agent", "llm", "tool"} or any(
        key.startswith(("gen_ai.prompts.", "gen_ai.completion.")) for key in attrs
    ):
        kind = span_kind or OPERATION_KIND.get(operation, "other")
        return SpanIdentity("agentlens", kind, "attributes", kind != "other")
    if operation:
        return SpanIdentity("otel", OPERATION_KIND.get(operation, "other"))
    if attrs.get("gen_ai.tool.name") not in (None, ""):
        return SpanIdentity("otel", "tool")
    if any(attrs.get(key) not in (None, "") for key in ("gen_ai.agent.id", "gen_ai.agent.name")):
        return SpanIdentity("otel", "agent")
    if any(
        attrs.get(key) not in (None, "")
        for key in (
            "gen_ai.provider.name",
            "gen_ai.request.model",
            "gen_ai.response.model",
        )
    ):
        return SpanIdentity("otel", "llm")
    for suffix, kind in ((".llm", "llm"), (".tool", "tool"), (".agent", "agent")):
        if name.endswith(suffix):
            return SpanIdentity("agentlens", kind, "name-fallback")
    return SpanIdentity("unknown", "other", "generic", False)


def operation(_attrs: dict[str, Any], identity: SpanIdentity, explicit: str | None) -> str | None:
    if identity.dialect == "agentlens" and identity.kind != "llm":
        return KIND_OPERATIONS.get(identity.kind)
    return explicit or KIND_OPERATIONS.get(identity.kind)


def provider(attrs: dict[str, Any], identity: SpanIdentity) -> Any:
    value = attrs.get("gen_ai.provider.name")
    return attrs.get("gen_ai.system") if value is None and identity.dialect == "agentlens" else value


def aliases(identity: SpanIdentity) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {
        "gen_ai.conversation.id": ("gen_ai.session.id",),
        "user.id": ("gen_ai.user.id",),
    }
    if identity.kind == "tool":
        values["gen_ai.tool.name"] = ("tool.name", "traceloop.entity.name")
    if identity.kind == "agent":
        values["gen_ai.agent.name"] = (
            "gen_ai.entity.name",
            "gen_ai.chain.name",
            "agent.info.name",
        )
        values["gen_ai.request.model"] = ("gen_ai.model_name",)
    return values


def extra_attributes(_attrs: dict[str, Any], identity: SpanIdentity) -> dict[str, Any]:
    return {"gen_ai.tool.type": "function"} if identity.kind == "tool" else {}


def merge(spans: list[dict[str, Any]], _warnings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    return spans, {}


def convert_content(span: dict[str, Any], identity: SpanIdentity) -> tuple[dict[str, Any], bool]:
    attrs = span["attributes"]
    failed = False
    if identity.dialect == "agentlens":
        inputs, failed_in = indexed_messages(attrs, "gen_ai.prompts", output=False)
        outputs, failed_out = indexed_messages(attrs, "gen_ai.completion", output=True)
        input_value = attrs.get("input.value") if not inputs and identity.kind == "agent" else None
        output_value = attrs.get("output.value") if not outputs and identity.kind == "agent" else None
        definitions, failed_definitions = indexed_definitions(attrs, "gen_ai.request.functions")
        failed = failed_in or failed_out or failed_definitions
    else:
        inputs, outputs = [], []
        input_value = attrs.get("gen_ai.input.messages")
        output_value = attrs.get("gen_ai.output.messages")
        definitions, failed_definitions = (
            parse_definitions(attrs["gen_ai.request.tools"])
            if attrs.get("gen_ai.request.tools") is not None
            else ([], False)
        )
        failed = failed or failed_definitions
    if input_value is not None:
        parsed, parse_failed = parse_messages(input_value)
        if not parse_failed or not inputs:
            inputs = parsed
        failed = failed or parse_failed
    if output_value is not None:
        parsed, parse_failed = parse_messages(output_value, output=True)
        if not parse_failed or not outputs:
            outputs = parsed
        failed = failed or parse_failed

    system, inputs = split_system(inputs)
    content: dict[str, Any] = {}
    if inputs:
        content["gen_ai.input.messages"] = inputs
    if outputs:
        content["gen_ai.output.messages"] = outputs
    if system:
        content["gen_ai.system_instructions"] = system
    if definitions:
        content["gen_ai.tool.definitions"] = definitions

    if attrs.get("gen_ai.system_instructions") is not None and not system:
        content["gen_ai.system_instructions"], parse_failed = parse_instructions(attrs["gen_ai.system_instructions"])
        failed = failed or parse_failed
    if identity.kind == "tool":
        for target, keys in {
            "gen_ai.tool.call.arguments": (
                "gen_ai.tool.call.arguments",
                "tool.input",
                "input.value",
                "traceloop.entity.input",
            ),
            "gen_ai.tool.call.result": (
                "gen_ai.tool.call.result",
                "tool.output",
                "output.value",
                "traceloop.entity.output",
            ),
        }.items():
            if (value := first(attrs, *keys)) is not None:
                content[target], parse_failed = parse_value(value)
                failed = failed or parse_failed
    for key in ("gen_ai.tool.definitions", "gen_ai.retrieval.documents"):
        if key in attrs and key not in content:
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
    """转换 AgentLens，以及混合在同一 Trace 内的标准 OTel Span。"""
    spans: list[dict[str, Any]] = []
    for span in raw:
        identity = identify_span(span)
        if not identity.is_ai_step:
            continue
        attrs = span["attributes"]
        content, failed = convert_content(span, identity) if include_content else ({}, False)
        converted = project_span(
            span,
            identity,
            operation=operation(
                attrs,
                identity,
                normalize_operation(attrs.get("gen_ai.operation.name")),
            ),
            provider=provider(attrs, identity),
            aliases=aliases(identity),
            extra=extra_attributes(attrs, identity),
            content=content,
            parse_failed=failed,
            warnings=warnings,
        )
        if converted:
            spans.append(converted)
    return merge(spans, warnings)
