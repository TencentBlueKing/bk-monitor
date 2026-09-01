"""Shared fixed Shell probe contract for host and Kubernetes inspection."""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any


PROBE_SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "collector_inspection.sh"
PROBE_PROTOCOL = "bklog.collector.inspection.probe.v1"
PROBE_VERSION = "137707063.3"
PROBE_ID = "bklog.collector.fixed_read_only"
MAX_PROBE_OUTPUT_BYTES = 10 * 1024 * 1024


class FixedProbeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def fixed_probe_script() -> bytes:
    """Return the exact repository-owned script used by every transport."""

    return PROBE_SCRIPT_PATH.read_bytes()


def fixed_probe_metadata(**transport: Any) -> dict[str, Any]:
    source = fixed_probe_script()
    return {
        "probe_id": PROBE_ID,
        "probe_protocol": PROBE_PROTOCOL,
        "probe_version": PROBE_VERSION,
        "script_sha256": hashlib.sha256(source).hexdigest(),
        "command": ["/bin/sh", "-s"],
        "mutations_permitted": False,
        **transport,
    }


def parse_probe_output(value: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    streams: dict[str, dict[str, Any]] = {}
    for line in value.splitlines():
        marker = line.find("BKLOG_")
        if marker > 0:
            line = line[marker:]
        fields = line.split("\t", 2)
        if not fields:
            continue
        if fields[0] == "BKLOG_KV" and len(fields) == 3:
            values[fields[1]] = fields[2]
            continue
        if fields[0] == "BKLOG_STREAM":
            header = line.split("\t", 5)
            if len(header) == 6:
                streams[header[1]] = {
                    "path": header[2],
                    "returned_size_bytes": _optional_int(header[3]),
                    "total_size_bytes": _optional_int(header[4]),
                    "truncated": header[5] == "true",
                    "lines": [],
                }
            continue
        if fields[0] == "BKLOG_LINE" and len(fields) == 3 and fields[1] in streams:
            streams[fields[1]]["lines"].append(fields[2])
            continue
        if fields[0] == "BKLOG_B64" and len(fields) == 3 and fields[1] in streams:
            try:
                decoded = base64.b64decode(fields[2], validate=True)
            except (binascii.Error, ValueError):
                streams[fields[1]]["decode_error"] = True
            else:
                streams[fields[1]]["binary_content"] = decoded
    for stream_value in streams.values():
        binary_content = stream_value.pop("binary_content", None)
        legacy_lines = stream_value.pop("lines")
        stream_value["content"] = (
            binary_content.decode("utf-8", errors="replace") if binary_content is not None else "\n".join(legacy_lines)
        )
    return {"values": values, "streams": streams}


def parse_and_validate_probe_output(value: str) -> dict[str, Any]:
    returned_size_bytes = len(value.encode("utf-8", errors="replace"))
    if returned_size_bytes > MAX_PROBE_OUTPUT_BYTES:
        raise FixedProbeError(
            "probe_output_limit_exceeded",
            "fixed collector probe exceeded the 10 MiB output limit",
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
    parsed["returned_size_bytes"] = returned_size_bytes
    parsed["maximum_size_bytes"] = MAX_PROBE_OUTPUT_BYTES
    return parsed


def _optional_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
