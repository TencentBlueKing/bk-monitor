"""产品路由和标准字段定义。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q

from constants.apm import LLMProduct

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet

# 能判定为 Agent 观测数据的 Span：各产品的埋点标记字段取并集，用于不区分层级的筛选与计数。
AGENT_CANDIDATE_FIELDS: tuple[str, ...] = (
    "attributes.gen_ai.span.kind",
    "attributes.gen_ai.operation.name",
    "attributes.agent.info.id",
    "attributes.agent.info.name",
    "attributes.langfuse.observation.type",
)
# Trace 检索要把谓词和用户关键字拼成一条 query_string，指标侧走 Q，两种形态都从同一份字段派生
AGENT_CANDIDATE_QUERY: str = " OR ".join(f"_exists_:{field}" for field in AGENT_CANDIDATE_FIELDS)
AGENT_CANDIDATE_Q: Q = Q(*(Q(**{f"{field}__exists": [""]}) for field in AGENT_CANDIDATE_FIELDS), _connector=Q.OR)


# gen_ai.operation.name -> Span 语义层级，未登记的取值（检索、任务等）不归类。
SPAN_TYPES: dict[str, str] = {
    "invoke_workflow": "AGENT",
    "create_agent": "AGENT",
    "invoke_agent": "AGENT",
    "plan": "AGENT",
    "execute_tool": "TOOL",
    "chat": "LLM",
    "generate_content": "LLM",
    "text_completion": "LLM",
    "fetch_response": "LLM",
    "embeddings": "LLM",
}


def resolve_product(entity_set: EntitySet, service_name: str) -> str:
    """取服务拓扑节点上登记的 LLM 产品，非 LLM 服务返回空串。"""
    if service_name not in entity_set.service_names:
        return ""
    system: dict[str, Any] = entity_set.get_system(service_name)
    return system.get("product") or "" if system.get("is_support_llm") else ""


def resolve_span_type(attributes: dict[str, Any]) -> str:
    """按标准化后的 operation.name 归类 Span，未登记的取值返回空串。"""
    # AgentLens 的 operation.name 上报为大写，统一转小写后再查表
    return SPAN_TYPES.get(str(attributes.get("gen_ai.operation.name", "")).strip().lower(), "")


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


def resolve_query_field(product: str, field: str) -> str:
    """命中映射表时按产品换算为存储中的原始字段，未命中（含非 LLM 服务）时原样透传。"""
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
    "gen_ai.usage.cache_write.input_tokens",
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
