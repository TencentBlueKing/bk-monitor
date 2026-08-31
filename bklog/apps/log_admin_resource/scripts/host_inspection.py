#!/usr/bin/env python
# ruff: noqa: UP032 - fixed remote script must remain Python 2.7 compatible
"""Fixed, read-only Linux collector inspection script.

The caller supplies one URL-safe base64 JSON token.  No command, script,
account or arbitrary path is accepted.  The optional source path is only used
after it has been proven to match the target DataID's rendered sub-config.

Keep this file Python 2.7/3 compatible because NodeMan-managed hosts may use
either runtime for JOB Python scripts.
"""

import base64
import fnmatch
import glob
import hashlib
import json
import os
import re
import select
import stat
import subprocess
import sys
import time
from datetime import datetime

try:
    STRING_TYPES = (basestring,)  # type: ignore[name-defined]
except NameError:
    STRING_TYPES = (str, bytes)


PROTOCOL = "bklog.collector.host_inspection.v1"
MAX_CONFIG_BYTES = 1024 * 1024
MAX_CHILD_CONFIGS = 200
MAX_SOURCE_FILES = 50
MAX_SOURCE_SAMPLE_BYTES = 64 * 1024
MAX_SOURCE_SAMPLE_LINES = 50
MAX_ERROR_LOG_BYTES = 10 * 1024 * 1024
MAX_REGISTRAR_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_FD_DETAILS = 50
COMMAND_TIMEOUT_SECONDS = 15

DEFAULT_DURATIONS = {
    "registry_flush": 1.0,
    "scan_frequency": 10.0,
    "max_backoff": 10.0,
    "multiline_timeout": 5.0,
}


def utcnow():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_warning(code, message):
    return {"code": code, "message": message, "retryable": False}


def make_probe(status, code, summary, evidence=None, warnings=None, started_at=None, started_monotonic=None):
    finished_at = utcnow()
    duration_ms = 0
    if started_monotonic is not None:
        duration_ms = round(max(0.0, time.time() - started_monotonic) * 1000, 2)
    return {
        "status": status,
        "code": code,
        "summary": summary,
        "evidence": evidence,
        "warnings": warnings or [],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
    }


def read_bounded(path, maximum):
    with open(path, "rb") as handle:
        value = handle.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError("file exceeds bounded inspection limit")
    return value


def decode_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def scalar(value):
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in ("'", '"') and value[-1:] == value[0:1]:
        return value[1:-1]
    lower = value.lower()
    if lower in ("true", "false"):
        return lower == "true"
    if re.match(r"^-?\d+$", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def parse_simple_yaml(text):
    """Parse only the flat/list constructs needed for bkunifylogbeat configs."""

    result = {}
    section = None
    section_indent = -1
    current_item = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = scalar(value)
                section = None
                current_item = None
            else:
                section = key
                section_indent = indent
                result.setdefault(section, [])
                current_item = None
            continue
        if section and indent > section_indent:
            if line.startswith("-"):
                current_item = {}
                if not isinstance(result.get(section), list):
                    result[section] = []
                result[section].append(current_item)
                line = line[1:].strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = scalar(value.strip())
                if current_item is not None:
                    current_item[key] = value
                elif isinstance(result.get(section), list):
                    result[section] = {key: value}
    return result


def parse_yaml(text):
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(text)
        if isinstance(parsed, dict):
            return parsed, "pyyaml"
    except Exception:
        pass
    return parse_simple_yaml(text), "bounded_fallback"


def get_config_value(config, dotted_key, default=None):
    if dotted_key in config:
        return config[dotted_key]
    value = config
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def normalize_multi_config(value):
    if isinstance(value, dict):
        value = [value]
    result = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        path = decode_text(item.get("path") or "").strip()
        pattern = decode_text(item.get("file_pattern") or item.get("pattern") or "").strip()
        if path and pattern:
            result.append({"path": path, "file_pattern": pattern})
    return result


def parse_duration(value, default):
    if value is None or value == "":
        return float(default)
    if isinstance(value, (int, float)):  # noqa: UP038 - fixed remote script must remain Python 2.7 compatible
        return max(0.0, float(value))
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*$", str(value), re.I)
    if not match:
        return float(default)
    number = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    return number * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]


def calculate_observation_window(durations):
    theoretical = (
        max(
            2 * durations["registry_flush"],
            durations["scan_frequency"],
            durations["max_backoff"],
            durations["multiline_timeout"],
        )
        + 2
    )
    return {
        "durations_seconds": durations,
        "theoretical_seconds": theoretical,
        "actual_seconds": min(30.0, max(5.0, theoretical)),
        "insufficient": theoretical > 30.0,
    }


def _data_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dictionary_data_id(value):
    for key in ("dataid", "data_id", "dataId", "bk_data_id"):
        if key in value:
            return _data_id(value.get(key))
    return None


def _input_paths(value):
    paths = value.get("paths") if isinstance(value, dict) else None
    if isinstance(paths, STRING_TYPES):
        return [paths] if decode_text(paths).strip() else []
    return [decode_text(item) for item in paths or [] if isinstance(item, STRING_TYPES) and decode_text(item).strip()]


