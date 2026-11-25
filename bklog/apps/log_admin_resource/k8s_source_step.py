"""Bind one collector-side file observation to the selected Pod, input and rendered config."""

import base64
import hashlib
import json
import posixpath
import re
from pathlib import Path

from apps.log_admin_resource.collector_probe_evidence import _expand_recursive_glob, parse_yaml_local_inputs
from apps.log_admin_resource.handlers.inspection import sanitize_sensitive_text
from apps.log_admin_resource.k8s_inspection_client import object_to_dict
from apps.log_admin_resource.k8s_inspection import (
    COLLECTOR_CONTAINER_NAME,
    collector_child_config_hints,
    protect_source_paths,
)
from apps.log_admin_resource.k8s_probe import FixedProbeError, run_collector_script
from apps.log_admin_resource.scripts.collector_source_step import matches, read_directory
from apps.log_databus.constants import ContainerCollectorType


def _collector_has_host_root(pod):
    spec = object_to_dict(pod)["spec"]
    volumes = {v["name"]: v.get("host_path") or v.get("hostPath") or {} for v in spec["volumes"]}
    container = next(c for c in spec["containers"] if c["name"] == COLLECTOR_CONTAINER_NAME)
    return any(
        (m.get("mount_path") or m.get("mountPath") or "").rstrip("/") == "/var/host"
        and volumes[m["name"]].get("path") == "/"
        and not (m.get("sub_path") or m.get("subPath") or m.get("sub_path_expr") or m.get("subPathExpr"))
        for m in container.get("volume_mounts") or container.get("volumeMounts") or []
    )


def _target_mounts(target, rendered_sources):
    mounts, sources, host_paths = {}, {}, []
    container = target["container"]
    uid = target.get("pod_uid") or ""
    for index, mount in enumerate(container["volume_mounts"]):
        path = mount.get("mount_path") or mount.get("mountPath")
        if not path:
            continue
        volume = mount["volume"]
        host = volume.get("path")
        sub_path = mount.get("sub_path") or mount.get("subPath") or ""
        path = posixpath.normpath(path)
        mounts[path] = bool(
            volume.get("type") in {"empty_dir", "persistent_volume_claim"}
            or (host and posixpath.normpath("/" + posixpath.join(host, sub_path).lstrip("/")) != "/")
        )
        if not mounts[path]:
            continue
        name = mount.get("name")
        pod_dir = f"/pods/{uid}/"
        references = {
            src: src.split(pod_dir, 1)[1]
            for src in rendered_sources.get(path, ())
            if uid and pod_dir in src and posixpath.normpath(src) == src
        }
        if sub_path or mount.get("subPathExpr") or mount.get("sub_path_expr"):
            if uid and name and container.get("name"):
                suffix = f"/{container['name']}/{index}"
                # For a PVC kubelet can use the backing PV's name in its subpath pin.
                pins = [
                    src
                    for src, tail in references.items()
                    if tail.startswith("volume-subpaths/") and tail.endswith(suffix) and len(tail.split("/")) == 4
                ]
                if len(pins) <= 1:
                    sources[path] = pins[0] if pins else f"/var/lib/kubelet{pod_dir}volume-subpaths/{name}{suffix}"
        elif host:
            sources[path] = host
            host_paths.append(path)
        elif uid and name and volume.get("type") == "empty_dir":
            tail = f"volumes/kubernetes.io~empty-dir/{name}"
            matches = [src for src, relative in references.items() if relative == tail]
            if len(matches) <= 1:
                sources[path] = matches[0] if matches else f"/var/lib/kubelet{pod_dir}{tail}"
        elif volume.get("type") == "persistent_volume_claim":
            candidates = [src for src, tail in references.items() if tail.startswith("volumes/")]
            if len(candidates) == 1:
                sources[path] = candidates[0]
    return mounts, sources, host_paths


def _rendered_inputs(parsed, hints, data_id):
    for key, stream in parsed["streams"].items():
        if not key.startswith("child_config.") or stream.get("truncated"):
            continue
        name = posixpath.basename(stream.get("path") or "")
        if not any(name == hint or name.endswith("_" + hint) for hint in hints):
            continue
        for config in parse_yaml_local_inputs(stream.get("content") or ""):
            if str(config.get("dataid", config.get("data_id"))) == str(data_id):
                yield config


def _rendered_mount_paths(config):
    """Yield node paths only when the renderer's host-prefix convention is known."""
    for field, dest, src in (("mounts", "container_path", "host_path"), ("mount_infos", "dest", "source")):
        mappings = config.get(field)
        if not isinstance(mappings, list) or (
            field == "mount_infos" and config.get("remove_path_prefix") != "/var/host"
        ):
            continue
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            source, destination = mapping.get(src), mapping.get(dest)
            if not isinstance(source, str) or not isinstance(destination, str):
                continue
            if field == "mounts":
                if not source.startswith("/var/host/"):
                    continue
                source = source.removeprefix("/var/host")
            if source.startswith("/") and posixpath.normpath(source) == source:
                yield posixpath.normpath(destination), source


