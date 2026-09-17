"""产品路由和标准字段定义。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q

from constants.apm import LLMProduct

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet

# 能判定为 Agent 观测数据的 Span：各产品的埋点标记字段取并集，用于不区分产品的筛选。
AGENT_CANDIDATE_FIELDS: tuple[str, ...] = (
    "attributes.gen_ai.span.kind",
    "attributes.gen_ai.operation.name",
    "attributes.agent.info.id",
    "attributes.agent.info.name",
    "attributes.langfuse.observation.type",
)
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


# 产品存储里的操作名 -> 标准 gen_ai.operation.name，未登记的取值只做小写化。
# 与 adapter 的归一口径对齐：聚合侧拿不到 span_name / 消息结构，只能映射字段取值本身。
OPERATION_NAME_ALIASES: dict[str, dict[str, str]] = {
    LLMProduct.AIDEV.value: {
        "chat": "chat",
        "completion": "text_completion",
        "embedding": "embeddings",
        "rerank": "retrieval",
    },
    LLMProduct.LANGFUSE.value: {
        "agent": "invoke_agent",
        "chain": "invoke_workflow",
        "embedding": "embeddings",
        "generation": "chat",
        "retriever": "retrieval",
        "tool": "execute_tool",
    },
    LLMProduct.AGENTLENS.value: {
        "agent": "invoke_agent",
        "llm": "chat",
        "tool": "execute_tool",
    },
}


def resolve_operation_name(product: str, value: Any) -> str:
    """把各产品存储中的操作名换算成标准名，空值保持为空串。"""
    raw = str(value).strip() if value not in (None, "") else ""
    if not raw:
        return ""
    lowered = raw.lower()
    return OPERATION_NAME_ALIASES.get(product, {}).get(lowered, lowered)
