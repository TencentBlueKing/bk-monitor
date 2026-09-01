"""Fixed collector-container probe and parser for Kubernetes inspection."""

from __future__ import annotations

import base64
import binascii
import hashlib
import time
from pathlib import Path
from typing import Any

from kubernetes.stream import stream

from apps.log_admin_resource.k8s_inspection import COLLECTOR_CONTAINER_NAME, CollectorCandidate
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient


PROBE_SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "k8s_inspection.sh"
PROBE_PROTOCOL = "bklog.collector.k8s_inspection.probe.v1"
FIXED_PROBE_TIMEOUT_SECONDS = 60
MAX_PROBE_OUTPUT_BYTES = 10 * 1024 * 1024


class FixedProbeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def fixed_probe_metadata(candidate: CollectorCandidate) -> dict[str, Any]:
    source = PROBE_SCRIPT_PATH.read_bytes()
    return {
        "probe_id": "bklog.collector.k8s.fixed_read_only",
        "probe_version": "137707084.1",
        "script_sha256": hashlib.sha256(source).hexdigest(),
        "collector_image_id": candidate.collector_image_id,
        "command": ["/bin/sh", "-s"],
        "container": COLLECTOR_CONTAINER_NAME,
        "mutations_permitted": False,
    }


def run_fixed_collector_probe(client: K8sInspectionClient, candidate: CollectorCandidate) -> dict[str, Any]:
    """Execute the repository-owned script in one already-validated collector identity."""

    script = PROBE_SCRIPT_PATH.read_text(encoding="utf-8")
    response = stream(
        client.bcs.api_instance_core_v1.connect_get_namespaced_pod_exec,
        name=candidate.pod_name,
        namespace=candidate.namespace,
        container=COLLECTOR_CONTAINER_NAME,
        command=["/bin/sh", "-s"],
        stderr=True,
        stdin=True,
        stdout=True,
        tty=False,
        _preload_content=False,
        _request_timeout=FIXED_PROBE_TIMEOUT_SECONDS,
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    total = 0
    deadline = time.monotonic() + FIXED_PROBE_TIMEOUT_SECONDS
    try:
        response.write_stdin(script if script.endswith("\n") else script + "\n")
        while response.is_open() and time.monotonic() < deadline:
            response.update(timeout=1)
            for ready, reader, parts in (
                (response.peek_stdout, response.read_stdout, stdout_parts),
                (response.peek_stderr, response.read_stderr, stderr_parts),
            ):
                if not ready():
                    continue
                chunk = reader()
                text = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else str(chunk)
                size = len(text.encode("utf-8", errors="replace"))
                if total + size > MAX_PROBE_OUTPUT_BYTES:
                    response.close()
                    raise FixedProbeError(
                        "probe_output_limit_exceeded",
                        "fixed collector probe exceeded the 10 MiB output limit",
                        retryable=False,
                    )
                parts.append(text)
                total += size
        if response.is_open():
            response.close()
            raise FixedProbeError("probe_timed_out", "fixed collector probe exceeded 60 seconds")
    finally:
        if response.is_open():
            response.close()

    parsed = parse_probe_output("".join(stdout_parts))
    if parsed.get("values", {}).get("protocol") != PROBE_PROTOCOL:
        raise FixedProbeError("probe_protocol_invalid", "fixed collector probe returned an invalid protocol")
    stderr = "".join(stderr_parts)[-65536:]
    return_code = getattr(response, "returncode", None)
    if return_code == 127 or ("/bin/sh" in stderr and "not found" in stderr.lower()):
        raise FixedProbeError(
            "probe_dependency_missing", "the collector image does not provide the fixed /bin/sh probe dependency"
        )
    if parsed.get("values", {}).get("completed") != "true":
        raise FixedProbeError("probe_incomplete", "fixed collector probe did not reach its completion marker")
    if return_code not in {None, 0}:
        raise FixedProbeError("probe_failed", f"fixed collector probe exited with status {return_code}")
    parsed["stderr"] = stderr
    parsed["return_code"] = return_code
    parsed["returned_size_bytes"] = total
    parsed["maximum_size_bytes"] = MAX_PROBE_OUTPUT_BYTES
    parsed["metadata"] = fixed_probe_metadata(candidate)
    return parsed


def parse_probe_output(value: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    streams: dict[str, dict[str, Any]] = {}
    for line in value.splitlines():
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


def _optional_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