def find_matching_inputs(value, expected_data_id, input_type=None, results=None):
    results = results if results is not None else []
    if isinstance(value, dict):
        current_data_id = _dictionary_data_id(value)
        if current_data_id == expected_data_id:
            results.append(
                {
                    "data_id": current_data_id,
                    "input_type": input_type or decode_text(value.get("type") or "unknown"),
                    "paths": _input_paths(value),
                    "scan_frequency": value.get("scan_frequency"),
                    "max_backoff": value.get("max_backoff"),
                    "multiline_timeout": get_config_value(value, "multiline.timeout"),
                }
            )
        for key, child in value.items():
            child_type = input_type
            if key in ("local", "log", "stdin", "udp", "tcp", "syslog"):
                child_type = key
            find_matching_inputs(child, expected_data_id, child_type, results)
    elif isinstance(value, list):
        for child in value:
            find_matching_inputs(child, expected_data_id, input_type, results)
    return results


def fallback_matching_inputs(text, expected_data_id):
    lines = text.splitlines()
    markers = []
    pattern = re.compile(r"^(\s*)(?:-\s*)?(?:dataid|data_id|dataId)\s*:\s*['\"]?(\d+)")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            markers.append((index, len(match.group(1)), _data_id(match.group(2))))

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

        def config_value(name):
            match = re.search(r"(?im)^\s*{}\s*:\s*['\"]?([^'\"\s#]+)".format(re.escape(name)), block)
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


def inspect_configs(setup_path, expected_data_id):
    main_path = os.path.join(setup_path, "plugins", "etc", "bkunifylogbeat.conf")
    raw = read_bounded(main_path, MAX_CONFIG_BYTES)
    text = decode_text(raw)
    main_config, parser = parse_yaml(text)
    multi_config = normalize_multi_config(get_config_value(main_config, "bkunifylogbeat.multi_config", []))
    warnings = []
    if not multi_config:
        warnings.append(make_warning("multi_config_missing", "main config has no bkunifylogbeat.multi_config entries"))

    durations = dict(DEFAULT_DURATIONS)
    explicit_durations = {"scan_frequency": [], "max_backoff": [], "multiline_timeout": []}
    durations["registry_flush"] = parse_duration(
        get_config_value(main_config, "bkunifylogbeat.registry.flush"), durations["registry_flush"]
    )
    matched = []
    candidate_count = 0
    inspected_config_count = 0
    for item in multi_config:
        candidates = sorted(glob.glob(os.path.join(item["path"], item["file_pattern"])))
        candidate_count += len(candidates)
        remaining_config_slots = max(0, MAX_CHILD_CONFIGS - inspected_config_count)
        selected_candidates = candidates[:remaining_config_slots]
        inspected_config_count += len(selected_candidates)
        for child_path in selected_candidates:
            try:
                child_raw = read_bounded(child_path, MAX_CONFIG_BYTES)
                child_text = decode_text(child_raw)
                child_config, child_parser = parse_yaml(child_text)
                inputs = find_matching_inputs(child_config, expected_data_id)
                fallback_inputs = fallback_matching_inputs(child_text, expected_data_id)
                if not inputs:
                    inputs = fallback_inputs
                elif fallback_inputs and not any(item.get("paths") for item in inputs):
                    for input_config in inputs:
                        input_config["paths"] = list(fallback_inputs[0].get("paths") or [])
                        for key in ("scan_frequency", "max_backoff", "multiline_timeout"):
                            if input_config.get(key) is None:
                                input_config[key] = fallback_inputs[0].get(key)
                if not inputs:
                    continue
                child_stat = os.stat(child_path)
                for input_config in inputs:
                    for key in ("scan_frequency", "max_backoff", "multiline_timeout"):
                        if input_config.get(key) is not None:
                            explicit_durations[key].append(parse_duration(input_config.get(key), durations[key]))
                matched.append(
                    {
                        "path": child_path,
                        "size_bytes": child_stat.st_size,
                        "mtime": child_stat.st_mtime,
                        "sha256": sha256_bytes(child_raw),
                        "parser": child_parser,
                        "data_id": expected_data_id,
                        "inputs": inputs,
                    }
                )
            except Exception as error:
                warnings.append(make_warning("child_config_unreadable", "{}: {}".format(child_path, error)))
        if len(candidates) > len(selected_candidates):
            warnings.append(make_warning("child_config_limit_reached", "child config enumeration was bounded"))

    for key, values in explicit_durations.items():
        if values:
            durations[key] = max(values)

    if len(matched) > 1:
        warnings.append(make_warning("multiple_matching_configs", "multiple sub-configs contain the target DataID"))
    main_stat = os.stat(main_path)
    public = {
        "main_config": {
            "path": main_path,
            "size_bytes": main_stat.st_size,
            "mtime": main_stat.st_mtime,
            "sha256": sha256_bytes(raw),
            "parser": parser,
            "path_data": get_config_value(main_config, "path.data"),
            "path_logs": get_config_value(main_config, "path.logs"),
            "path_pid": get_config_value(main_config, "path.pid"),
            "multi_config": multi_config,
            "registry_flush_seconds": durations["registry_flush"],
        },
        "candidate_config_count": candidate_count,
        "inspected_config_count": inspected_config_count,
        "matching_configs": matched,
        "matching_config_count": len(matched),
        "warnings": warnings,
    }
    internal = {
        "path_data": get_config_value(main_config, "path.data"),
        "path_logs": get_config_value(main_config, "path.logs"),
        "durations": durations,
        "matching_configs": matched,
    }
    return public, internal


