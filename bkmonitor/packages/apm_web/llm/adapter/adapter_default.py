"""标准 OTel GenAI Span 的保守 fallback。"""

from __future__ import annotations

from typing import Any

from .fields import STANDARD_FIELDS
from .utils import present, standard_content


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {key: value for key, value in attrs.items() if key in STANDARD_FIELDS and present(value)}
        attributes.update(standard_content(attrs))
        if not attributes:
            continue
        spans.append(
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span["parent_span_id"],
                "span_name": span["span_name"],
                "start_time": span["start_time"],
                "end_time": span["end_time"],
                "elapsed_time": span["elapsed_time"],
                "status": span["status"],
                "resource": span["resource"],
                "attributes": attributes,
            }
        )
    return spans
