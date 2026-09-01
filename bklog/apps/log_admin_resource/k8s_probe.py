"""Kubernetes transport adapter for the shared fixed collector probe."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from kubernetes.stream import stream

from apps.log_admin_resource.collector_probe import (
    MAX_PROBE_OUTPUT_BYTES,
    FixedProbeError,
    fixed_probe_command,
    fixed_probe_metadata as common_probe_metadata,
    fixed_probe_script,
    parse_and_validate_probe_output,
)
from apps.log_admin_resource.k8s_inspection import COLLECTOR_CONTAINER_NAME, CollectorCandidate
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient


FIXED_PROBE_TIMEOUT_SECONDS = 60


def fixed_probe_metadata(
    candidate: CollectorCandidate,
    *,
    bk_data_id: int,
    include_source_sample: bool,
    child_config_hints: Iterable[str] = (),
) -> dict[str, Any]:
    return common_probe_metadata(
        bk_data_id=bk_data_id,
        include_source_sample=include_source_sample,
        child_config_hints=child_config_hints,
        executor="K8S_POD_EXEC",
        collector_image_id=candidate.collector_image_id,
        container=COLLECTOR_CONTAINER_NAME,
    )


def run_fixed_collector_probe(
    client: K8sInspectionClient,
    candidate: CollectorCandidate,
    *,
    bk_data_id: int,
    include_source_sample: bool,
    child_config_hints: Iterable[str] = (),
) -> dict[str, Any]:
    """Execute the repository-owned script in one already-validated collector identity."""

    script = fixed_probe_script().decode("utf-8")
    response = stream(
        client.bcs.api_instance_core_v1.connect_get_namespaced_pod_exec,
        name=candidate.pod_name,
        namespace=candidate.namespace,
        container=COLLECTOR_CONTAINER_NAME,
        command=fixed_probe_command(bk_data_id, include_source_sample, child_config_hints),
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
                        "fixed collector probe exceeded the 4 MiB output limit",
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

    stderr = "".join(stderr_parts)[-65536:]
    return_code = getattr(response, "returncode", None)
    if return_code == 127 or ("/bin/sh" in stderr and "not found" in stderr.lower()):
        raise FixedProbeError(
            "probe_dependency_missing", "the collector image does not provide the fixed /bin/sh probe dependency"
        )
    if return_code not in {None, 0}:
        raise FixedProbeError("probe_failed", f"fixed collector probe exited with status {return_code}")
    parsed = parse_and_validate_probe_output("".join(stdout_parts))
    parsed["stderr"] = stderr
    parsed["return_code"] = return_code
    parsed["metadata"] = fixed_probe_metadata(
        candidate,
        bk_data_id=bk_data_id,
        include_source_sample=include_source_sample,
        child_config_hints=child_config_hints,
    )
    return parsed
