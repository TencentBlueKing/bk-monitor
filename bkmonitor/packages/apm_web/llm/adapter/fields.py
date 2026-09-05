"""产品路由和标准字段定义。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import LLMProduct, OtlpKey

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet


def detect_product(entity_set: EntitySet, spans: list[dict[str, Any]]) -> str:
    """根据 Span 所属服务的拓扑节点信息，为整条 Trace 选择转换器。"""
    service_names: set[str] = {
        service_name
        for span in spans
        if (service_name := span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME))
    }
    systems: list[dict[str, Any]] = [
        entity_set.get_system(service_name) for service_name in service_names.intersection(entity_set.service_names)
    ]
    products: set[str] = {
        product for system in systems if system.get("is_support_llm") and (product := system.get("product"))
    }
    for product in (LLMProduct.GALILEO, LLMProduct.AIDEV, LLMProduct.AGENTLENS, LLMProduct.LANGFUSE):
        if product.value in products:
            return product.value
    return LLMProduct.DEFAULT.value


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