def _read_text(path, maximum=1024 * 1024):
    return decode_text(read_bounded(path, maximum))


def _parse_key_value_lines(text):
    result = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def _kilobytes(value):
    match = re.match(r"^(\d+)\s*kB$", str(value), re.I)
    return int(match.group(1)) * 1024 if match else None


def _boot_epoch():
    for line in _read_text("/proc/stat", 1024 * 1024).splitlines():
        if line.startswith("btime "):
            return float(line.split()[1])
    return time.time() - float(_read_text("/proc/uptime", 128).split()[0])


def _cpu_count():
    if hasattr(os, "cpu_count"):
        return os.cpu_count()
    try:
        import multiprocessing

        return multiprocessing.cpu_count()
    except Exception:
        return 1


def normalize_proc_executable(value):
    suffix = " (deleted)"
    return (value[: -len(suffix)], True) if value.endswith(suffix) else (value, False)


def _fd_evidence(pid):
    fd_path = "/proc/{}/fd".format(pid)
    warnings = []
    try:
        names = os.listdir(fd_path)
    except (IOError, OSError) as error:  # noqa: UP024 - Python 2 remote runtime
        return {
            "count": None,
            "soft_limit": None,
            "hard_limit": None,
            "usage_ratio": None,
            "groups": {},
            "details": [],
            "details_truncated": False,
            "enumeration_races": 0,
            "warnings": [make_warning("fd_directory_unavailable", str(error))],
        }
    groups = {"regular_file": 0, "socket": 0, "pipe": 0, "anon_inode": 0, "other": 0, "deleted": 0}
    details = []
    detail_count = 0
    races = 0
    for name in names:
        try:
            target = os.readlink(os.path.join(fd_path, name))
        except OSError:
            races += 1
            continue
        if target.endswith(" (deleted)"):
            groups["deleted"] += 1
        if target.startswith("socket:"):
            kind = "socket"
        elif target.startswith("pipe:"):
            kind = "pipe"
        elif target.startswith("anon_inode:"):
            kind = "anon_inode"
        elif target.startswith("/"):
            kind = "regular_file"
        else:
            kind = "other"
        groups[kind] += 1
        if kind == "regular_file" or target.endswith(" (deleted)"):
            detail_count += 1
            if len(details) < MAX_FD_DETAILS:
                details.append({"fd": int(name), "kind": kind, "target": target})

    soft = None
    hard = None
    try:
        for line in _read_text("/proc/{}/limits".format(pid), 1024 * 1024).splitlines():
            if line.startswith("Max open files"):
                columns = line.split()
                if len(columns) >= 5:
                    soft = None if columns[3] == "unlimited" else int(columns[3])
                    hard = None if columns[4] == "unlimited" else int(columns[4])
                break
    except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
        warnings.append(make_warning("fd_limits_unavailable", str(error)))
    count = len(names)
    return {
        "count": count,
        "soft_limit": soft,
        "hard_limit": hard,
        "usage_ratio": round(float(count) / soft, 6) if soft else None,
        "groups": groups,
        "details": details,
        "details_truncated": detail_count > MAX_FD_DETAILS,
        "enumeration_races": races,
        "warnings": warnings,
    }


def inspect_process(pid, expected_binary):
    proc = "/proc/{}".format(pid)
    exe = os.readlink(os.path.join(proc, "exe"))
    executable_path, binary_deleted = normalize_proc_executable(exe)
    if os.path.realpath(executable_path) != os.path.realpath(expected_binary):
        return None
    raw_stat = _read_text(os.path.join(proc, "stat"), 1024 * 1024)
    end_comm = raw_stat.rfind(")")
    fields = raw_stat[end_comm + 2 :].split()
    clock_ticks = float(os.sysconf("SC_CLK_TCK"))
    start_ticks = int(fields[19])
    warnings = []
    if binary_deleted:
        warnings.append(make_warning("process_binary_deleted", "the running executable has been replaced or deleted"))
    try:
        started_epoch = _boot_epoch() + start_ticks / clock_ticks
        started_at = datetime.utcfromtimestamp(started_epoch).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        runtime_seconds = max(0.0, time.time() - started_epoch)
    except Exception as error:
        warnings.append(make_warning("process_start_time_unavailable", str(error)))
        started_at = None
        runtime_seconds = None
    try:
        status = _parse_key_value_lines(_read_text(os.path.join(proc, "status"), 1024 * 1024))
    except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
        warnings.append(make_warning("process_status_unavailable", str(error)))
        status = {}
    try:
        io = _parse_key_value_lines(_read_text(os.path.join(proc, "io"), 1024 * 1024))
    except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
        warnings.append(make_warning("process_io_unavailable", str(error)))
        io = {}
    smaps = {}
    try:
        smaps = _parse_key_value_lines(_read_text(os.path.join(proc, "smaps_rollup"), 2 * 1024 * 1024))
    except Exception as error:
        warnings.append(make_warning("smaps_rollup_unavailable", str(error)))
    try:
        cmdline = _read_text(os.path.join(proc, "cmdline"), 64 * 1024).replace("\x00", " ").strip()
    except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
        warnings.append(make_warning("process_cmdline_unavailable", str(error)))
        cmdline = None
    fd_evidence = _fd_evidence(pid)
    warnings.extend(fd_evidence.pop("warnings", []))
    return {
        "pid": int(pid),
        "start_ticks": start_ticks,
        "started_at": started_at,
        "runtime_seconds": runtime_seconds,
        "binary_path": exe,
        "binary_deleted": binary_deleted,
        "cmdline": cmdline,
        "cpu_ticks": int(fields[11]) + int(fields[12]),
        "clock_ticks_per_second": clock_ticks,
        "cpu_count": _cpu_count(),
        "memory": {
            "vm_rss_bytes": _kilobytes(status.get("VmRSS")),
            "vm_size_bytes": _kilobytes(status.get("VmSize")),
            "vm_swap_bytes": _kilobytes(status.get("VmSwap")),
            "threads": int(status.get("Threads", fields[17])),
            "smaps_rollup": {
                key: _kilobytes(value)
                for key, value in smaps.items()
                if key in ("Rss", "Pss", "Private_Clean", "Private_Dirty", "Shared_Clean", "Shared_Dirty")
            },
        },
        "file_descriptors": fd_evidence,
        "io": {key: int(value) for key, value in io.items() if str(value).isdigit()},
        "warnings": warnings,
    }


