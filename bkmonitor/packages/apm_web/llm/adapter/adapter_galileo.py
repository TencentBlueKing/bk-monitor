"""Galileo 固定转换规则。"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .content import (
    parse_definitions,
    parse_instructions,
    parse_message,
    parse_messages,
    parse_value,
)
from .fields import (
    KIND_OPERATIONS,
    OPERATION_KIND,
    SpanIdentity,
    normalize_operation,
    project_span,
)
from .utils import safe_parse


def identify_span(span: dict[str, Any]) -> SpanIdentity:
    attrs = span["attributes"]
    name = span["span_name"].lower()
    operation_name = str(attrs.get("gen_ai.operation.name", "")).lower()
    kind = "workflow" if name == "invocation" else OPERATION_KIND.get(operation_name, "other")
    semantic_event = any(event["name"].startswith("gen_ai.") for event in span["events"])
    feature = any(
        attrs.get(key) not in (None, "")
        for key in (
            "gen_ai.operation.name",
            "gen_ai.agent.id",
            "gen_ai.agent.name",
            "gen_ai.request.model",
            "gen_ai.response.model",
            "gen_ai.tool.name",
        )
    )
    return SpanIdentity("galileo", kind, "events", kind != "other" or semantic_event or feature)


def operation(_attrs: dict[str, Any], identity: SpanIdentity, explicit: str | None) -> str | None:
    if identity.kind == "workflow":
        return "invoke_agent"
    return explicit or KIND_OPERATIONS.get(identity.kind)


def provider(attrs: dict[str, Any], _identity: SpanIdentity) -> Any:
    # gen_ai.system 是 tRPC Agent 运行时名，不是模型 provider。
    return attrs.get("gen_ai.provider.name")


def aliases(identity: SpanIdentity) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {
        "gen_ai.conversation.id": ("gen_ai.session_id",),
        "user.id": ("gen_ai.user.id",),
        "gen_ai.usage.cache_read.input_tokens": ("gen_ai.usage.cache_read_input_tokens",),
        "gen_ai.usage.cache_creation.input_tokens": ("gen_ai.usage.cache_creation_input_tokens",),
        "gen_ai.usage.reasoning.output_tokens": ("gen_ai.usage.reasoning_tokens",),
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


def extra_attributes(attrs: dict[str, Any], identity: SpanIdentity) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if identity.kind == "tool":
        extra["gen_ai.tool.type"] = "function"
    request_model = attrs.get("gen_ai.request.model")
    if request_model is None and identity.kind == "agent":
        request_model = attrs.get("gen_ai.model_name")
    if attrs.get("gen_ai.response.model") is None and request_model:
        extra["gen_ai.response.model"] = request_model
    nested, failed = safe_parse(attrs.get("trpc.python.agent.llm_response"))
    if not failed and isinstance(nested, dict):
        extra["gen_ai.response.id"] = nested.get("response_id")
    return extra


def merge(spans: list[dict[str, Any]], _warnings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """合并 invocation 外层与 agent_run 内层，保留单个 Agent Span。"""
    by_parent: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for span in spans:
        by_parent[span["parent_span_id"]].append(span)
    dropped: set[str] = set()
    redirects: dict[str, str] = {}
    for outer in spans:
        if outer["span_name"].lower() != "invocation":
            continue
        inner = next(
            (item for item in by_parent.get(outer["span_id"], []) if item["span_name"].lower().startswith("agent_run")),
            None,
        )
        if inner is None:
            continue
        for key in (
            "gen_ai.input.messages",
            "gen_ai.output.messages",
            "gen_ai.system_instructions",
        ):
            if key in outer["attributes"]:
                inner["attributes"][key] = deepcopy(outer["attributes"][key])
        inner["parent_span_id"] = outer["parent_span_id"]
        dropped.add(outer["span_id"])
        redirects[outer["span_id"]] = inner["span_id"]
    return [span for span in spans if span["span_id"] not in dropped], redirects


def convert_content(span: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """迁移 Galileo events；gen_ai.choice 按第一版规则丢弃。"""
    attrs = span["attributes"]
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    instructions: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []
    content: dict[str, Any] = {}
    failed = False
    if attrs.get("gen_ai.system_instructions") is not None:
        parts, parse_failed = parse_instructions(attrs["gen_ai.system_instructions"])
        instructions.extend(parts)
        failed = failed or parse_failed
    for event in span["events"]:
        name = event["name"]
        detail = event["attributes"].get("message.detail")
        if detail is None or name == "gen_ai.choice":
            continue
        if name == "gen_ai.system.message":
            parsed, parse_failed = parse_value(detail)
            parts, part_failed = parse_instructions(parsed)
            instructions.extend(parts)
            failed = failed or parse_failed or part_failed
        elif name in {
            "gen_ai.user.message",
            "gen_ai.assistant.message",
            "gen_ai.tool.message",
        }:
            parsed, parse_failed = parse_value(detail)
            default = name.removeprefix("gen_ai.").removesuffix(".message")
            if message := parse_message(parsed, default_role=default):
                inputs.append(message)
            failed = failed or parse_failed
        elif name == "gen_ai.invoke_agent_request":
            messages, parse_failed = parse_messages(detail)
            inputs.extend(messages)
            failed = failed or parse_failed
        elif name == "gen_ai.invoke_agent_response":
            messages, parse_failed = parse_messages(detail, output=True)
            outputs.extend(messages)
            failed = failed or parse_failed
        elif name == "gen_ai.tools":
            values, parse_failed = parse_definitions(detail)
            definitions.extend(values)
            failed = failed or parse_failed
        elif name == "gen_ai.tool_call_args":
            content["gen_ai.tool.call.arguments"], parse_failed = parse_value(detail)
            failed = failed or parse_failed
        elif name == "gen_ai.tool_response":
            content["gen_ai.tool.call.result"], parse_failed = parse_value(detail)
            failed = failed or parse_failed

    if not definitions and attrs.get("gen_ai.request.tools") is not None:
        definitions, parse_failed = parse_definitions(attrs["gen_ai.request.tools"])
        failed = failed or parse_failed
    if instructions:
        content["gen_ai.system_instructions"] = instructions
    if inputs:
        content["gen_ai.input.messages"] = inputs
    if outputs:
        content["gen_ai.output.messages"] = outputs
    if definitions:
        content["gen_ai.tool.definitions"] = definitions
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
    spans: list[dict[str, Any]] = []
    for span in raw:
        identity = identify_span(span)
        if not identity.is_ai_step:
            continue
        attrs = span["attributes"]
        content, failed = convert_content(span) if include_content else ({}, False)
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
