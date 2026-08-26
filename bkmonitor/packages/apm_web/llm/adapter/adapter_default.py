"""标准 OTel GenAI Span 的保守 fallback。"""

from __future__ import annotations

from typing import Any

from .content import parse_standard_content
from .fields import normalize_operation, project_span


def convert_content(span: dict[str, Any]) -> dict[str, Any]:
    return parse_standard_content(span["attributes"]).build()


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        operation = normalize_operation(attrs.get("gen_ai.operation.name"))
        content = convert_content(span)
        converted = project_span(
            span,
            operation=operation,
            provider=attrs.get("gen_ai.provider.name"),
            aliases={},
            extra={},
            content=content,
        )
        if converted:
            spans.append(converted)
    return spans