def process_snapshot(expected_binary):
    processes = []
    warnings = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            value = inspect_process(int(name), expected_binary)
            if value:
                processes.append(value)
        except (IOError, OSError, ValueError, IndexError) as error:  # noqa: UP024 - Python 2 remote runtime
            if os.path.exists("/proc/{}".format(name)):
                warnings.append(make_warning("proc_field_unavailable", "pid {}: {}".format(name, error)))
    if len(processes) > 1:
        warnings.append(make_warning("multiple_collector_processes", "multiple processes match the exact binary path"))
    return {
        "binary_path": expected_binary,
        "processes": processes,
        "process_count": len(processes),
        "warnings": warnings,
    }


def process_delta(first, second, elapsed):
    first_map = {(item["pid"], item["start_ticks"]): item for item in first.get("processes", [])}
    second_map = {(item["pid"], item["start_ticks"]): item for item in second.get("processes", [])}
    deltas = []
    restarted = bool(first.get("processes") and second.get("processes") and not set(first_map).intersection(second_map))
    availability_changed = bool(first.get("processes")) != bool(second.get("processes"))
    for identity in sorted(set(first_map).intersection(second_map)):
        before = first_map[identity]
        after = second_map[identity]
        cpu_seconds = float(after["cpu_ticks"] - before["cpu_ticks"]) / after["clock_ticks_per_second"]
        single_core = 100.0 * cpu_seconds / elapsed if elapsed else None
        cpu_count = after.get("cpu_count") or 1
        io_delta = {}
        for key in set(before.get("io", {})).intersection(after.get("io", {})):
            difference = after["io"][key] - before["io"][key]
            io_delta[key] = {"delta": difference, "per_second": difference / elapsed if elapsed else None}
        before_rss = before.get("memory", {}).get("vm_rss_bytes")
        after_rss = after.get("memory", {}).get("vm_rss_bytes")
        before_fd = before.get("file_descriptors", {}).get("count")
        after_fd = after.get("file_descriptors", {}).get("count")
        deltas.append(
            {
                "pid": after["pid"],
                "start_ticks": after["start_ticks"],
                "cpu_time_delta_seconds": cpu_seconds,
                "cpu_single_core_percent": single_core,
                "cpu_machine_percent": single_core / cpu_count if single_core is not None else None,
                "rss_delta_bytes": after_rss - before_rss if before_rss is not None and after_rss is not None else None,
                "fd_delta": after_fd - before_fd if before_fd is not None and after_fd is not None else None,
                "io": io_delta,
            }
        )
    return {
        "elapsed_seconds": elapsed,
        "process_restarted_during_sampling": restarted,
        "process_availability_changed_during_sampling": availability_changed,
        "deltas": [] if restarted else deltas,
    }


def configured_patterns(matching_configs):
    patterns = []
    for config in matching_configs:
        for input_config in config.get("inputs", []):
            for pattern in input_config.get("paths", []):
                if pattern:
                    patterns.append(os.path.abspath(decode_text(pattern)))
    return sorted(set(patterns))


def source_is_allowed(source, patterns):
    absolute = os.path.abspath(source)
    for pattern in patterns:
        matches = glob.glob(pattern)
        if any(os.path.abspath(item) == absolute for item in matches):
            return True
        if not os.path.exists(absolute) and fnmatch.fnmatchcase(absolute, pattern):
            return True
    return False


def _source_stat(path):
    is_symlink = os.path.islink(path)
    value = {
        "path": path,
        "normalized_path": os.path.realpath(path),
        "exists": os.path.exists(path),
        "lexists": os.path.lexists(path),
        "is_symlink": is_symlink,
        "symlink_target": os.readlink(path) if is_symlink else None,
    }
    if not value["exists"]:
        return value
    file_stat = os.stat(path)
    value.update(
        {
            "readable": os.access(path, os.R_OK),
            "size_bytes": file_stat.st_size,
            "mtime": file_stat.st_mtime,
            "inode": file_stat.st_ino,
            "device": file_stat.st_dev,
            "mode": stat.filemode(file_stat.st_mode),
        }
    )
    return value


