"""Agent 观测数据到标准 Span 的轻量路由入口。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import LLMProduct, OtlpKey

from . import adapter_agentlens, adapter_bkaidev, adapter_default, adapter_galileo, adapter_langfuse
from .fields import resolve_product, resolve_span_type

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet

# 未登记的产品（langfuse、非 LLM 服务）按标准 OTel 字段保守转换。
ADAPTERS = {
    LLMProduct.AGENTLENS.value: adapter_agentlens.convert,
    LLMProduct.AIDEV.value: adapter_bkaidev.convert,
    LLMProduct.GALILEO.value: adapter_galileo.convert,
    LLMProduct.LANGFUSE.value: adapter_langfuse.convert,
    LLMProduct.DEFAULT.value: adapter_default.convert,
}


def adapt_spans(
    raw_spans: Iterable[dict[str, Any]],
    entity_set: EntitySet,
) -> list[dict[str, Any]]:
    """按 EntitySet 的服务检测结果路由转换器。"""
    spans_by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_span in raw_spans:
        service_name: str = raw_span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME, "")
        product = resolve_product(entity_set, service_name)
        spans_by_product[product].append(raw_span)

    # 先尽力转换，再按标准操作类型判断是否为 LLM Span，避免依赖各产品的原始标记字段。
    spans: list[dict[str, Any]] = [
        span
        for product, product_spans in spans_by_product.items()
        for span in ADAPTERS.get(product, adapter_default.convert)(product_spans)
        if isinstance(operation := span["attributes"].get("gen_ai.operation.name"), str) and operation.strip()
    ]
    for span in spans:
        # 识别不出语义层级的 Span 不带该字段，调用方据此决定是否展示 LLM 观测
        if span_type := resolve_span_type(span["attributes"]):
            span["span_type"] = span_type
    spans.sort(key=lambda span: span["start_time"])
    return spans


__all__ = ["adapt_spans"]
