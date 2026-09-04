"""Agent 观测数据到标准 Span 的轻量路由入口。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from constants.apm import LLMProduct

from . import adapter_agentlens, adapter_bkaidev, adapter_default, adapter_galileo
from .fields import detect_product

if TYPE_CHECKING:
    from apm_web.strategy.dispatch.entity import EntitySet

ADAPTERS = {
    LLMProduct.AGENTLENS.value: adapter_agentlens.convert,
    LLMProduct.AIDEV.value: adapter_bkaidev.convert,
    LLMProduct.GALILEO.value: adapter_galileo.convert,
    LLMProduct.LANGFUSE.value: adapter_default.convert,
    LLMProduct.DEFAULT.value: adapter_default.convert,
}


def adapt_spans(
    raw_spans: Iterable[dict[str, Any]],
    entity_set: EntitySet,
) -> list[dict[str, Any]]:
    raw = list(raw_spans)
    raw.sort(key=lambda item: item["start_time"])
    product = detect_product(entity_set, raw)
    convert = ADAPTERS[product]
    return convert(raw)


__all__ = ["adapt_spans"]
