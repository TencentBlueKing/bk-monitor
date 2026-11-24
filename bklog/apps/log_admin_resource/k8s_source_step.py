"""Bind one collector-side file observation to the selected Pod, input and rendered config."""

import base64
import hashlib
import json
import posixpath
import re
from pathlib import Path

import yaml

from apps.log_admin_resource.collector_probe_evidence import _expand_recursive_glob
from apps.log_admin_resource.k8s_inspection_client import object_to_dict
from apps.log_admin_resource.k8s_inspection import COLLECTOR_CONTAINER_NAME, collector_child_config_hints
from apps.log_admin_resource.k8s_probe import FixedProbeError, run_collector_script
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


def _target_mounts(target):
    mounts = {}
    for mount in target["container"]["volume_mounts"]:
        path = mount.get("mount_path") or mount.get("mountPath")
        if not path:
            continue
        volume = mount["volume"]
        host = volume.get("path")
        sub_path = mount.get("sub_path") or mount.get("subPath") or ""
        mounts[posixpath.normpath(path)] = bool(
            volume.get("type") in {"empty_dir", "persistent_volume_claim"}
            or (host and posixpath.normpath("/" + posixpath.join(host, sub_path).lstrip("/")) != "/")
        )
    return mounts


def _rendered_inputs(parsed, hints, data_id):
    for key, stream in parsed["streams"].items():
        if not key.startswith("child_config.") or stream.get("truncated"):
            continue
        name = posixpath.basename(stream.get("path") or "")
        if not any(name == hint or name.endswith("_" + hint) for hint in hints):
            continue
        for doc in yaml.safe_load_all(stream.get("content") or ""):
            if not isinstance(doc, dict):
                continue
            inputs = doc.get("local") or []
            for config in inputs if isinstance(inputs, list) else [inputs]:
                if isinstance(config, dict) and str(config.get("dataid", config.get("data_id"))) == str(data_id):
                    yield config


def source_policy(parsed, target, expected, data_id, collector_pod, *, metadata_only=False):
    if not _collector_has_host_root(collector_pod):
        raise FixedProbeError("host_proc_unavailable", "the collector has no verified host root mount")
    directories = set()
    pids = set()
    for item in expected:
        if item.get("collector_type") != ContainerCollectorType.CONTAINER:
            continue
        hints = collector_child_config_hints(target, [item])
        if not hints:
            continue
        for path in item["spec"].get("path") or []:
            if not isinstance(path, str) or not path.startswith("/") or posixpath.normpath(path) != path:
                continue
            for pattern in _expand_recursive_glob(path):
                directory = posixpath.dirname(pattern)
                # A filesystem root is not a target-specific log directory.
                first = directory.lstrip("/").split("/", 1)[0]
                if first and not any(ch in first for ch in "*?["):
                    directories.add(directory)
        for config in _rendered_inputs(parsed, hints, data_id):
            # Only use a rendered process root as a PID hint. Host source paths
            # can be renamed or rebound independently of the live Pod mount.
            roots = [config.get("root_fs")]
            if config.get("remove_path_prefix") == "/var/host":
                roots.extend(
                    "/var/host" + mount["source"]
                    for mount in config.get("mount_infos") or []
                    if isinstance(mount, dict) and mount.get("dest") == "/" and isinstance(mount.get("source"), str)
                )
            for root in roots:
                match = re.fullmatch(r"/var/host/proc/([1-9][0-9]*)/root", root) if isinstance(root, str) else None
                if match:
                    pids.add(match[1])
    policy = {
        "mounts": _target_mounts(target),
        "runtime_id": (target["container"].get("container_id") or "").split("://")[-1],
    }
    if len(pids) == 1:
        policy["runtime_pid"] = pids.pop()
    if metadata_only:
        return policy
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
    failed = bool(result.get("error"))
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
