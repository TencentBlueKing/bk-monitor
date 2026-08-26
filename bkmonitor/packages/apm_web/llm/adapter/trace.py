"""修复转换后的 Span 关系并稳定排序。"""

from __future__ import annotations

from typing import Any


def _reparent(
    spans: list[dict[str, Any]],
    raw_by_id: dict[str, dict[str, Any]],
) -> None:
    kept = {span["span_id"] for span in spans}
    for span in spans:
        parent = span["parent_span_id"]
        visited: set[str] = set()
        unresolved = False
        while parent and parent not in kept and parent not in visited:
            visited.add(parent)
            raw_parent = raw_by_id.get(parent)
            if raw_parent is None:
                unresolved = True
                break
            parent = raw_parent.get("parent_span_id")
        span["parent_span_id"] = parent if parent != span["span_id"] and (parent in kept or unresolved) else None


def finalize_spans(
    raw: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    _reparent(spans, {span["span_id"]: span for span in raw})
    spans.sort(key=lambda item: (item["start_time"], item["span_id"]))
    return spans
