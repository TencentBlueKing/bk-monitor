"""Shared bounded-runtime helpers for host and Kubernetes inspections."""

from __future__ import annotations

from typing import Any


def normalize_runtime_log_options(value: dict[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    case_sensitive = bool(value.get("case_sensitive", False))
    keywords = []
    seen = set()
    for item in value.get("keywords") or []:
        keyword = str(item)
        normalized = keyword if case_sensitive else keyword.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)
    return {
        "keywords": sorted(keywords),
        "match": value.get("match", "any"),
        "case_sensitive": case_sensitive,
        "context_lines": int(value.get("context_lines", 0)),
    }


def filter_runtime_logs(log_evidence: dict[str, Any], options: dict[str, Any] | None) -> dict[str, Any]:
    """Apply literal matching in the Resource Worker and merge contexts."""

    options = options or {}
    keywords = [str(item) for item in options.get("keywords") or []]
    if not keywords:
        return log_evidence
    match_mode = options.get("match", "any")
    case_sensitive = bool(options.get("case_sensitive", False))
    context_lines = int(options.get("context_lines", 0))
    needles = keywords if case_sensitive else [item.casefold() for item in keywords]
    scanned_lines = 0
    matched_lines = 0
    ranges = []

    for file_evidence in log_evidence.get("files", []) or []:
        content = str(file_evidence.pop("content", ""))
        lines = content.splitlines()
        matching_indexes = []
        for index, line in enumerate(lines):
            candidate = line if case_sensitive else line.casefold()
            matches = [needle in candidate for needle in needles]
            if (match_mode == "all" and all(matches)) or (match_mode == "any" and any(matches)):
                matching_indexes.append(index)

        intervals = _merge_context_intervals(matching_indexes, context_lines, len(lines))
        selected = []
        matching_set = set(matching_indexes)
        for start, end in intervals:
            for index in range(start, end + 1):
                selected.append({"line_number": index + 1, "content": lines[index], "matched": index in matching_set})
        file_evidence["filter_result"] = {
            "scanned_lines": len(lines),
            "matched_lines": len(matching_indexes),
            "returned_lines": len(selected),
            "lines": selected,
            "scanned_range": {
                "start_offset_bytes": file_evidence.get("start_offset_bytes"),
                "end_offset_bytes": file_evidence.get("end_offset_bytes"),
                "relative_start_line": 1 if lines else None,
                "relative_end_line": len(lines) if lines else None,
            },
        }
        scanned_lines += len(lines)
        matched_lines += len(matching_indexes)
        ranges.append({"path": file_evidence.get("path"), **file_evidence["filter_result"]["scanned_range"]})

    log_evidence["filter"] = {
        "keywords": keywords,
        "match": match_mode,
        "case_sensitive": case_sensitive,
        "context_lines": context_lines,
        "scanned_lines": scanned_lines,
        "matched_lines": matched_lines,
        "truncated": bool(log_evidence.get("truncated")),
        "scanned_ranges": ranges,
        "scope_statement": (
            "no literal match was found in the bounded scanned ranges; this does not cover all historical logs"
            if matched_lines == 0
            else "literal matches are limited to the bounded scanned ranges"
        ),
    }
    return log_evidence


def _merge_context_intervals(indexes: list[int], context: int, line_count: int) -> list[tuple[int, int]]:
    intervals = []
    for index in indexes:
        start = max(0, index - context)
        end = min(max(0, line_count - 1), index + context)
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], end))
        else:
            intervals.append((start, end))
    return intervals


def apply_runtime_log_filter(
    probes: dict[str, Any], options: dict[str, Any] | None, *, probe_names: tuple[str, ...] = ("collector_logs",)
) -> None:
    for probe_name in probe_names:
        probe = probes.get(probe_name)
        if not isinstance(probe, dict) or not isinstance(probe.get("evidence"), dict):
            continue
        filter_runtime_logs(probe["evidence"], options)
        if (options or {}).get("keywords"):
            matched = probe["evidence"].get("filter", {}).get("matched_lines", 0)
            probe["code"] = "collector_log_literal_matches" if matched else "collector_log_literal_no_match"
            probe["summary"] = (
                "literal matches were returned with merged context"
                if matched
                else "no literal match was found in the bounded scanned ranges"
            )
