"""产品路由和标准字段定义。"""

from __future__ import annotations

from typing import Any, Literal

Product = Literal["bkaidev", "galileo", "agentlens", "default"]

BKAIDEV_SPAN_NAMES = {
    "agent.execution",
    "chain.workflow",
    "langgraph.workflow",
    "chat_model.generate",
    "chatmodel.chat",
    "tool.execution",
}
BKAIDEV_TASK_NAMES = {"model.task", "model_node.task", "tools.task", "chain.task"}


def detect_product(spans: list[dict[str, Any]]) -> Product:
    """只根据 Span 自身信息为整条 Trace 选择转换器。"""
    if any(str(span["resource"].get("telemetry.sdk.name", "")).lower() == "galileo" for span in spans):
        return "galileo"
    if any(
        span["span_name"].lower() in BKAIDEV_SPAN_NAMES
        or span["span_name"].lower() in BKAIDEV_TASK_NAMES
        or any(key.startswith(("agent.info.", "agent.session.")) for key in span["attributes"])
        for span in spans
    ):
        return "bkaidev"
    if any(
        str(span["attributes"].get("gen_ai.span.kind", "")).lower() in {"agent", "llm", "tool"}
        or any(key.startswith(("gen_ai.prompts.", "gen_ai.completion.")) for key in span["attributes"])
        or span["span_name"].lower().endswith((".agent", ".llm", ".tool"))
        for span in spans
    ):
        return "agentlens"
    return "default"


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
