"""Agent 观测数据到标准 Span 的轻量路由入口。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from . import adapter_agentlens, adapter_bkaidev, adapter_default, adapter_galileo
from .fields import detect_product
from .trace import finalize_spans
from .utils import normalize_span

ADAPTERS = {
    "agentlens": adapter_agentlens.convert,
    "galileo": adapter_galileo.convert,
    "bkaidev": adapter_bkaidev.convert,
    "default": adapter_default.convert,
}


def adapt_spans(
    raw_spans: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = [normalize_span(item) for item in raw_spans if isinstance(item, dict)]
    raw.sort(key=lambda item: (item["start_time"], item["span_id"]))
    product = detect_product(raw)
    convert = ADAPTERS[product]
    spans = convert(raw)
    return finalize_spans(raw, spans)


__all__ = ["adapt_spans"]