def source_directories(target, expected):
    by_config = {}
    if target.get("type") != "pod_container":
        return by_config
    matched_ids = {str(value) for value in target.get("matched_container_config_ids") or []}
    for item in expected:
        if item.get("collector_type") != ContainerCollectorType.CONTAINER:
            continue
        # Cluster-bound CRs have no SaaS config ID and have already passed target_config_matches.
        config_id = item["container_config_id"]
        if config_id is not None and str(config_id) not in matched_ids:
            continue
        patterns = set()
        for path in item["spec"].get("path") or []:
            if not isinstance(path, str) or not path.startswith("/") or posixpath.normpath(path) != path:
                continue
            for pattern in _expand_recursive_glob(path):
                directory = posixpath.dirname(pattern)
                # A filesystem root is not a target-specific log directory.
                first = directory.lstrip("/").split("/", 1)[0]
                if first and not any(ch in first for ch in "*?["):
                    patterns.add(directory)
        by_config[item["container_config_id"]] = patterns
    return by_config


def source_read_binding(target, expected, request, directory=None):
    by_config = source_directories(target, expected)
    if directory is None:
        patterns = set().union(*by_config.values())
        if not patterns:
            raise FixedProbeError("source_directory_unknown", "no target-specific log directory was identified")
        try:
            directory = read_directory(request, patterns)
        except ValueError as exc:
            raise FixedProbeError("outside_target_log_directory", str(exc)) from exc
    return directory, {key for key, patterns in by_config.items() if matches(directory, patterns)}


def source_policy(parsed, target, expected, data_id, collector_pod, *, metadata_only=False):
    if not _collector_has_host_root(collector_pod):
        raise FixedProbeError("host_proc_unavailable", "the collector has no verified host root mount")
    by_config = source_directories(target, expected)
    pids = set()
    rendered_sources = {}
    for item in expected:
        if item["container_config_id"] not in by_config:
            continue
        hints = collector_child_config_hints(target, [item])
        for config in _rendered_inputs(parsed, hints, data_id):
            roots = [config.get("root_fs")]
            for destination, source in _rendered_mount_paths(config):
                if destination == "/":
                    roots.append("/var/host" + source)
                else:
                    rendered_sources.setdefault(destination, set()).add(source)
            for root in roots:
                match = re.fullmatch(r"/var/host/proc/([1-9][0-9]*)/root", root) if isinstance(root, str) else None
                if match:
                    pids.add(match[1])
    mounts, sources, host_paths = _target_mounts(target, rendered_sources)
    policy = {
        "mounts": mounts,
        "mount_sources": sources,
        "host_path_mounts": host_paths,
        "runtime_id": (target["container"].get("container_id") or "").split("://")[-1],
    }
    if len(pids) == 1:
        policy["runtime_pid"] = pids.pop()
    if metadata_only:
        return policy
    directories = set().union(*by_config.values())
    if not directories:
        raise FixedProbeError("source_directory_unknown", "no target-specific log directory was identified")
    return {**policy, "directories": sorted(directories)}


def inspect_source_step(client, candidate, parsed, target, expected, data_id, request, collector_pod):
    native = request.get("path_space") == "collector"
    if native and request["operation"] != "read":
        if "via" in request:
            raise FixedProbeError("invalid_collector_step", "collector paths support metadata operations only")
        policy = {}
        identity = {}
    else:
        policy = source_policy(
            parsed, target, expected, data_id, collector_pod, metadata_only=request["operation"] != "read"
        )
        identity = {"pod_uid": target["pod_uid"], "container_id": target["container"]["container_id"]}
    policy.update(collector_pod_uid=candidate.pod_uid, collector_container_id=candidate.collector_container_id)
    policy["interval"] = min(10, max(1, int(parsed["values"].get("observation_seconds") or 5)))
    policy["pid"] = int(parsed["values"].get("process_pid") or 0)
    encoded = base64.b64encode(json.dumps([policy, request]).encode()).decode("ascii")
    if len(encoded) > 65536:
        raise FixedProbeError("source_policy_too_large", "rendered source policy exceeds the fixed argument budget")
    helper = Path(__file__).with_name("scripts").joinpath("collector_source_step.py").read_text()
    script = (
        "cd / || exit 1\n"
        "for py in /usr/bin/python3 /usr/bin/python /usr/local/bin/python3; do\n"
        '    [ -x "$py" ] || continue\n'
        f"    exec \"$py\" -E -S - {encoded} <<'BKLOG_SOURCE_STEP'\n"
        f"{helper}\nBKLOG_SOURCE_STEP\n"
        'done\nprintf \'{"error":"collector_python_unavailable"}\\n\'\nexit\n'
    )
    stdout, _, _ = run_collector_script(client, candidate, ["/bin/sh", "-s"], script)
    try:
        result = json.loads(stdout)
    except ValueError as exc:
        raise FixedProbeError(
            "source_step_invalid_response", "collector file observation returned no valid JSON"
        ) from exc
    protect_source_paths(result)
    result["source_paths_checked"] = True
    failed = bool(result.get("error"))
    if request["operation"] == "list" and not failed:
        row = result["observation"]
        # Save only positions before the evidence store redacts text. The API
        # can then distinguish a real literal "***" from a redacted filename.
        row["redacted_entry_positions"] = [
            pos for pos, path in enumerate(row["entries"], 1) if sanitize_sensitive_text(path, maximum=None) != path
        ]
    return {
        "status": "failed" if failed else "success",
        "code": "source_step_incomplete" if failed else "source_step_completed",
        "summary": "file evidence from the selected collector container",
        "evidence": {
            "request": request,
            **identity,
            "collector_pod_uid": candidate.pod_uid,
            **result,
        },
        "probe_metadata": {
            "script_sha256": hashlib.sha256(helper.encode()).hexdigest(),
            "container": COLLECTOR_CONTAINER_NAME,
        },
        "warnings": [],
    }
