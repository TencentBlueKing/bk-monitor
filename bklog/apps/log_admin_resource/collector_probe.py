"""Shared fixed Shell probe contract for host and Kubernetes inspection."""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any


PROBE_SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "collector_inspection.sh"
PROBE_PROTOCOL = "bklog.collector.inspection.probe.v1"
PROBE_VERSION = "137707063.4"
PROBE_ID = "bklog.collector.fixed_read_only"
# BK-JOB/GSE caps one atomic script-task log at 5 MiB; keep one MiB for transport framing and prefixes.
MAX_PROBE_OUTPUT_BYTES = 4 * 1024 * 1024

_MANIFEST_KEYS = {
    "manifest_kv_count",
    "manifest_stream_count",
    "output_budget_bytes",
    "output_budget_exhausted",
    "completed",
}


class FixedProbeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def fixed_probe_script() -> bytes:
    """Return the exact repository-owned script used by every transport."""

    return PROBE_SCRIPT_PATH.read_bytes()


def fixed_probe_arguments(bk_data_id: int, include_source_sample: bool) -> tuple[str, str]:
    """Build the only two server-controlled arguments accepted by the fixed probe."""

    if isinstance(bk_data_id, bool):
        raise ValueError("bk_data_id must be a positive integer")
    try:
        normalized_data_id = int(bk_data_id)
    except (TypeError, ValueError) as error:
        raise ValueError("bk_data_id must be a positive integer") from error
    if normalized_data_id <= 0 or str(normalized_data_id) != str(bk_data_id):
        raise ValueError("bk_data_id must be a positive integer")
    return str(normalized_data_id), "1" if include_source_sample else "0"


def fixed_probe_command(bk_data_id: int, include_source_sample: bool) -> list[str]:
    return ["/bin/sh", "-s", "--", *fixed_probe_arguments(bk_data_id, include_source_sample)]


def fixed_probe_metadata(*, bk_data_id: int, include_source_sample: bool, **transport: Any) -> dict[str, Any]:
    source = fixed_probe_script()
    return {
        "probe_id": PROBE_ID,
        "probe_protocol": PROBE_PROTOCOL,
        "probe_version": PROBE_VERSION,
        "script_sha256": hashlib.sha256(source).hexdigest(),
        "command": fixed_probe_command(bk_data_id, include_source_sample),
        "target_data_id": bk_data_id,
        "include_source_sample": include_source_sample,
        "mutations_permitted": False,
        **transport,
    }


