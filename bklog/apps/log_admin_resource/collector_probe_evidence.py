"""Convert shared fixed-probe output into bounded collector evidence."""

from __future__ import annotations

import fnmatch
import hashlib
import os
from typing import Any

import yaml

from apps.log_admin_resource.collector_probe_parsers import (
    classify_registrar_progress,
    fallback_matching_inputs,
    parse_registrar_strings_with_stats,
    state_for_file,
)


MAX_SOURCE_SAMPLE_BYTES = 64 * 1024
MAX_SOURCE_SAMPLE_LINES = 50


def build_probe_evidence(
    parsed: dict[str, Any],
    *,
    bk_data_id: int,
    source: str | None,
    include_source_sample: bool,
    config_map_main: str | None,
    expected_specs: list[dict[str, Any]] | None = None,
    sidecar_required: bool = True,
) -> dict[str, dict[str, Any]]:
    values = parsed.get("values") or {}
    streams = parsed.get("streams") or {}
    configs, matching_inputs = _rendered_configs(values, streams, bk_data_id)
    render_comparison = _rendered_config_comparison(expected_specs or [], matching_inputs)
    first_sources = _source_rows(values, "first")
    second_sources = _source_rows(values, "second")
    allowed_patterns = sorted(
        {
            str(path)
            for input_config in matching_inputs
            for path in input_config.get("paths") or []
            if isinstance(path, str) and path.startswith("/")
        }
    )
    selected_first, selected_second, source_error = _select_sources(
        first_sources, second_sources, allowed_patterns, source
    )

    main_config = streams.get("main_config") or {}
    main_content = str(main_config.get("content") or "")
    mounted_main_sha256 = values.get("main_config.sha256") or _sha256_text(main_content)
    config_map_main_sha256 = _sha256_text(config_map_main) if config_map_main is not None else None
    main_matches = config_map_main is not None and mounted_main_sha256 == config_map_main_sha256
    config_status = "success" if configs and matching_inputs and render_comparison["equivalent"] else "warning"
    if matching_inputs and render_comparison["equivalent"]:
        config_code = "child_config_rendered"
    elif matching_inputs:
        config_code = "child_config_rendered_drift"
    elif values.get("child_config_scan_truncated") == "true":
        config_code = "child_config_scan_truncated"
    elif (_integer(values.get("child_config_match_count")) or 0) > 0:
        config_code = "matched_child_config_content_unavailable"
    else:
        config_code = "data_id_child_config_not_rendered"
    config_warnings = []
    if values.get("main_config.unavailable") == "base64_missing":
        config_warnings.append(
            {
                "code": "probe_dependency_missing",
                "message": "base64 is unavailable in the collector runtime; exact config content was not returned",
                "retryable": False,
            }
        )
    if len([item for item in configs if item["matching_input_count"]]) > 1:
        config_warnings.append(
            {
                "code": "multiple_matching_child_configs",
                "message": "multiple rendered child configs contain the selected DataID",
                "retryable": False,
            }
        )
    if (_integer(values.get("main_config_candidate_count")) or 0) > 1:
        config_warnings.append(
            {
                "code": "multiple_main_config_candidates",
                "message": "multiple bounded fallback main-config candidates were found",
                "retryable": False,
            }
        )
    if values.get("child_config_scan_truncated") == "true":
        config_warnings.append(
            {
                "code": "child_config_scan_truncated",
                "message": "the bounded child-config scan reached its limit before all candidates were inspected",
                "retryable": False,
            }
        )
    if values.get("child_config_match_limit_exceeded") == "true":
        config_warnings.append(
            {
                "code": "child_config_match_limit_exceeded",
                "message": "more matching child configs exist than can be returned in one probe",
                "retryable": False,
            }
        )
    if values.get("output_budget_exhausted") == "true":
        config_warnings.append(
            {
                "code": "probe_output_budget_exhausted",
                "message": "lower-priority evidence was omitted to stay below the transport output limit",
                "retryable": False,
            }
        )
    config_probe = {
        "status": config_status,
        "code": config_code,
        "summary": "rendered collector configuration was inspected",
        "evidence": {
            "main_config": {
                "path": values.get("main_config_path"),
                "discovery_source": values.get("main_config_source"),
                "candidate_count": _integer(values.get("main_config_candidate_count")),
                "mtime_epoch": _integer(values.get("main_config.mtime_epoch")),
                "sha256": mounted_main_sha256,
                "total_size_bytes": main_config.get("total_size_bytes"),
                "truncated": main_config.get("truncated", False),
                "safe_projection": _safe_main_config(main_content),
                "mounted_config_map_exact_match": main_matches if config_map_main is not None else None,
                "mounted_config_map_sha256": config_map_main_sha256,
            },
            "child_configs": configs,
            "child_config_scan": {
                "target_data_id": _integer(values.get("target_data_id")),
                "hint_count": _integer(values.get("child_config_hint_count")),
                "hint_path_count": _integer(values.get("child_config_hint_path_count")),
                "scanned_count": _integer(values.get("child_config_scanned_count")),
                "scan_limit": _integer(values.get("child_config_scan_limit")),
                "scan_truncated": values.get("child_config_scan_truncated") == "true",
                "match_count": _integer(values.get("child_config_match_count")),
                "match_limit_exceeded": values.get("child_config_match_limit_exceeded") == "true",
            },
            "matching_input_count": len(matching_inputs),
            "matching_patterns": allowed_patterns,
            "render_comparison": render_comparison,
        },
        "warnings": config_warnings,
    }

    collector_process_probe = _process_probe(values, streams, "collector")
    sidecar_process_probe = (
        _process_probe(values, streams, "sidecar")
        if sidecar_required
        else {
            "status": "skipped",
            "code": "sidecar_not_applicable",
            "summary": "sidecar process evidence is not applicable to physical-host collection",
            "evidence": None,
            "warnings": [],
        }
    )
    source_probe = _source_probe(
        values=values,
        streams=streams,
        first_rows=selected_first,
        second_rows=selected_second,
        allowed_patterns=allowed_patterns,
        source=source,
        include_sample=include_source_sample,
        error=source_error,
    )
    registrar_probe = _registrar_probe(values, streams, selected_first, selected_second)
    progress_probe = _progress_probe(values, streams, selected_first, selected_second)
    return {
        "main_config_mounted": config_probe,
        "collector_process": collector_process_probe,
        "sidecar_process": sidecar_process_probe,
        "source_path": source_probe,
        "registrar": registrar_probe,
        "progress": progress_probe,
    }


