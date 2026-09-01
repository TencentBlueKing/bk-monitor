"""Transport-independent parsers used by collector probe evidence."""

from __future__ import annotations

import json
import os
import re
from typing import Any


def fallback_matching_inputs(text: str, expected_data_id: int) -> list[dict[str, Any]]:
    """Recover bounded local inputs when a rendered config is not valid YAML."""

    lines = text.splitlines()
    markers = []
    pattern = re.compile(r"^(\s*)(?:-\s*)?(?:dataid|data_id|dataId)\s*:\s*['\"]?(\d+)")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            markers.append((index, len(match.group(1)), _integer(match.group(2))))

    results = []
    for marker_index, (start, indent, data_id) in enumerate(markers):
        if data_id != expected_data_id:
            continue
        end = len(lines)
        for next_start, next_indent, _next_data_id in markers[marker_index + 1 :]:
            if next_indent <= indent:
                end = next_start
                break
        block = "\n".join(lines[start:end])
        paths = []
        in_paths = False
        paths_indent = 0
        for line in lines[start + 1 : end]:
            if re.match(r"^\s*paths\s*:\s*$", line):
                in_paths = True
                paths_indent = len(line) - len(line.lstrip(" "))
                continue
            if in_paths:
                path_indent = len(line) - len(line.lstrip(" "))
                path_match = re.match(r"^\s*-\s*['\"]?(.+?)['\"]?\s*$", line)
                if path_match and path_indent > paths_indent:
                    paths.append(path_match.group(1))
                    continue
                if line.strip() and path_indent <= paths_indent:
                    in_paths = False

        def config_value(name: str) -> str | None:
            match = re.search(rf"(?im)^\s*{re.escape(name)}\s*:\s*['\"]?([^'\"\s#]+)", block)
            return match.group(1) if match else None

        results.append(
            {
                "data_id": expected_data_id,
                "input_type": "unknown",
                "paths": paths,
                "scan_frequency": config_value("scan_frequency"),
                "max_backoff": config_value("max_backoff"),
                "multiline_timeout": config_value("multiline.timeout"),
            }
        )
    return results


def parse_registrar_strings(text: str) -> list[dict[str, Any]]:
    states = []
    for value in _json_values(text):
        _collect_registrar_states(value, states)
    deduplicated = {}
    for item in states:
        key = (
            item.get("source"),
            item.get("inode"),
            item.get("device"),
            item.get("offset"),
            str(item.get("timestamp")),
        )
        deduplicated[key] = item
    return list(deduplicated.values())


def state_for_file(states: list[dict[str, Any]], file_info: dict[str, Any]) -> dict[str, Any]:
    source = file_info.get("path")
    normalized = file_info.get("normalized_path")
    path_states = [
        item
        for item in states
        if item.get("source") in (source, normalized) or os.path.realpath(item.get("source") or "") == normalized
    ]
    current = [
        item
        for item in path_states
        if item.get("inode") == file_info.get("inode") and item.get("device") == file_info.get("device")
    ]

    def sort_key(item: dict[str, Any]) -> tuple[str, int]:
        return str(item.get("timestamp") or ""), item.get("offset") if item.get("offset") is not None else -1

    return {
        "current": sorted(current, key=sort_key)[-1] if current else None,
        "historical": sorted(path_states, key=sort_key)[-5:] if path_states and not current else [],
    }


def classify_registrar_progress(
    first_file: dict[str, Any],
    second_file: dict[str, Any],
    first_match: dict[str, Any],
    second_match: dict[str, Any],
    *,
    insufficient: bool = False,
) -> dict[str, Any]:
    if first_file.get("inode") != second_file.get("inode") or first_file.get("device") != second_file.get("device"):
        observed = "file_rotated_during_sampling"
    elif not second_match.get("current"):
        observed = "historical_state_only" if second_match.get("historical") else "registrar_state_not_found"
    else:
        before_state = first_match.get("current") or second_match.get("current")
        after_state = second_match.get("current")
        before_offset = before_state.get("offset") if before_state else None
        after_offset = after_state.get("offset")
        if before_offset is None or after_offset is None:
            observed = "progress_indeterminate"
        else:
            file_growth = second_file.get("size_bytes", 0) - first_file.get("size_bytes", 0)
            progress = after_offset - before_offset
            before_lag = max(0, first_file.get("size_bytes", 0) - before_offset)
            after_lag = max(0, second_file.get("size_bytes", 0) - after_offset)
            if progress > 0:
                observed = "progress_advancing_but_lagging" if after_lag > before_lag else "progress_advancing"
            elif file_growth > 0:
                observed = "source_growing_but_progress_static"
            elif after_offset >= second_file.get("size_bytes", 0):
                observed = "caught_up_or_source_idle"
            elif after_lag > 0:
                observed = "progress_static_with_backlog"
            else:
                observed = "progress_indeterminate"
    return {
        "status": "insufficient_observation_window" if insufficient else observed,
        "observed_status": observed,
        "observation_window_insufficient": insufficient,
        "first_state": first_match,
        "second_state": second_match,
    }


def _json_values(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values = []
    for line in text.splitlines():
        for index, character in enumerate(line):
            if character not in "[{":
                continue
            try:
                value, _end = decoder.raw_decode(line[index:])
            except ValueError:
                continue
            values.append(value)
            break
    return values


def _case_get(value: dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): child for key, child in value.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _identity_from_state(value: dict[str, Any]) -> tuple[int | None, int | None]:
    inode = _case_get(value, "inode", "ino")
    device = _case_get(value, "device", "dev")
    nested = _case_get(value, "FileStateOS", "file_state_os", "meta")
    if isinstance(nested, dict):
        inode = inode if inode is not None else _case_get(nested, "inode", "ino")
        device = device if device is not None else _case_get(nested, "device", "dev")
    return _integer(inode), _integer(device)


def _collect_registrar_states(value: Any, results: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        source = _case_get(value, "source")
        offset = _case_get(value, "offset")
        if source is not None and offset is not None:
            inode, device = _identity_from_state(value)
            results.append(
                {
                    "source": str(source),
                    "offset": _integer(offset),
                    "timestamp": _case_get(value, "timestamp", "updated_at"),
                    "ttl": _case_get(value, "ttl"),
                    "type": _case_get(value, "type"),
                    "meta": _case_get(value, "meta"),
                    "inode": inode,
                    "device": device,
                }
            )
        for child in value.values():
            _collect_registrar_states(child, results)
    elif isinstance(value, list):
        for child in value:
            _collect_registrar_states(child, results)


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