def parse_probe_output(value: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    streams: dict[str, dict[str, Any]] = {}
    content_kv_count = 0
    stream_count = 0
    duplicate_stream_names: list[str] = []
    unmatched_end_streams: list[str] = []
    for line in value.splitlines():
        marker = line.find("BKLOG_")
        if marker > 0:
            line = line[marker:]
        fields = line.split("\t", 2)
        if not fields:
            continue
        if fields[0] == "BKLOG_KV" and len(fields) == 3:
            values[fields[1]] = fields[2]
            if fields[1] not in _MANIFEST_KEYS:
                content_kv_count += 1
            continue
        if fields[0] == "BKLOG_STREAM":
            header = line.split("\t", 6)
            if len(header) in {6, 7}:
                stream_count += 1
                if header[1] in streams:
                    duplicate_stream_names.append(header[1])
                streams[header[1]] = {
                    "path": header[2],
                    "returned_size_bytes": _optional_int(header[3]),
                    "total_size_bytes": _optional_int(header[4]),
                    "truncated": header[5] == "true",
                    "encoded_size_bytes": _optional_int(header[6]) if len(header) == 7 else None,
                    "encoded_parts": [],
                    "base64_record_count": 0,
                    "ended": False,
                    "lines": [],
                }
            continue
        if fields[0] == "BKLOG_LINE" and len(fields) == 3 and fields[1] in streams:
            streams[fields[1]]["lines"].append(fields[2])
            continue
        if fields[0] == "BKLOG_B64" and len(fields) == 3 and fields[1] in streams:
            streams[fields[1]]["base64_record_count"] += 1
            streams[fields[1]]["encoded_parts"].append(fields[2])
            continue
        if fields[0] == "BKLOG_END_STREAM" and len(fields) >= 2:
            stream = streams.get(fields[1])
            if stream is None:
                unmatched_end_streams.append(fields[1])
            else:
                stream["ended"] = True
    for stream_value in streams.values():
        encoded = "".join(stream_value.pop("encoded_parts"))
        stream_value["actual_encoded_size_bytes"] = len(encoded.encode("ascii", errors="replace"))
        binary_content = None
        if stream_value["base64_record_count"]:
            try:
                binary_content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                stream_value["decode_error"] = True
            else:
                stream_value["actual_decoded_size_bytes"] = len(binary_content)
        legacy_lines = stream_value.pop("lines")
        stream_value["content"] = (
            binary_content.decode("utf-8", errors="replace") if binary_content is not None else "\n".join(legacy_lines)
        )
    return {
        "values": values,
        "streams": streams,
        "integrity": {
            "content_kv_count": content_kv_count,
            "stream_count": stream_count,
            "duplicate_stream_names": duplicate_stream_names,
            "unmatched_end_streams": unmatched_end_streams,
        },
    }


def parse_and_validate_probe_output(value: str) -> dict[str, Any]:
    returned_size_bytes = len(value.encode("utf-8", errors="replace"))
    if returned_size_bytes > MAX_PROBE_OUTPUT_BYTES:
        raise FixedProbeError(
            "probe_output_limit_exceeded",
            "fixed collector probe exceeded the 4 MiB output limit",
            retryable=False,
        )
    parsed = parse_probe_output(value)
    values = parsed.get("values") or {}
    if values.get("protocol") != PROBE_PROTOCOL:
        raise FixedProbeError("probe_protocol_invalid", "fixed collector probe returned an invalid protocol")
    if values.get("probe_version") != PROBE_VERSION:
        raise FixedProbeError("probe_version_invalid", "fixed collector probe returned an unexpected version")
    if values.get("completed") != "true":
        raise FixedProbeError("probe_incomplete", "fixed collector probe did not reach its completion marker")
    _validate_integrity(parsed)
    parsed["returned_size_bytes"] = returned_size_bytes
    parsed["maximum_size_bytes"] = MAX_PROBE_OUTPUT_BYTES
    return parsed


def _validate_integrity(parsed: dict[str, Any]) -> None:
    values = parsed["values"]
    streams = parsed["streams"]
    integrity = parsed["integrity"]
    declared_kv_count = _optional_int(values.get("manifest_kv_count", ""))
    declared_stream_count = _optional_int(values.get("manifest_stream_count", ""))
    declared_budget = _optional_int(values.get("output_budget_bytes", ""))
    if declared_budget != MAX_PROBE_OUTPUT_BYTES:
        raise FixedProbeError("probe_manifest_invalid", "fixed collector probe returned an invalid output budget")
    if declared_kv_count != integrity["content_kv_count"]:
        raise FixedProbeError("probe_incomplete", "fixed collector probe KV manifest is incomplete")
    if declared_stream_count != integrity["stream_count"]:
        raise FixedProbeError("probe_incomplete", "fixed collector probe stream manifest is incomplete")
    if integrity["duplicate_stream_names"] or integrity["unmatched_end_streams"]:
        raise FixedProbeError("probe_stream_invalid", "fixed collector probe returned an invalid stream sequence")
    for stream in streams.values():
        if not stream["ended"] or stream["base64_record_count"] != 1:
            raise FixedProbeError("probe_incomplete", "fixed collector probe returned an incomplete stream")
        if stream.get("decode_error"):
            raise FixedProbeError("probe_stream_invalid", "fixed collector probe returned invalid base64 content")
        if stream["encoded_size_bytes"] != stream.get("actual_encoded_size_bytes"):
            raise FixedProbeError("probe_incomplete", "fixed collector probe stream encoded size does not match")
        if stream["returned_size_bytes"] != stream.get("actual_decoded_size_bytes"):
            raise FixedProbeError("probe_incomplete", "fixed collector probe stream decoded size does not match")


def _optional_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
