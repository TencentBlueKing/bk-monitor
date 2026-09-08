"""LLM 标准会话字段与各产品原始字段。"""

from constants.apm import LLMProduct, OtlpKey

STANDARD_CONVERSATION_FIELD = OtlpKey.get_attributes_key("gen_ai.conversation.id")

PRODUCT_CONVERSATION_FIELDS = {
    LLMProduct.DEFAULT.value: STANDARD_CONVERSATION_FIELD,
    LLMProduct.AGENTLENS.value: OtlpKey.get_attributes_key("gen_ai.session.id"),
    LLMProduct.AIDEV.value: OtlpKey.get_attributes_key("agent.session.session_code"),
    LLMProduct.GALILEO.value: OtlpKey.get_attributes_key("gen_ai.session_id"),
    LLMProduct.LANGFUSE.value: STANDARD_CONVERSATION_FIELD,
}

CONVERSATION_QUERY_FIELDS = tuple(dict.fromkeys(PRODUCT_CONVERSATION_FIELDS.values()))
