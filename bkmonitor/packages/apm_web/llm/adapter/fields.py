"""产品路由、Span 类型和标准字段投影定义。"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from .utils import first, nonnegative_int

Product = Literal["bkaidev", "galileo", "agentlens", "default"]

OPERATION_KIND = {
    "chat": "llm",
    "generate_content": "llm",
    "text_completion": "llm",
    "embeddings": "llm",
    "fetch_response": "llm",
    "call_llm": "llm",
    "execute_tool": "tool",
    "retrieval": "retriever",
    "search_memory": "retriever",
    "create_agent": "agent",
    "invoke_agent": "agent",
    "agent_run": "agent",
    "plan": "agent",
    "invoke_workflow": "workflow",
    "invocation": "workflow",
}
KIND_OPERATIONS = {
    "agent": "invoke_agent",
    "workflow": "invoke_workflow",
    "llm": "chat",
    "tool": "execute_tool",
    "retriever": "retrieval",
}


@dataclass(frozen=True)
class SpanIdentity:
    dialect: str
    kind: str
    variant: str = "standard"
    is_ai_step: bool = True


def detect_product(spans: list[dict[str, Any]], app_name: str) -> Product:
    """整条 Trace 只选择一次产品转换器。"""
    if app_name.lower().startswith("bkapp_ai"):
        return "bkaidev"
    if any(str(span["resource"].get("telemetry.sdk.name", "")).lower() == "galileo" for span in spans):
        return "galileo"
    if any(
        str(span["attributes"].get("gen_ai.span.kind", "")).lower() in {"agent", "llm", "tool"}
        or any(key.startswith(("gen_ai.prompts.", "gen_ai.completion.")) for key in span["attributes"])
        or span["span_name"].lower().endswith((".agent", ".llm", ".tool"))
        for span in spans
    ):
        return "agentlens"
    return "default"


FINISH_REASONS = {"tool_calls": "tool_call", "tool_call": "tool_call"}
STANDARD_FIELDS = {
    "error.type",
    "user.id",
    "user.name",
    "user.hash",
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.conversation.id",
    "gen_ai.agent.id",
    "gen_ai.agent.name",
    "gen_ai.agent.description",
    "gen_ai.agent.version",
    "gen_ai.request.model",
    "gen_ai.request.temperature",
    "gen_ai.request.reasoning.level",
    "gen_ai.response.id",
    "gen_ai.response.model",
    "gen_ai.response.status",
    "gen_ai.response.finish_reasons",
    "gen_ai.response.time_to_first_chunk",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.usage.cache_creation.input_tokens",
    "gen_ai.usage.reasoning.output_tokens",
    "gen_ai.system_instructions",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.tool.definitions",
    "gen_ai.tool.name",
    "gen_ai.tool.description",
    "gen_ai.tool.type",
    "gen_ai.tool.call.id",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
    "gen_ai.retrieval.query.text",
    "gen_ai.retrieval.top_k",
    "gen_ai.retrieval.documents",
    "gen_ai.data_source.id",
}
PASSTHROUGH_FIELDS = STANDARD_FIELDS - {
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.response.finish_reasons",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.usage.cache_creation.input_tokens",
    "gen_ai.usage.reasoning.output_tokens",
    "gen_ai.system_instructions",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.tool.definitions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
    "gen_ai.retrieval.documents",
}
KNOWN_OPERATIONS = {
    "chat",
    "generate_content",
    "text_completion",
    "embeddings",
    "retrieval",
    "fetch_response",
    "create_agent",
    "invoke_agent",
    "execute_tool",
    "invoke_workflow",
    "plan",
}
KNOWN_PROVIDERS = {
    "openai",
    "anthropic",
    "azure.openai",
    "aws.bedrock",
    "gcp.vertex_ai",
    "gcp.gemini",
    "cohere",
    "mistral_ai",
    "perplexity",
    "xai",
    "deepseek",
}
TOKEN_FIELDS = (
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.usage.cache_creation.input_tokens",
    "gen_ai.usage.reasoning.output_tokens",
)
LLM_OPERATIONS = {
    "chat",
    "generate_content",
    "text_completion",
    "fetch_response",
    "embeddings",
}
TOOL_OPERATIONS = {"execute_tool"}
AGENT_OPERATIONS = {"create_agent", "invoke_agent", "plan"}
WORKFLOW_OPERATIONS = {"invoke_workflow"}


def present(value: Any, *, allow_empty: bool = False) -> bool:
    if value is None:
        return False
    if not allow_empty and isinstance(value, str) and not value.strip():
        return False
    return not isinstance(value, list | dict) or bool(value)


def put(target: dict[str, Any], key: str, value: Any, *, allow_empty: bool = False) -> None:
    if key in STANDARD_FIELDS and key not in target and present(value, allow_empty=allow_empty):
        target[key] = deepcopy(value)


def open_enum(value: Any, known: set[str]) -> str | None:
    if not present(value):
        return None
    original = str(value)
    lowered = original.lower()
    return lowered if lowered in known else original


def normalize_operation(value: Any) -> str | None:
    return open_enum(value, KNOWN_OPERATIONS)


def operation_of(span: dict[str, Any]) -> str | None:
    value = span["attributes"].get("gen_ai.operation.name")
    return str(value) if present(value) else None


def project_span(
    span: dict[str, Any],
    identity: SpanIdentity,
    *,
    operation: str | None,
    provider: Any,
    aliases: dict[str, tuple[str, ...]],
    extra: dict[str, Any],
    content: dict[str, Any],
    parse_failed: bool,
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """把产品转换器给出的结果投影到协议白名单和标准 Span 外层。"""
    attrs = span["attributes"]
    standard: dict[str, Any] = {}
    put(standard, "gen_ai.operation.name", operation)

    for key in PASSTHROUGH_FIELDS:
        value = attrs.get(key)
        if key in {"gen_ai.request.temperature", "gen_ai.response.time_to_first_chunk"}:
            if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                put(standard, key, float(value))
        elif key == "gen_ai.retrieval.top_k":
            put(standard, key, nonnegative_int(value))
        elif key == "gen_ai.tool.type":
            if value in {"extension", "function", "datastore"}:
                put(standard, key, value)
        elif present(value, allow_empty=key == "gen_ai.agent.description"):
            put(standard, key, str(value), allow_empty=key == "gen_ai.agent.description")

    put(standard, "gen_ai.provider.name", open_enum(provider, KNOWN_PROVIDERS))
    for target in TOKEN_FIELDS:
        put(standard, target, nonnegative_int(attrs.get(target)))
    for target, source_keys in aliases.items():
        value = first(attrs, *source_keys)
        if target in TOKEN_FIELDS:
            value = nonnegative_int(value)
        put(
            standard,
            target,
            str(value) if target == "gen_ai.agent.id" and value is not None else value,
        )
    if identity.kind == "llm":
        standard.setdefault("gen_ai.usage.input_tokens", 0)
        standard.setdefault("gen_ai.usage.output_tokens", 0)

    raw_reasons = attrs.get("gen_ai.response.finish_reasons")
    values = raw_reasons if isinstance(raw_reasons, list) else [raw_reasons]
    reasons = [FINISH_REASONS.get(str(value), str(value)) for value in values if present(value)]
    if reasons:
        standard["gen_ai.response.finish_reasons"] = reasons
    for source in (extra, content):
        for key, value in source.items():
            put(standard, key, value)

    if "gen_ai.response.finish_reasons" not in standard:
        output = standard.get("gen_ai.output.messages")
        message_reasons = (
            [
                message["finish_reason"]
                for message in output
                if isinstance(message, dict) and present(message.get("finish_reason"))
            ]
            if isinstance(output, list)
            else []
        )
        if message_reasons:
            standard["gen_ai.response.finish_reasons"] = message_reasons
    if not standard.get("gen_ai.operation.name"):
        return None
    if parse_failed:
        warnings.append(
            {
                "code": "content_parse_error",
                "message": "Content could not be fully parsed",
                "span_id": span["span_id"],
            }
        )
    resource = deepcopy(span["resource"])
    return {
        "trace_id": span["trace_id"],
        "span_id": span["span_id"],
        "parent_span_id": span["parent_span_id"],
        "span_name": span["span_name"],
        "start_time": span["start_time"],
        "end_time": span["end_time"],
        "elapsed_time": span["elapsed_time"],
        "status": deepcopy(span["status"]),
        "resource": resource if isinstance(resource, dict) else {},
        "attributes": standard,
        "_variant": identity.variant,
    }
