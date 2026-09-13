"""产品路由和标准字段定义。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import LLMProduct, OtlpKey

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet

# 一次查询涉及多个产品时的取用顺序。
PRODUCT_PRIORITY = (LLMProduct.GALILEO, LLMProduct.AIDEV, LLMProduct.AGENTLENS, LLMProduct.LANGFUSE)

# 能判定为 Agent 观测数据的 Span：各产品的埋点标记字段取并集，用于不区分层级的筛选与计数。
AGENT_CANDIDATE_QUERY = (
    "_exists_:attributes.gen_ai.span.kind "
    "OR _exists_:attributes.gen_ai.operation.name "
    "OR _exists_:attributes.agent.info.id "
    "OR _exists_:attributes.agent.info.name "
    "OR _exists_:attributes.langfuse.observation.type"
)


def resolve_product(entity_set: EntitySet, service_names: Iterable[str]) -> str:
    """根据服务的拓扑节点信息选择产品，均非 LLM 服务时落到 default。"""
    systems: list[dict[str, Any]] = [
        entity_set.get_system(service_name)
        for service_name in set(service_names).intersection(entity_set.service_names)
    ]
    products: set[str] = {
        product for system in systems if system.get("is_support_llm") and (product := system.get("product"))
    }
    for product in PRODUCT_PRIORITY:
        if product.value in products:
            return product.value
    return LLMProduct.DEFAULT.value


def detect_product(entity_set: EntitySet, spans: list[dict[str, Any]]) -> str:
    """根据 Span 所属服务的拓扑节点信息，为整条 Trace 选择转换器。"""
    return resolve_product(
        entity_set,
        {
            service_name
            for span in spans
            if (service_name := span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME))
        },
    )


# 分组字段映射：标准字段 -> 产品 -> 存储中的原始字段，只登记与标准名不一致的产品。
QUERY_FIELD_MAPPING: dict[str, dict[str, str]] = {
    "attributes.gen_ai.conversation.id": {
        LLMProduct.AIDEV.value: "attributes.agent.session.session_code",
        LLMProduct.AGENTLENS.value: "attributes.gen_ai.session.id",
        LLMProduct.GALILEO.value: "attributes.gen_ai.session_id",
        LLMProduct.LANGFUSE.value: "attributes.session.id",
    },
    "attributes.gen_ai.operation.name": {
        # 该产品的 operation.name 取值为大写，语义层级实际由 span.kind 表达
        LLMProduct.AGENTLENS.value: "attributes.gen_ai.span.kind",
        LLMProduct.LANGFUSE.value: "attributes.langfuse.observation.type",
        LLMProduct.AIDEV.value: "attributes.llm.request.type",
    },
    "attributes.gen_ai.response.model": {
        # 该产品未上报 response.model，但 request.model 在样本与生产环境都是全量填充的
        LLMProduct.GALILEO.value: "attributes.gen_ai.request.model",
        LLMProduct.LANGFUSE.value: "attributes.langfuse.observation.model.name",
    },
}


def resolve_query_field(product: str | None, field: str) -> str:
    """命中映射表时按产品换算为存储中的原始字段，未命中时原样透传。"""
    if product is None:
        return field
    return QUERY_FIELD_MAPPING.get(field, {}).get(product, field)


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