def tail_sample(path, maximum_bytes=MAX_SOURCE_SAMPLE_BYTES, maximum_lines=MAX_SOURCE_SAMPLE_LINES):
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - maximum_bytes), os.SEEK_SET)
        value = handle.read(maximum_bytes)
    decoded_lines = decode_text(value).splitlines()
    lines = decoded_lines[-maximum_lines:]
    returned = "\n".join(lines)
    returned_bytes = returned.encode("utf-8")
    if len(returned_bytes) > maximum_bytes:
        returned = returned_bytes[-maximum_bytes:].decode("utf-8", "ignore")
        lines = returned.splitlines()[-maximum_lines:]
        returned = "\n".join(lines)
    return {
        "content": returned,
        "line_count": len(lines),
        "returned_bytes": len(returned.encode("utf-8")),
        "truncated": size > len(value) or len(decoded_lines) > maximum_lines,
        "source_size_bytes": size,
    }


def inspect_sources(patterns, explicit_source, include_sample):
    if explicit_source:
        if not source_is_allowed(explicit_source, patterns):
            raise ValueError("source_path_outside_target_config")
        paths = [os.path.abspath(explicit_source)]
        total_match_count = 1
    else:
        paths = sorted(set(path for pattern in patterns for path in glob.glob(pattern)))
        total_match_count = len(paths)
    if total_match_count > MAX_SOURCE_FILES:
        stats = []
        for path in paths:
            try:
                stats.append(os.stat(path))
            except OSError:
                pass
        return {
            "status": "source_narrowing_required",
            "patterns": patterns,
            "match_count": total_match_count,
            "returned_count": 0,
            "total_size_bytes": sum(item.st_size for item in stats),
            "latest_mtime": max([item.st_mtime for item in stats] or [None]),
            "files": [],
        }
    files = []
    sample_bytes_remaining = MAX_SOURCE_SAMPLE_BYTES
    sample_lines_remaining = MAX_SOURCE_SAMPLE_LINES
    for path in paths:
        try:
            item = _source_stat(path)
        except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
            item = {
                "path": path,
                "normalized_path": os.path.realpath(path),
                "exists": os.path.exists(path),
                "readable": False,
                "inspection_warning": make_warning("source_metadata_unavailable", str(error)),
            }
        if include_sample and item.get("exists") and item.get("readable"):
            if sample_bytes_remaining <= 0 or sample_lines_remaining <= 0:
                item["sample_warning"] = make_warning(
                    "source_sample_limit_reached", "the task-level source sample limit was reached"
                )
            else:
                try:
                    item["sample"] = tail_sample(path, sample_bytes_remaining, sample_lines_remaining)
                    sample_bytes_remaining -= item["sample"]["returned_bytes"]
                    sample_lines_remaining -= item["sample"]["line_count"]
                except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
                    item["sample_warning"] = make_warning("source_sample_unavailable", str(error))
        files.append(item)
    return {
        "status": "inspected",
        "patterns": patterns,
        "match_count": total_match_count,
        "returned_count": len(files),
        "source_sample_limit": {
            "maximum_bytes": MAX_SOURCE_SAMPLE_BYTES,
            "maximum_lines": MAX_SOURCE_SAMPLE_LINES,
            "returned_bytes": MAX_SOURCE_SAMPLE_BYTES - sample_bytes_remaining,
            "returned_lines": MAX_SOURCE_SAMPLE_LINES - sample_lines_remaining,
        }
        if include_sample
        else None,
        "files": files,
    }


