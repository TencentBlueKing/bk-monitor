"""产品转换完成后的 Trace 关系修复、统计和 API 结果组装。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..agent_rules import agent_feature_hits
from .content import tool_calls
from .fields import (
    AGENT_OPERATIONS,
    LLM_OPERATIONS,
    TOOL_OPERATIONS,
    WORKFLOW_OPERATIONS,
    Product,
    operation_of,
)
from .utils import CONTENT_KEY_PARTS

SCHEMA_VERSION = "1.0"
_LLM_OPERATIONS = LLM_OPERATIONS


def _reparent(
    spans: list[dict[str, Any]],
    raw_by_id: dict[str, dict[str, Any]],
    redirects: dict[str, str],
) -> None:
    kept = {span["span_id"] for span in spans}
    for span in spans:
        parent = span["parent_span_id"]
        visited: set[str] = set()
        unresolved = False
        while parent and parent not in kept and parent not in visited:
            visited.add(parent)
            if parent in redirects:
                parent = redirects[parent]
            else:
                raw_parent = raw_by_id.get(parent)
                if raw_parent is None:
                    unresolved = True
                    break
                parent = raw_parent.get("parent_span_id")
        span["parent_span_id"] = parent if parent != span["span_id"] and (parent in kept or unresolved) else None


def _inherit_agent_context(spans: list[dict[str, Any]]) -> None:
    by_id = {span["span_id"]: span for span in spans}
    for span in spans:
        if operation_of(span) != "chat":
            continue
        parent_id = span["parent_span_id"]
        while parent_id and parent_id in by_id:
            parent = by_id[parent_id]
            if operation_of(parent) == "invoke_agent":
                for key in ("gen_ai.conversation.id", "user.id"):
                    if key not in span["attributes"] and key in parent["attributes"]:
                        span["attributes"][key] = parent["attributes"][key]
                break
            parent_id = parent["parent_span_id"]


def _backfill_tool_call_ids(spans: list[dict[str, Any]]) -> None:
    llm_calls = [
        (span, call)
        for span in spans
        if operation_of(span) in LLM_OPERATIONS
        for call in tool_calls(span["attributes"].get("gen_ai.output.messages"))
        if call.get("id") not in (None, "")
    ]
    for tool in spans:
        if operation_of(tool) != "execute_tool" or tool["attributes"].get("gen_ai.tool.call.id"):
            continue
        name = tool["attributes"].get("gen_ai.tool.name")
        matches = [
            (llm, call)
            for llm, call in llm_calls
            if call.get("name") == name
            and llm["start_time"] <= tool["start_time"]
            and (llm["parent_span_id"] == tool["parent_span_id"] or llm["span_id"] == tool["parent_span_id"])
        ]
        if matches:
            _, call = max(matches, key=lambda item: item[0]["start_time"])
            tool["attributes"]["gen_ai.tool.call.id"] = str(call["id"])


def _raw_span(span: dict[str, Any], *, include_content: bool) -> dict[str, Any]:
    raw = deepcopy(span)
    if not include_content:
        raw["attributes"] = {
            key: value for key, value in raw["attributes"].items() if not any(part in key for part in CONTENT_KEY_PARTS)
        }
        for event in raw["events"]:
            event["attributes"] = {
                key: value
                for key, value in event["attributes"].items()
                if not any(part in key for part in CONTENT_KEY_PARTS)
            }
    return raw


def _trace_io(spans: list[dict[str, Any]]) -> dict[str, Any] | None:
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    source = "inferred"
    for span in spans:
        if operation_of(span) not in AGENT_OPERATIONS | WORKFLOW_OPERATIONS:
            continue
        reported_in = span["attributes"].get("gen_ai.input.messages")
        reported_out = span["attributes"].get("gen_ai.output.messages")
        if isinstance(reported_in, list) and reported_in:
            inputs = reported_in
        if isinstance(reported_out, list) and reported_out:
            outputs = reported_out
        if inputs or outputs:
            source = "reported"
            break
    if not inputs:
        for span in spans:
            messages = span["attributes"].get("gen_ai.input.messages")
            if isinstance(messages, list) and messages:
                users = [message for message in messages if message.get("role") == "user"]
                inputs = users[-1:] or messages[-1:]
                break
    if not outputs:
        for span in reversed(spans):
            messages = span["attributes"].get("gen_ai.output.messages")
            if isinstance(messages, list) and messages:
                outputs = messages[-1:]
                break
    return {"input_messages": inputs, "output_messages": outputs, "source": source} if inputs or outputs else None


def build_trace(
    raw: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    redirects: dict[str, str],
    warnings: list[dict[str, Any]],
    *,
    trace_id: str,
    include_content: bool,
    include_raw: bool,
    partial: bool,
    product: Product,
) -> dict[str, Any]:
    """组装产品无关的标准 Trace 响应。"""
    _reparent(spans, {span["span_id"]: span for span in raw}, redirects)
    if product == "galileo":
        _inherit_agent_context(spans)
    _backfill_tool_call_ids(spans)
    spans.sort(key=lambda item: (item["start_time"], item["span_id"]))
    for span in spans:
        span.pop("_variant", None)
    if partial:
        warnings.append({"code": "partial_trace", "message": "The 5000 Span scan limit was reached"})

    llm_spans = [span for span in spans if operation_of(span) in LLM_OPERATIONS]
    tool_spans = [span for span in spans if operation_of(span) in TOOL_OPERATIONS]
    input_tokens = sum(span["attributes"].get("gen_ai.usage.input_tokens", 0) for span in llm_spans)
    output_tokens = sum(span["attributes"].get("gen_ai.usage.output_tokens", 0) for span in llm_spans)
    elapsed_time = max((span["end_time"] for span in raw), default=0) - min(
        (span["start_time"] for span in raw), default=0
    )
    decision_loop = any(
        operation_of(span) in TOOL_OPERATIONS
        and any(operation_of(item) in LLM_OPERATIONS for item in spans[:index])
        and any(operation_of(item) in LLM_OPERATIONS for item in spans[index + 1 :])
        for index, span in enumerate(spans)
    )
    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "classification": {
            "is_gen_ai_trace": bool(spans),
            "is_agent_trace": bool(agent_feature_hits(spans)),
            "is_conversation_trace": any(
                operation_of(span) in AGENT_OPERATIONS | WORKFLOW_OPERATIONS | LLM_OPERATIONS for span in spans
            ),
            "has_decision_loop": decision_loop,
        },
        "summary": {
            "raw_span_count": len(raw),
            "span_count": len(spans),
            "llm_count": len(llm_spans),
            "tool_count": len(tool_spans),
            "error_span_count": sum(span["status"]["code"] == 2 for span in spans),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "elapsed_time": max(0, elapsed_time),
        },
        "trace_io": _trace_io(spans) if include_content else None,
        "spans": spans,
        "warnings": warnings,
    }
    if include_raw:
        response["raw_spans"] = [_raw_span(span, include_content=include_content) for span in raw]
    return response