def _rendered_configs(
    values: dict[str, str], streams: dict[str, dict[str, Any]], bk_data_id: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    configs = []
    matching_inputs = []
    for name, stream in sorted(streams.items()):
        if not name.startswith("child_config."):
            continue
        content = str(stream.get("content") or "")
        inputs = _yaml_local_inputs(content, bk_data_id)
        matches = [
            item
            for item in inputs
            if str(item.get("dataid") if "dataid" in item else item.get("data_id")) == str(bk_data_id)
        ]
        matching_inputs.extend(matches)
        configs.append(
            {
                "path": stream.get("path"),
                "mtime_epoch": _integer(values.get(f"{name}.mtime_epoch")),
                "sha256": _sha256_text(content),
                "total_size_bytes": stream.get("total_size_bytes"),
                "truncated": stream.get("truncated", False),
                "matching_input_count": len(matches),
                "matching_inputs": [_safe_input(item) for item in matches],
            }
        )
    return configs, matching_inputs


def _rendered_config_comparison(
    expected_specs: list[dict[str, Any]], matching_inputs: list[dict[str, Any]]
) -> dict[str, Any]:
    if not expected_specs:
        return {"equivalent": True, "compared_fields": [], "differences": []}
    expected_paths = sorted(
        {str(path) for spec in expected_specs for path in (spec.get("path") or []) if isinstance(path, str)}
    )
    actual_paths = sorted(
        {
            str(path)
            for input_config in matching_inputs
            for path in (input_config.get("paths") or [])
            if isinstance(path, str)
        }
    )
    differences = []
    if expected_paths != actual_paths:
        differences.append({"field": "path", "expected": expected_paths, "actual": actual_paths})
    for field in ("encoding", "exclude_files", "multiline"):
        expected_values = [spec.get(field) for spec in expected_specs if spec.get(field) is not None]
        actual_values = [item.get(field) for item in matching_inputs if item.get(field) is not None]
        if expected_values and expected_values != actual_values:
            differences.append({"field": field, "expected": expected_values, "actual": actual_values})
    return {
        "equivalent": not differences,
        "compared_fields": ["path", "encoding", "exclude_files", "multiline"],
        "differences": differences,
    }


def _yaml_local_inputs(content: str, bk_data_id: int) -> list[dict[str, Any]]:
    try:
        documents = list(yaml.safe_load_all(content))
    except yaml.YAMLError:
        documents = []
    results = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        local = document.get("local") or []
        if isinstance(local, dict):
            local = [local]
        results.extend(item for item in local if isinstance(item, dict))
    if results:
        return results
    return fallback_matching_inputs(content, bk_data_id)


def _safe_input(value: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "dataid",
        "data_id",
        "input",
        "paths",
        "exclude_files",
        "tail_files",
        "encoding",
        "scan_frequency",
        "max_backoff",
        "close_inactive",
        "ignore_older",
        "clean_removed",
        "clean_inactive",
        "multiline",
        "docker-json",
        "is_container_std",
    )
    return {key: value.get(key) for key in keys if key in value}


def _safe_main_config(content: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        value = {}
    if not isinstance(value, dict):
        return {}
    result = {key: value.get(key) for key in ("path.data", "path.logs", "path.pid") if key in value}
    registry = value.get("bkunifylogbeat.registry")
    if isinstance(registry, dict):
        result["bkunifylogbeat.registry"] = {
            key: registry.get(key) for key in ("flush", "gc_frequency") if key in registry
        }
    if "bkunifylogbeat.multi_config" in value:
        result["bkunifylogbeat.multi_config"] = value["bkunifylogbeat.multi_config"]
    return result


def _source_rows(values: dict[str, str], phase: str) -> list[dict[str, Any]]:
    rows = []
    count = _integer(values.get(f"{phase}.source_count")) or 0
    for index in range(min(50, count)):
        prefix = f"{phase}.source.{index}."
        path = values.get(prefix + "path")
        if not path:
            continue
        rows.append(
            {
                "index": index,
                "pattern": values.get(prefix + "pattern"),
                "path": path,
                "normalized_path": values.get(prefix + "resolved_path") or os.path.normpath(path),
                "symlink": values.get(prefix + "symlink") == "true",
                "device": _integer(values.get(prefix + "device")),
                "inode": _integer(values.get(prefix + "inode")),
                "size_bytes": _integer(values.get(prefix + "size_bytes")),
                "mtime_epoch": _integer(values.get(prefix + "mtime_epoch")),
            }
        )
    return rows


def _select_sources(
    first_rows: list[dict[str, Any]],
    second_rows: list[dict[str, Any]],
    allowed_patterns: list[str],
    source: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    def allowed(row: dict[str, Any]) -> bool:
        return any(fnmatch.fnmatchcase(row["path"], pattern) for pattern in allowed_patterns)

    first = [row for row in first_rows if allowed(row)]
    second = [row for row in second_rows if allowed(row)]
    if source:
        normalized = os.path.normpath(source)
        if normalized != source or not source.startswith("/"):
            return [], [], "source_not_in_rendered_config"
        if not any(fnmatch.fnmatchcase(source, pattern) for pattern in allowed_patterns):
            return [], [], "source_not_in_rendered_config"
        first = [row for row in first if row["path"] == source]
        second = [row for row in second if row["path"] == source]
    return first, second, None


def build_collector_file_log_probe(parsed: dict[str, Any], *, fallback: bool = True) -> dict[str, Any]:
    """Return the fixed collector file-log fallback captured by the repository probe."""

    values = parsed.get("values") or {}
    streams = parsed.get("streams") or {}
    count = min(2, _integer(values.get("collector_file_log_count")) or 0)
    files = []
    for index in range(count):
        stream = streams.get(f"collector_file_log.{index}") or {}
        if not stream:
            continue
        files.append(
            {
                "path": stream.get("path"),
                "content": str(stream.get("content") or ""),
                "returned_size_bytes": stream.get("returned_size_bytes"),
                "total_size_bytes": stream.get("total_size_bytes"),
                "truncated": stream.get("truncated", False),
            }
        )
    returned_size = sum(len(item["content"].encode("utf-8", errors="replace")) for item in files)
    return {
        "status": "warning" if files and fallback else "success" if files else "failed",
        "code": "collector_file_logs_fallback"
        if files and fallback
        else "collector_file_logs_inspected"
        if files
        else "collector_logs_unavailable",
        "summary": (
            "fixed collector file logs were used because current pods/log was unavailable"
            if files and fallback
            else "bounded collector file logs were inspected"
            if files
            else "collector file logs were unavailable"
        ),
        "evidence": {
            "files": files,
            "returned_size_bytes": returned_size,
            "public_return_limit_bytes": 1024 * 1024,
            "truncated": any(item.get("truncated") for item in files),
            "fallback": fallback,
        },
        "warnings": [],
    }


def _process_probe(values: dict[str, str], streams: dict[str, dict[str, Any]], role: str) -> dict[str, Any]:
    first = _process_row(values, "first", role)
    second = _process_row(values, "second", role)
    if not first or not second:
        return {
            "status": "failed",
            "code": f"{role}_process_unavailable",
            "summary": f"{role} process evidence is unavailable",
            "evidence": {"first": first, "second": second},
            "warnings": [],
        }
    same_process = first["pid"] == second["pid"] and first["start_ticks"] == second["start_ticks"]
    delta = None
    if same_process:
        observation_seconds = _number(values.get("observation_seconds"))
        cpu_ticks_delta = _delta(second.get("cpu_ticks"), first.get("cpu_ticks"))
        read_bytes_delta = _delta(second.get("read_bytes"), first.get("read_bytes"))
        write_bytes_delta = _delta(second.get("write_bytes"), first.get("write_bytes"))
        clock_ticks = second.get("clock_ticks_per_second") or first.get("clock_ticks_per_second")
        cpu_count = second.get("cpu_count") or first.get("cpu_count")
        delta = {
            "cpu_ticks": cpu_ticks_delta,
            "rss_bytes": _delta(second.get("rss_bytes"), first.get("rss_bytes")),
            "pss_bytes": _delta(second.get("pss_bytes"), first.get("pss_bytes")),
            "threads": _delta(second.get("threads"), first.get("threads")),
            "fd_count": _delta(second.get("fd_count"), first.get("fd_count")),
            "read_bytes": read_bytes_delta,
            "write_bytes": write_bytes_delta,
            "read_bytes_per_second": _rate(read_bytes_delta, observation_seconds),
            "write_bytes_per_second": _rate(write_bytes_delta, observation_seconds),
            "cpu_percent_of_pod_capacity": _cpu_percent(cpu_ticks_delta, clock_ticks, observation_seconds, cpu_count),
        }
    return {
        "status": "success" if same_process else "warning",
        "code": f"{role}_process_sampled" if same_process else f"{role}_restarted_during_sampling",
        "summary": f"{role} process and bounded resource deltas were sampled",
        "evidence": {
            "first": first,
            "second": second,
            "same_process": same_process,
            "delta": delta,
            "observation_seconds": _number(values.get("observation_seconds")),
            "cgroup": {
                phase: {
                    "membership": str((streams.get(f"{phase}.{role}.cgroup") or {}).get("content") or "") or None,
                    "metrics": {
                        metric: values.get(f"{phase}.{role}.cgroup.{metric}")
                        for metric in (
                            "memory.current",
                            "memory.max",
                            "pids.current",
                            "pids.max",
                            "cpu.stat.usage_usec",
                            "cpu.stat.user_usec",
                            "cpu.stat.system_usec",
                            "cpu.stat.nr_periods",
                            "cpu.stat.nr_throttled",
                            "cpu.stat.throttled_usec",
                        )
                        if values.get(f"{phase}.{role}.cgroup.{metric}") is not None
                    },
                }
                for phase in ("first", "second")
            },
        },
        "warnings": [],
    }


def _process_row(values: dict[str, str], phase: str, role: str) -> dict[str, Any] | None:
    prefix = f"{phase}.{role}"
    pid = _integer(values.get(f"{prefix}.process_pid"))
    if not pid:
        return None
    page_size = _integer(values.get("page_size")) or 4096
    rss_pages = _integer(values.get(f"{prefix}.rss_pages"))
    pss_kib = _integer(values.get(f"{prefix}.pss_kib"))
    return {
        "pid": pid,
        "binary_path": values.get(f"{prefix}.binary_path"),
        "start_ticks": _integer(values.get(f"{prefix}.start_ticks")),
        "cpu_ticks": _integer(values.get(f"{prefix}.cpu_ticks")),
        "rss_bytes": rss_pages * page_size if rss_pages is not None else None,
        "pss_bytes": pss_kib * 1024 if pss_kib is not None else None,
        "threads": _integer(values.get(f"{prefix}.threads")),
        "fd_count": _integer(values.get(f"{prefix}.fd_count")),
        "fd_soft_limit": _integer(values.get(f"{prefix}.fd_soft_limit")),
        "fd_hard_limit": _integer(values.get(f"{prefix}.fd_hard_limit")),
        "fd_classification": {
            "inspected": _integer(values.get(f"{prefix}.fd_inspected")),
            "socket": _integer(values.get(f"{prefix}.fd_socket")),
            "pipe": _integer(values.get(f"{prefix}.fd_pipe")),
            "anon_inode": _integer(values.get(f"{prefix}.fd_anon")),
            "other": _integer(values.get(f"{prefix}.fd_other")),
            "deleted": _integer(values.get(f"{prefix}.fd_deleted")),
            "truncated": values.get(f"{prefix}.fd_classification_truncated") == "true",
        },
        "read_bytes": _integer(values.get(f"{prefix}.read_bytes")),
        "write_bytes": _integer(values.get(f"{prefix}.write_bytes")),
        "clock_ticks_per_second": _integer(values.get("clock_ticks_per_second")),
        "cpu_count": _integer(values.get("cpu_count")),
    }


def _source_probe(
    *,
    values: dict[str, str],
    streams: dict[str, dict[str, Any]],
    first_rows: list[dict[str, Any]],
    second_rows: list[dict[str, Any]],
    allowed_patterns: list[str],
    source: str | None,
    include_sample: bool,
    error: str | None,
) -> dict[str, Any]:
    if error:
        return {
            "status": "failed",
            "code": error,
            "summary": "requested source is outside the selected DataID rendered configuration",
            "evidence": {"requested_source": source, "allowed_patterns": allowed_patterns},
            "warnings": [],
        }
    if values.get("source_narrowing_required") == "true" and (not source or not first_rows and not second_rows):
        return {
            "status": "warning",
            "code": "source_narrowing_required",
            "summary": "the bounded remote source set cannot prove the requested source state",
            "evidence": {"requested_source": source, "allowed_patterns": allowed_patterns, "files": []},
            "warnings": [],
        }
    second_by_path = {row["path"]: row for row in second_rows}
    files = []
    returned_lines = 0
    returned_bytes = 0
    sample_unavailable_reasons = []
    for first in first_rows:
        row = {"first": first, "second": second_by_path.get(first["path"])}
        if include_sample and source and first["path"] == source:
            sample_name = f"second.source.{(row['second'] or first)['index']}.sample"
            sample_stream = streams.get(sample_name) or {}
            unavailable_reason = values.get(f"{sample_name}.unavailable")
            sample = str(sample_stream.get("content") or "")
            sample_bytes = sample.encode("utf-8", errors="replace")[-MAX_SOURCE_SAMPLE_BYTES:]
            lines = sample_bytes.decode("utf-8", errors="replace").splitlines()[-MAX_SOURCE_SAMPLE_LINES:]
            returned_sample_bytes = len("\n".join(lines).encode("utf-8", errors="replace"))
            row["sample"] = {
                "lines": lines,
                "returned_lines": len(lines),
                "returned_bytes": returned_sample_bytes,
                "unavailable_reason": unavailable_reason,
            }
            if unavailable_reason:
                sample_unavailable_reasons.append(unavailable_reason)
            returned_lines += len(lines)
            returned_bytes += returned_sample_bytes
        files.append(row)
    return {
        "status": "success" if files else "warning",
        "code": "source_paths_inspected" if files else "configured_source_not_present",
        "summary": "configured source paths were bounded and sampled by file identity",
        "evidence": {
            "requested_source": source,
            "allowed_patterns": allowed_patterns,
            "files": files,
            "source_sample_limit": {
                "maximum_lines": MAX_SOURCE_SAMPLE_LINES,
                "maximum_bytes": MAX_SOURCE_SAMPLE_BYTES,
                "returned_lines": returned_lines,
                "returned_bytes": returned_bytes,
            },
        },
        "warnings": (
            [
                {
                    "code": "source_sample_unavailable",
                    "message": "the requested source sample could not be returned within the fixed probe bounds",
                    "retryable": False,
                    "reasons": sorted(set(sample_unavailable_reasons)),
                }
            ]
            if sample_unavailable_reasons
            else []
        ),
    }


def _registrar_sampling(
    values: dict[str, str],
    stream: dict[str, Any],
    stats: dict[str, int],
    phase: str,
) -> dict[str, Any]:
    """Report how much of the registrar the bounded sample actually accounts for."""
    prefix = f"{phase}.registrar_strings."
    truncated = bool(stream.get("truncated"))
    unparsed_line_count = stats.get("unparsed_line_count") or 0
    partial_state_count = stats.get("partial_state_count") or 0
    returned_line_count = stats.get("line_count") or 0
    filtered_line_count = _integer(values.get(prefix + "filtered_line_count"))
    incomplete_reasons = []
    if truncated:
        incomplete_reasons.append("stream_truncated")
    if unparsed_line_count:
        incomplete_reasons.append("unparsed_lines")
    if partial_state_count:
        incomplete_reasons.append("partial_states")
    if filtered_line_count is not None and filtered_line_count > returned_line_count:
        incomplete_reasons.append("lines_missing_from_sample")
    return {
        "filtered": values.get(prefix + "filtered") == "true",
        "filter_key_count": _integer(values.get(prefix + "filter_key_count")),
        "total_line_count": _integer(values.get(prefix + "total_line_count")),
        "filtered_line_count": filtered_line_count,
        "returned_line_count": returned_line_count,
        "returned_size_bytes": stream.get("returned_size_bytes"),
        "truncated": truncated,
        "unparsed_line_count": unparsed_line_count,
        "partial_state_count": partial_state_count,
        "incomplete_reasons": incomplete_reasons,
    }


def _registrar_probe(
    values: dict[str, str],
    streams: dict[str, dict[str, Any]],
    first_rows: list[dict[str, Any]],
    second_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    unavailable = values.get("second.registrar_unavailable") or values.get("first.registrar_unavailable")
    if unavailable:
        code = "probe_dependency_missing" if unavailable == "strings_missing" else "registrar_unavailable"
        return {
            "status": "failed",
            "code": code,
            "summary": "registrar strings evidence is unavailable",
            "evidence": {"reason": unavailable, "registrar_path": values.get("registrar_path")},
            "warnings": [],
        }
    first_stream = streams.get("first.registrar_strings") or {}
    second_stream = streams.get("second.registrar_strings") or {}
    first_states, first_stats = parse_registrar_strings_with_stats(str(first_stream.get("content") or ""))
    second_states, second_stats = parse_registrar_strings_with_stats(str(second_stream.get("content") or ""))
    first_matches = {row["path"]: state_for_file(first_states, row) for row in first_rows}
    second_matches = {row["path"]: state_for_file(second_states, row) for row in second_rows}
    first_sampling = _registrar_sampling(values, first_stream, first_stats, "first")
    second_sampling = _registrar_sampling(values, second_stream, second_stats, "second")
    incomplete_reasons = sorted(set(first_sampling["incomplete_reasons"]) | set(second_sampling["incomplete_reasons"]))
    return {
        "status": "warning" if incomplete_reasons else "success",
        "code": "registrar_strings_incomplete" if incomplete_reasons else "registrar_strings_inspected",
        "summary": (
            "bounded strings evidence is incomplete, so an absent state does not prove the file is untracked"
            if incomplete_reasons
            else "live BoltDB was not opened; bounded strings evidence was matched by source, inode and device"
        ),
        "evidence": {
            "path": values.get("registrar_path"),
            "first_state_count": len(first_states),
            "second_state_count": len(second_states),
            "first_matches": first_matches,
            "second_matches": second_matches,
            "first_sampling": first_sampling,
            "second_sampling": second_sampling,
        },
        "warnings": (
            [
                {
                    "code": "registrar_evidence_incomplete",
                    "message": "registrar evidence is bounded; an absent state cannot be read as an untracked file",
                    "retryable": False,
                    "reasons": incomplete_reasons,
                }
            ]
            if incomplete_reasons
            else []
        ),
    }


def _progress_probe(
    values: dict[str, str],
    streams: dict[str, dict[str, Any]],
    first_rows: list[dict[str, Any]],
    second_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first_stream = streams.get("first.registrar_strings") or {}
    second_stream = streams.get("second.registrar_strings") or {}
    first_states, first_stats = parse_registrar_strings_with_stats(str(first_stream.get("content") or ""))
    second_states, second_stats = parse_registrar_strings_with_stats(str(second_stream.get("content") or ""))
    evidence_incomplete = bool(
        _registrar_sampling(values, first_stream, first_stats, "first")["incomplete_reasons"]
        or _registrar_sampling(values, second_stream, second_stats, "second")["incomplete_reasons"]
    )
    second_by_path = {row["path"]: row for row in second_rows}
    results = []
    insufficient = values.get("insufficient_observation_window") == "true"
    for first in first_rows:
        second = second_by_path.get(first["path"])
        if not second:
            continue
        results.append(
            {
                "path": first["path"],
                **classify_registrar_progress(
                    first,
                    second,
                    state_for_file(first_states, first),
                    state_for_file(second_states, second),
                    insufficient=insufficient,
                    evidence_incomplete=evidence_incomplete,
                ),
            }
        )
    return {
        "status": "success" if results else "warning",
        "code": "registrar_progress_sampled" if results else "registrar_progress_unavailable",
        "summary": "progress reflects collector read/ACK evidence, not GSE delivery, storage or query success",
        "evidence": {
            "items": results,
            "observation_required_seconds": _number(values.get("observation_required_seconds")),
            "observation_seconds": _number(values.get("observation_seconds")),
            "registrar_evidence_incomplete": evidence_incomplete,
            "scope_statement": "Registrar progress proves only local collector read/ACK state",
        },
        "warnings": [],
    }


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(right: int | None, left: int | None) -> int | None:
    if right is None or left is None:
        return None
    return right - left


def _rate(delta: int | None, seconds: float | None) -> float | None:
    if delta is None or not seconds or seconds <= 0:
        return None
    return round(delta / seconds, 3)


def _cpu_percent(
    delta_ticks: int | None, clock_ticks: int | None, seconds: float | None, cpu_count: int | None
) -> float | None:
    if delta_ticks is None or not clock_ticks or not seconds or not cpu_count:
        return None
    return round(delta_ticks / clock_ticks / seconds / cpu_count * 100, 3)