def run_strings(path, timeout_seconds=COMMAND_TIMEOUT_SECONDS, maximum=MAX_REGISTRAR_OUTPUT_BYTES):
    process = subprocess.Popen(["strings", "-n", "4", "--", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = bytearray()
    deadline = time.time() + timeout_seconds
    fd = process.stdout.fileno()
    while time.time() < deadline:
        readable, _, _ = select.select([fd], [], [], 0.2)
        if readable:
            chunk = os.read(fd, min(65536, maximum + 1 - len(output)))
            if not chunk:
                process.wait()
                break
            output.extend(chunk)
            if len(output) > maximum:
                process.kill()
                process.wait()
                raise ValueError("registrar strings output exceeds bounded limit")
        if process.poll() is not None:
            break
    if process.poll() is None:
        process.kill()
        process.wait()
        raise ValueError("registrar strings command timed out")
    if process.returncode not in (0, None):
        raise ValueError("registrar strings command failed")
    remaining = maximum + 1 - len(output)
    if remaining > 0:
        output.extend(process.stdout.read(remaining))
    if len(output) > maximum:
        raise ValueError("registrar strings output exceeds bounded limit")
    return decode_text(bytes(output))


def _json_values(text):
    decoder = json.JSONDecoder()
    values = []
    for line in text.splitlines():
        for index, character in enumerate(line):
            if character not in "[{":
                continue
            try:
                value, _end = decoder.raw_decode(line[index:])
                values.append(value)
                break
            except ValueError:
                continue
    return values


def _case_get(value, *keys):
    lowered = {str(key).lower(): child for key, child in value.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _identity_from_state(value):
    inode = _case_get(value, "inode", "ino")
    device = _case_get(value, "device", "dev")
    nested = _case_get(value, "FileStateOS", "file_state_os", "meta")
    if isinstance(nested, dict):
        inode = inode if inode is not None else _case_get(nested, "inode", "ino")
        device = device if device is not None else _case_get(nested, "device", "dev")
    try:
        inode = int(inode) if inode is not None else None
    except (TypeError, ValueError):
        inode = None
    try:
        device = int(device) if device is not None else None
    except (TypeError, ValueError):
        device = None
    return inode, device


def collect_registrar_states(value, results=None):
    results = results if results is not None else []
    if isinstance(value, dict):
        source = _case_get(value, "source")
        offset = _case_get(value, "offset")
        if source is not None and offset is not None:
            inode, device = _identity_from_state(value)
            try:
                offset = int(offset)
            except (TypeError, ValueError):
                offset = None
            results.append(
                {
                    "source": decode_text(source),
                    "offset": offset,
                    "timestamp": _case_get(value, "timestamp", "updated_at"),
                    "ttl": _case_get(value, "ttl"),
                    "type": _case_get(value, "type"),
                    "meta": _case_get(value, "meta"),
                    "inode": inode,
                    "device": device,
                }
            )
        for child in value.values():
            collect_registrar_states(child, results)
    elif isinstance(value, list):
        for child in value:
            collect_registrar_states(child, results)
    return results


def parse_registrar_strings(text):
    states = []
    for value in _json_values(text):
        collect_registrar_states(value, states)
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


def _state_for_file(states, file_info):
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

    def sort_key(item):
        return (
            str(item.get("timestamp") or ""),
            item.get("offset") if item.get("offset") is not None else -1,
        )

    return {
        "current": sorted(current, key=sort_key)[-1] if current else None,
        "historical": sorted(path_states, key=sort_key)[-5:] if path_states and not current else [],
    }


def classify_registrar_progress(first_file, second_file, first_match, second_match, insufficient=False):
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
        "observation_window_insufficient": bool(insufficient),
        "first_state": first_match,
        "second_state": second_match,
    }


def registrar_snapshot(path_data):
    if not path_data:
        raise ValueError("path.data is unavailable")
    database = os.path.join(path_data, "bkunifylogbeat.bkpipe.db")
    return database, parse_registrar_strings(run_strings(database))


def inspect_registrar(database, first_states, first_sources, second_sources, window):
    first_by_path = {item.get("path"): item for item in first_sources.get("files", [])}
    first_matches = {path: _state_for_file(first_states, item) for path, item in first_by_path.items()}
    second_states = parse_registrar_strings(run_strings(database))
    results = []
    for second_file in second_sources.get("files", []):
        path = second_file.get("path")
        first_file = first_by_path.get(path, second_file)
        second_match = _state_for_file(second_states, second_file)
        progress = classify_registrar_progress(
            first_file,
            second_file,
            first_matches.get(path, {"current": None, "historical": []}),
            second_match,
            insufficient=window.get("insufficient", False),
        )
        results.append({"source": path, "progress": progress})
    return {"path": database, "state_count": len(second_states), "sources": results, "observation_window": window}


def _tail_file(path, maximum):
    size = os.path.getsize(path)
    start_offset = max(0, size - maximum)
    with open(path, "rb") as handle:
        handle.seek(start_offset, os.SEEK_SET)
        value = handle.read(maximum)
    content = decode_text(value)
    encoded = content.encode("utf-8")
    if len(encoded) > maximum:
        content = encoded[:maximum].decode("utf-8", "ignore")
    return content, size > len(value), size, start_offset, start_offset + len(value)


def inspect_collector_logs(path_logs, maximum=MAX_ERROR_LOG_BYTES):
    if not path_logs:
        raise ValueError("path.logs is unavailable")
    patterns = [
        os.path.join(path_logs, "bkunifylogbeat"),
        os.path.join(path_logs, "bkunifylogbeat.[0-9]*"),
        os.path.join(path_logs, "bkunifylogbeat.err*"),
        os.path.join(path_logs, "bkunifylogbeat.error*"),
        os.path.join(path_logs, "bkunifylogbeat-error*.log*"),
    ]
    candidates = sorted(set(path for pattern in patterns for path in glob.glob(pattern)))
    entries = []
    warnings = []
    for path in candidates:
        try:
            path_stat = os.lstat(path)
            if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
                warnings.append(make_warning("collector_log_file_skipped", "non-regular log path: {}".format(path)))
                continue
            entries.append((path, path_stat))
        except (IOError, OSError) as error:  # noqa: UP024 - Python 2 remote runtime
            warnings.append(make_warning("collector_log_file_unavailable", "{}: {}".format(path, error)))
    entries.sort(key=lambda item: item[1].st_mtime, reverse=True)
    remaining = maximum
    files = []
    original = sum(item[1].st_size for item in entries)
    truncated = False
    for path, path_stat in entries:
        size = path_stat.st_size
        if remaining <= 0:
            truncated = True
            continue
        try:
            content, item_truncated, size, start_offset, end_offset = _tail_file(path, remaining)
        except (IOError, OSError, ValueError) as error:  # noqa: UP024 - Python 2 remote runtime
            warnings.append(make_warning("collector_log_file_unavailable", "{}: {}".format(path, error)))
            continue
        returned = len(content.encode("utf-8"))
        remaining -= returned
        truncated = truncated or item_truncated
        files.append(
            {
                "path": path,
                "size_bytes": size,
                "mtime": path_stat.st_mtime,
                "start_offset_bytes": start_offset,
                "end_offset_bytes": end_offset,
                "content": content,
            }
        )
    return {
        "patterns": patterns,
        "files": files,
        "candidate_file_count": len(candidates),
        "file_count": len(entries),
        "original_size_bytes": original,
        "returned_size_bytes": maximum - remaining,
        "truncated": truncated or original > maximum,
        "limit_bytes": maximum,
        "warnings": warnings,
    }


def _probe_status_from_sources(value):
    if value.get("status") == "source_narrowing_required":
        return "warning", "source_narrowing_required", "more than 50 source files matched; specify source"
    if not value.get("files"):
        return "warning", "source_not_found", "no source file matched the target config"
    if any(item.get("inspection_warning") for item in value.get("files", [])):
        return "warning", "source_metadata_unavailable", "at least one source file could not be inspected"
    if any(not item.get("exists") for item in value.get("files", [])):
        return "warning", "source_not_found", "at least one configured source does not exist"
    if any(not item.get("readable") for item in value.get("files", [])):
        return "warning", "source_unreadable", "at least one configured source is not readable"
    return "success", "source_files_inspected", "source file metadata was inspected"


def execute(payload):
    probes = {}
    started_at = utcnow()
    setup_path = os.path.abspath(payload["setup_path"])
    expected_binary = os.path.join(setup_path, "plugins", "bin", "bkunifylogbeat")

    step_started = utcnow()
    step_clock = time.time()
    try:
        config_public, config_internal = inspect_configs(setup_path, int(payload["bk_data_id"]))
        config_status = "success" if config_public["matching_config_count"] else "warning"
        config_code = "config_matched" if config_public["matching_config_count"] else "target_data_id_not_found"
        probes["config"] = make_probe(
            config_status,
            config_code,
            "target sub-config was located"
            if config_public["matching_config_count"]
            else "no sub-config contains target DataID",
            config_public,
            warnings=config_public.get("warnings"),
            started_at=step_started,
            started_monotonic=step_clock,
        )
    except Exception as error:
        config_internal = None
        probes["config"] = make_probe(
            "failed", "config_unavailable", str(error), None, started_at=step_started, started_monotonic=step_clock
        )

    step_started = utcnow()
    step_clock = time.time()
    first_process = None
    try:
        first_process = process_snapshot(expected_binary)
        process_status = "success" if first_process["process_count"] == 1 else "warning"
        process_code = (
            "process_running"
            if first_process["process_count"] == 1
            else "process_not_running"
            if first_process["process_count"] == 0
            else "multiple_collector_processes"
        )
        probes["process"] = make_probe(
            process_status,
            process_code,
            "collector process was matched by exact binary path",
            first_process,
            warnings=first_process.get("warnings"),
            started_at=step_started,
            started_monotonic=step_clock,
        )
    except Exception as error:
        probes["process"] = make_probe(
            "failed",
            "process_inspection_failed",
            str(error),
            None,
            started_at=step_started,
            started_monotonic=step_clock,
        )

    first_sources = None
    patterns = []
    if config_internal and config_internal.get("matching_configs"):
        step_started = utcnow()
        step_clock = time.time()
        try:
            patterns = configured_patterns(config_internal["matching_configs"])
            first_sources = inspect_sources(
                patterns,
                payload.get("source"),
                bool(payload.get("include_source_sample")),
            )
            status, code, summary = _probe_status_from_sources(first_sources)
            probes["source_files"] = make_probe(
                status, code, summary, first_sources, started_at=step_started, started_monotonic=step_clock
            )
        except Exception as error:
            probes["source_files"] = make_probe(
                "failed",
                "source_inspection_failed",
                str(error),
                None,
                started_at=step_started,
                started_monotonic=step_clock,
            )
    else:
        probes["source_files"] = make_probe(
            "skipped", "target_config_unavailable", "source inspection requires a matching target config", None
        )

    window = calculate_observation_window(config_internal["durations"] if config_internal else dict(DEFAULT_DURATIONS))
    registrar_first = None
    registrar_first_error = None
    if config_internal and first_sources and first_sources.get("status") == "inspected":
        try:
            registrar_first = registrar_snapshot(config_internal.get("path_data"))
        except Exception as error:
            registrar_first_error = error

    sample_started = time.time()
    time.sleep(window["actual_seconds"])
    elapsed = max(0.001, time.time() - sample_started)
    second_process = None
    second_process_error = None
    try:
        second_process = process_snapshot(expected_binary)
    except Exception as error:
        second_process_error = error
    if first_process is not None and second_process is not None:
        process_resource_evidence = {
            "first": first_process,
            "second": second_process,
            "trend": process_delta(first_process, second_process, elapsed),
            "observation_window": window,
        }
        trend = process_resource_evidence["trend"]
        resource_status = (
            "warning"
            if trend["process_restarted_during_sampling"] or trend["process_availability_changed_during_sampling"]
            else "success"
        )
        resource_code = (
            "process_restarted_during_sampling"
            if trend["process_restarted_during_sampling"]
            else "process_availability_changed_during_sampling"
            if trend["process_availability_changed_during_sampling"]
            else "process_resources_sampled"
        )
        probes["process_resources"] = make_probe(
            resource_status,
            resource_code,
            "process resources are short-window evidence, not a leak or load diagnosis",
            process_resource_evidence,
        )
    else:
        probes["process_resources"] = make_probe(
            "failed",
            "process_resource_sampling_failed",
            "one or both process snapshots are unavailable",
            {
                "first": first_process,
                "second": second_process,
                "observation_window": window,
                "second_snapshot_error": str(second_process_error) if second_process_error is not None else None,
            },
        )

    second_sources = None
    if first_sources and first_sources.get("status") == "inspected":
        try:
            second_sources = inspect_sources(patterns, payload.get("source"), False)
            probes["source_files"]["evidence"]["second_sample"] = second_sources
        except Exception as error:
            probes["source_files"]["warnings"].append(make_warning("second_source_sample_failed", str(error)))

    if registrar_first and first_sources and second_sources:
        step_started = utcnow()
        step_clock = time.time()
        try:
            registrar = inspect_registrar(registrar_first[0], registrar_first[1], first_sources, second_sources, window)
            statuses = [item["progress"]["status"] for item in registrar.get("sources", [])]
            registrar_status = (
                "warning"
                if any(
                    item in ("registrar_state_not_found", "historical_state_only", "insufficient_observation_window")
                    for item in statuses
                )
                else "success"
            )
            probes["registrar"] = make_probe(
                registrar_status,
                "registrar_inspected",
                "Registrar ACK progress is not proof of GSE, cleaning, storage or query health",
                registrar,
                started_at=step_started,
                started_monotonic=step_clock,
            )
        except Exception as error:
            probes["registrar"] = make_probe(
                "failed",
                "registrar_inspection_failed",
                str(error),
                None,
                started_at=step_started,
                started_monotonic=step_clock,
            )
    elif registrar_first_error is not None:
        probes["registrar"] = make_probe("failed", "registrar_inspection_failed", str(registrar_first_error), None)
    else:
        probes["registrar"] = make_probe(
            "skipped", "source_or_config_unavailable", "Registrar correlation requires config and source evidence", None
        )

    if config_internal:
        step_started = utcnow()
        step_clock = time.time()
        try:
            logs = inspect_collector_logs(
                config_internal.get("path_logs"), int(payload.get("max_error_log_bytes", MAX_ERROR_LOG_BYTES))
            )
            if not logs.get("files"):
                log_status = "warning"
                log_code = "collector_logs_not_found"
            elif logs.get("truncated"):
                log_status = "warning"
                log_code = "collector_logs_truncated"
            elif logs.get("warnings"):
                log_status = "warning"
                log_code = "collector_logs_partially_collected"
            else:
                log_status = "success"
                log_code = "collector_logs_collected"
            probes["collector_logs"] = make_probe(
                log_status,
                log_code,
                "current and rotated bkunifylogbeat error logs were collected without DataID filtering",
                logs,
                warnings=logs.get("warnings"),
                started_at=step_started,
                started_monotonic=step_clock,
            )
        except Exception as error:
            probes["collector_logs"] = make_probe(
                "failed",
                "collector_logs_unavailable",
                str(error),
                None,
                started_at=step_started,
                started_monotonic=step_clock,
            )
    else:
        probes["collector_logs"] = make_probe(
            "skipped", "path_logs_unavailable", "collector log path requires the main config", None
        )

    failed = [value for value in probes.values() if value["status"] == "failed"]
    usable = [value for value in probes.values() if value["status"] in ("success", "warning")]
    task_status = "failed" if not usable else "partial" if failed else "success"
    return {
        "protocol": PROTOCOL,
        "task_status": task_status,
        "started_at": started_at,
        "finished_at": utcnow(),
        "setup_path": setup_path,
        "probes": probes,
        "partial": task_status == "partial",
    }


def decode_payload(token):
    padding = "=" * ((4 - len(token) % 4) % 4)
    value = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    payload = json.loads(decode_text(value))
    allowed = {"setup_path", "bk_data_id", "source", "include_source_sample", "max_error_log_bytes"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError("unsupported payload fields")
    if not payload.get("setup_path") or not payload.get("bk_data_id"):
        raise ValueError("setup_path and bk_data_id are required")
    if payload.get("source") is not None and not isinstance(payload.get("source"), STRING_TYPES):
        raise ValueError("source must be a string")
    maximum = int(payload.get("max_error_log_bytes", MAX_ERROR_LOG_BYTES))
    payload["max_error_log_bytes"] = min(MAX_ERROR_LOG_BYTES, max(0, maximum))
    return payload


def main(argv=None):
    argv = argv or sys.argv
    try:
        if len(argv) != 2:
            raise ValueError("exactly one bounded inspection token is required")
        result = execute(decode_payload(argv[1]))
    except Exception as error:
        result = {
            "protocol": PROTOCOL,
            "task_status": "failed",
            "started_at": utcnow(),
            "finished_at": utcnow(),
            "partial": False,
            "probes": {},
            "error": {"code": "inspection_script_failed", "message": str(error), "retryable": False},
        }
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
