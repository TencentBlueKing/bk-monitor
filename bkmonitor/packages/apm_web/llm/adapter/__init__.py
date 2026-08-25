"""Agent 观测数据到标准 Span 的轻量路由入口。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from . import adapter_agentlens, adapter_bkaidev, adapter_default, adapter_galileo
from .fields import Product, detect_product
from .trace import _LLM_OPERATIONS, SCHEMA_VERSION, build_trace
from .utils import normalize_span

ADAPTERS = {
    "agentlens": adapter_agentlens.convert,
    "galileo": adapter_galileo.convert,
    "bkaidev": adapter_bkaidev.convert,
    "default": adapter_default.convert,
}


def adapt_trace(
    raw_spans: Iterable[dict[str, Any]],
    *,
    trace_id: str,
    app_name: str = "",
    sdk_type: Product | None = None,
    include_content: bool = False,
    include_raw: bool = False,
    partial: bool = False,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    raw = [normalize_span(item, warnings) for item in raw_spans if isinstance(item, dict)]
    raw.sort(key=lambda item: (item["start_time"], item["span_id"]))
    product = sdk_type or detect_product(raw, app_name)
    convert = ADAPTERS[product]
    spans, redirects = convert(raw, include_content=include_content, warnings=warnings)
    return build_trace(
        raw,
        spans,
        redirects,
        warnings,
        trace_id=trace_id,
        include_content=include_content,
        include_raw=include_raw,
        partial=partial,
        product=product,
    )


__all__ = ["SCHEMA_VERSION", "_LLM_OPERATIONS", "adapt_trace"]
