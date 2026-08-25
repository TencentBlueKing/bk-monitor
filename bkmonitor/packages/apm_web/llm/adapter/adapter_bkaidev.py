"""BKAIDev 固定转换规则。"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .content import (
    indexed_messages,
    parse_definitions,
    parse_instructions,
    parse_messages,
    parse_value,
    split_system,
)
from .fields import KIND_OPERATIONS, SpanIdentity, normalize_operation, project_span
from .utils import first

BKA_NAMES = {
    "agent.execution": ("agent", "business"),
    "chain.workflow": ("workflow", "business"),
    "langgraph.workflow": ("workflow", "traceloop"),
    "chat_model.generate": ("llm", "business"),
    "chatmodel.chat": ("llm", "traceloop"),
    "tool.execution": ("tool", "business"),
}
BKA_TASK_NAMES = {"model.task", "model_node.task", "tools.task", "chain.task"}
REQUEST_OPERATIONS = {
    "chat": "chat",
    "completion": "text_completion",
    "embedding": "embeddings",
    "rerank": "retrieval",
}


def identify_span(span: dict[str, Any]) -> SpanIdentity:
    attrs = span["attributes"]
    name = span["span_name"].lower()
    if name in BKA_TASK_NAMES:
        return SpanIdentity("bkaidev", "other", "traceloop", False)
    if name in BKA_NAMES:
        kind, default_variant = BKA_NAMES[name]
    elif name.endswith(".tool") or attrs.get("tool.name"):
        kind, default_variant = "tool", "traceloop"
    else:
        return SpanIdentity("bkaidev", "other", "generic", False)
    business = any(key.startswith(("agent.info.", "agent.session.")) for key in attrs)
    return SpanIdentity(
        "bkaidev",
        kind,
        "business" if business else default_variant,
        kind != "other",
    )


def operation(attrs: dict[str, Any], identity: SpanIdentity, explicit: str | None) -> str | None:
    request_type = str(attrs.get("llm.request.type", "")).lower()
    if request_type:
        return REQUEST_OPERATIONS.get(request_type, request_type)
    return explicit or KIND_OPERATIONS.get(identity.kind)


def provider(attrs: dict[str, Any], _identity: SpanIdentity) -> Any:
    return attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system")


def aliases(identity: SpanIdentity) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {
        "gen_ai.agent.name": ("agent.info.name",),
        "gen_ai.conversation.id": ("agent.session.session_code",),
        "user.name": ("agent.session.caller_executor",),
        "gen_ai.agent.id": ("agent.info.id",),
        "gen_ai.usage.input_tokens": ("gen_ai.usage.prompt_tokens",),
        "gen_ai.usage.output_tokens": ("gen_ai.usage.completion_tokens",),
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


def extra_attributes(_attrs: dict[str, Any], _identity: SpanIdentity) -> dict[str, Any]:
    return {}


def _operation_of(span: dict[str, Any]) -> str | None:
    value = span["attributes"].get("gen_ai.operation.name")
    return str(value) if value not in (None, "") else None


def merge(spans: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """合并 BKAIDev business 与 Traceloop 的双埋点 Span。"""
    business = [(index, span) for index, span in enumerate(spans) if span["_variant"] == "business"]
    wrappers = [(index, span) for index, span in enumerate(spans) if span["_variant"] == "traceloop"]
    candidates: list[tuple[tuple[int, int, str, str], int, int]] = []
    for left_index, left in business:
        for right_index, right in wrappers:
            operation = _operation_of(left)
            if operation not in {"invoke_workflow", "execute_tool"}:
                continue
            if operation != _operation_of(right):
                continue
            left_key = left["attributes"].get("gen_ai.request.model") or left["attributes"].get("gen_ai.tool.name")
            right_key = right["attributes"].get("gen_ai.request.model") or right["attributes"].get("gen_ai.tool.name")
            if left_key and right_key and left_key != right_key:
                continue
            start_delta = abs(left["start_time"] - right["start_time"])
            duration_delta = abs(left["elapsed_time"] - right["elapsed_time"])
            if start_delta <= 10_000 and duration_delta <= max(
                10_000, int(0.05 * max(left["elapsed_time"], right["elapsed_time"]))
            ):
                candidates.append(
                    (
                        (
                            start_delta,
                            duration_delta,
                            left["span_id"],
                            right["span_id"],
                        ),
                        left_index,
                        right_index,
                    )
                )
    candidates.sort()
    costs: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for cost, left_index, _ in candidates:
        costs[left_index].append(cost[:2])
    ambiguous = {index for index, values in costs.items() if len(values) > 1 and values[0] == values[1]}
    for index in ambiguous:
        warnings.append(
            {
                "code": "dedup_ambiguous",
                "message": "BKAIDev duplicate candidates have the same cost",
                "span_id": spans[index]["span_id"],
            }
        )

    used_left: set[int] = set()
    dropped: set[int] = set()
    redirects: dict[str, str] = {}
    for _, left_index, right_index in candidates:
        if left_index in ambiguous or left_index in used_left or right_index in dropped:
            continue
        primary, secondary = spans[left_index], spans[right_index]
        for key, value in secondary["attributes"].items():
            if key.startswith("gen_ai.usage.") or key not in primary["attributes"]:
                primary["attributes"][key] = deepcopy(value)
        if secondary["status"]["code"] == 2:
            primary["status"] = deepcopy(secondary["status"])
        used_left.add(left_index)
        dropped.add(right_index)
        redirects[secondary["span_id"]] = primary["span_id"]
    return [span for index, span in enumerate(spans) if index not in dropped], redirects


def convert_content(span: dict[str, Any], identity: SpanIdentity) -> tuple[dict[str, Any], bool]:
    attrs = span["attributes"]
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    failed = False
    if identity.kind in {"agent", "workflow", "llm"}:
        input_value = first(attrs, "llm.input", "traceloop.entity.input")
        output_value = first(attrs, "llm.output", "traceloop.entity.output")
        inputs, failed_in = indexed_messages(attrs, "gen_ai.prompt", output=False)
        outputs, failed_out = indexed_messages(attrs, "gen_ai.completion", output=True)
        failed = failed_in or failed_out
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
    if attrs.get("gen_ai.request.tools") is not None:
        definitions, parse_failed = parse_definitions(attrs["gen_ai.request.tools"])
        if definitions:
            content["gen_ai.tool.definitions"] = definitions
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
