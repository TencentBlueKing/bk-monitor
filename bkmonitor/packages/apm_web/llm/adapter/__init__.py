"""Agent 观测数据到标准 Span 的轻量路由入口。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from . import adapter_agentlens, adapter_bkaidev, adapter_default, adapter_galileo
from .fields import detect_product

ADAPTERS = {
    "agentlens": adapter_agentlens.convert,
    "galileo": adapter_galileo.convert,
    "bkaidev": adapter_bkaidev.convert,
    "default": adapter_default.convert,
}


def adapt_spans(
    raw_spans: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = list(raw_spans)
    raw.sort(key=lambda item: item["start_time"])
    product = detect_product(raw)
    convert = ADAPTERS[product]
    return convert(raw)


__all__ = ["adapt_spans"]
