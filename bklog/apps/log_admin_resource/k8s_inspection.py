"""Pure domain rules for bounded Kubernetes collector inspection."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from apps.log_admin_resource.handlers.inspection import sanitize_sensitive_text
from apps.log_admin_resource.k8s_inspection_client import object_to_dict
from apps.log_databus.constants import ContainerCollectorType, LabelSelectorOperator
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario


COLLECTOR_CONTAINER_NAME = "bkunifylogbeat-bklog"
SIDECAR_CONTAINER_NAME = "bklogsidecar"
COLLECTOR_BINARY = "/bin/bkunifylogbeat"
MAIN_CONFIG_PATH = "/data/etc/bkunifylogbeat.conf"
SIDECAR_BINARY = "/bk-log-sidecar"
SIDECAR_REQUIRED_ARGS = {
    "--bkunifylogbeat-config=/data/etc/bkunifylogbeat",
    "--bkunifylogbeat-pid-file=/data/run/bkunifylogbeat.pid",
    "--host-path=/var/host/",
}
BKLOG_CONFIG_CRD_NAME = "bklogconfigs.bk.tencent.com"
BKLOG_CONFIG_NAMESPACE = "default"
MAX_CANDIDATES = 20
MAX_CONTRACT_EVIDENCE = 100


@dataclass(frozen=True)
class CollectorCandidate:
    cluster_id: str
    namespace: str
    daemon_set_name: str
    daemon_set_uid: str
    pod_name: str
    pod_uid: str
    node_name: str
    collector_container_id: str
    collector_image_id: str
    manual_installation: bool

    def binding(self) -> dict[str, Any]:
        return asdict(self)


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def target_identity(target: dict[str, Any] | None) -> str:
    return sha256_json(target)


def expected_bklog_configs(collector: Any, container_configs: Iterable[Any]) -> list[dict[str, Any]]:
    results = []
    for container_config in container_configs:
        if collector.yaml_config_enabled and container_config.raw_config:
            spec = copy.deepcopy(container_config.raw_config)
            spec.update(
                {
                    "dataId": collector.bk_data_id,
                    "extMeta": {label["key"]: label["value"] for label in (collector.extra_labels or []) if label},
                    "addPodLabel": collector.add_pod_label,
                    "addPodAnnotation": collector.add_pod_annotation,
                }
            )
        else:
            spec = K8sCollectorHandler.collector_container_config_to_raw_config(collector, container_config)

        edge_output = CollectorScenario.get_edge_transport_output_params(collector.data_link_id)
        if edge_output:
            spec.setdefault("extOptions", {})["output.kafka"] = edge_output
        if (container_config.params or {}).get("tail_files") is False:
            spec.setdefault("extOptions", {})["tail_files"] = False
        spec.setdefault("extMeta", {})["bk_bcs_cluster_id"] = collector.bcs_cluster_id
        name = f"{collector.collector_config_name_en.lower()}-{collector.bk_biz_id}-{container_config.id}".replace(
            "_", "-"
        )
        results.append(
            {
                "name": name,
                "container_config_id": container_config.id,
                "collector_type": container_config.collector_type,
                "spec": spec,
                "safe_spec": safe_spec_projection(spec),
            }
        )
    return results


def safe_spec_projection(spec: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "dataId",
        "path",
        "exclude_files",
        "encoding",
        "logConfigType",
        "allContainer",
        "namespaceSelector",
        "workloadType",
        "workloadName",
        "containerNameMatch",
        "containerNameExclude",
        "labelSelector",
        "annotationSelector",
        "multiline",
        "delimiter",
        "addPodLabel",
        "addPodAnnotation",
    )
    result = {key: copy.deepcopy(spec.get(key)) for key in keys if key in spec}
    ext_options = spec.get("extOptions") or {}
    if "tail_files" in ext_options:
        result["tail_files"] = ext_options["tail_files"]
    return result


def desired_config_evidence(
    *, expected: list[dict[str, Any]], actual_items: Iterable[dict[str, Any]], configured_namespace: str
) -> dict[str, Any]:
    actual_by_name = {
        str((item.get("metadata") or {}).get("name")): item
        for item in actual_items
        if isinstance(item, dict) and (item.get("metadata") or {}).get("name")
    }
    rows = []
    required_bk_envs = set()
    for item in expected:
        actual = actual_by_name.get(item["name"])
        metadata = (actual or {}).get("metadata") or {}
        actual_spec = (actual or {}).get("spec") or {}
        labels = metadata.get("labels") or {}
        if labels.get("bk_env"):
            required_bk_envs.add(str(labels["bk_env"]))
        exact = bool(actual is not None and actual_spec == item["spec"])
        rows.append(
            {
                "name": item["name"],
                "container_config_id": item["container_config_id"],
                "present": actual is not None,
                "namespace": configured_namespace,
                "uid": metadata.get("uid"),
                "generation": metadata.get("generation"),
                "resource_version": metadata.get("resourceVersion") or metadata.get("resource_version"),
                "creation_timestamp": metadata.get("creationTimestamp") or metadata.get("creation_timestamp"),
                "deletion_timestamp": metadata.get("deletionTimestamp") or metadata.get("deletion_timestamp"),
                "labels": {key: labels[key] for key in ("bk_env", "app.kubernetes.io/managed-by") if key in labels},
                "expected_spec_sha256": sha256_json(item["spec"]),
                "actual_spec_sha256": sha256_json(actual_spec) if actual is not None else None,
                "exact_match": exact,
                "different_paths": different_paths(item["spec"], actual_spec) if actual is not None else ["$"],
                "safe_expected_spec": item["safe_spec"],
                "safe_actual_spec": safe_spec_projection(actual_spec) if actual is not None else None,
                "conditions": _safe_conditions((actual or {}).get("status") or {}),
            }
        )
    return {
        "configured_namespace": configured_namespace,
        "items": rows,
        "all_present": all(item["present"] for item in rows),
        "all_exact_match": all(item["exact_match"] for item in rows),
        "required_bk_envs": sorted(required_bk_envs),
    }


def different_paths(expected: Any, actual: Any, path: str = "$") -> list[str]:
    if type(expected) is not type(actual):
        return [path]
    if isinstance(expected, dict):
        paths = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                paths.append(f"{path}.{key}")
            else:
                paths.extend(different_paths(expected[key], actual[key], f"{path}.{key}"))
            if len(paths) >= 100:
                return paths[:100]
        return paths
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [path]
        paths = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            paths.extend(different_paths(left, right, f"{path}[{index}]"))
            if len(paths) >= 100:
                return paths[:100]
        return paths
    return [] if expected == actual else [path]


def target_config_matches(
    target: dict[str, Any], target_object: dict[str, Any], expected: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matches = []
    for item in expected:
        spec = item["spec"]
        if target["type"] == "node":
            if spec.get("logConfigType") != ContainerCollectorType.NODE:
                continue
            if _labels_match(target_object.get("metadata", {}).get("labels") or {}, spec.get("labelSelector") or {}):
                matches.append(item)
            continue
        if spec.get("logConfigType") not in {ContainerCollectorType.CONTAINER, ContainerCollectorType.STDOUT}:
            continue
        if _pod_target_matches(target, target_object, spec):
            matches.append(item)
    return matches


def _pod_target_matches(target: dict[str, Any], pod: dict[str, Any], spec: dict[str, Any]) -> bool:
    metadata = pod.get("metadata") or {}
    pod_spec = pod.get("spec") or {}
    namespace_selector = spec.get("namespaceSelector") or {}
    namespace = str(metadata.get("namespace") or "")
    if not namespace_selector.get("any") and namespace_selector.get("matchNames"):
        if namespace not in namespace_selector.get("matchNames"):
            return False
    if namespace in (namespace_selector.get("excludeNames") or []):
        return False
    if not _labels_match(metadata.get("labels") or {}, spec.get("labelSelector") or {}):
        return False
    if not _expressions_match(
        metadata.get("annotations") or {}, (spec.get("annotationSelector") or {}).get("matchExpressions") or []
    ):
        return False
    workload_type, workload_name = pod_workload(metadata)
    if spec.get("workloadType") and workload_type != spec.get("workloadType"):
        return False
    if spec.get("workloadName"):
        try:
            if not re.match(str(spec["workloadName"]), workload_name or ""):
                return False
        except re.error:
            return False
    container_name = target["container_name"]
    actual_names = {str(item.get("name")) for item in (pod_spec.get("containers") or [])}
    if container_name not in actual_names:
        return False
    included = set(spec.get("containerNameMatch") or [])
    excluded = set(spec.get("containerNameExclude") or [])
    if included and container_name not in included:
        return False
    if container_name in excluded:
        return False
    return True


def pod_workload(metadata: dict[str, Any]) -> tuple[str | None, str | None]:
    references = metadata.get("ownerReferences") or metadata.get("owner_references") or []
    if not references:
        return None, None
    owner = next((item for item in references if item.get("controller")), references[0])
    kind = owner.get("kind")
    name = owner.get("name")
    if kind == "ReplicaSet" and isinstance(name, str) and "-" in name:
        return "Deployment", name.rsplit("-", 1)[0]
    return kind, name


def safe_target_snapshot(target: dict[str, Any], value: Any, matched: list[dict[str, Any]]) -> dict[str, Any]:
    item = object_to_dict(value)
    metadata = item.get("metadata") or {}
    label_keys = _selector_keys(matched)
    labels = metadata.get("labels") or {}
    safe_labels = {key: labels[key] for key in sorted(label_keys) if key in labels}
    if target["type"] == "node":
        status = item.get("status") or {}
        node_info = status.get("node_info") or status.get("nodeInfo") or {}
        return {
            "type": "node",
            "node_name": metadata.get("name"),
            "uid": metadata.get("uid"),
            "resource_version": metadata.get("resource_version") or metadata.get("resourceVersion"),
            "creation_timestamp": metadata.get("creation_timestamp") or metadata.get("creationTimestamp"),
            "deletion_timestamp": metadata.get("deletion_timestamp") or metadata.get("deletionTimestamp"),
            "labels": safe_labels,
            "conditions": _safe_conditions(status),
            "node_info": {
                key: node_info.get(key)
                for key in (
                    "operating_system",
                    "operatingSystem",
                    "os_image",
                    "osImage",
                    "architecture",
                    "container_runtime_version",
                    "containerRuntimeVersion",
                    "kernel_version",
                    "kernelVersion",
                )
                if node_info.get(key) is not None
            },
            "matched_container_config_ids": [entry["container_config_id"] for entry in matched],
        }
    spec = item.get("spec") or {}
    status = item.get("status") or {}
    target_container = next(
        (entry for entry in spec.get("containers") or [] if entry.get("name") == target["container_name"]), {}
    )
    target_status = next(
        (
            entry
            for entry in (status.get("container_statuses") or status.get("containerStatuses") or [])
            if entry.get("name") == target["container_name"]
        ),
        {},
    )
    mounts = target_container.get("volume_mounts") or target_container.get("volumeMounts") or []
    volumes = {entry.get("name"): entry for entry in spec.get("volumes") or []}
    safe_mounts = [_safe_volume_mount(mount, volumes.get(mount.get("name")) or {}) for mount in mounts]
    return {
        "type": "pod_container",
        "namespace": metadata.get("namespace"),
        "pod_name": metadata.get("name"),
        "pod_uid": metadata.get("uid"),
        "resource_version": metadata.get("resource_version") or metadata.get("resourceVersion"),
        "creation_timestamp": metadata.get("creation_timestamp") or metadata.get("creationTimestamp"),
        "deletion_timestamp": metadata.get("deletion_timestamp") or metadata.get("deletionTimestamp"),
        "labels": safe_labels,
        "owner_references": [
            {key: reference.get(key) for key in ("kind", "name", "uid", "controller") if key in reference}
            for reference in (metadata.get("owner_references") or metadata.get("ownerReferences") or [])[:5]
        ],
        "node_name": spec.get("node_name") or spec.get("nodeName"),
        "phase": status.get("phase"),
        "start_time": status.get("start_time") or status.get("startTime"),
        "conditions": _safe_conditions(status),
        "qos_class": status.get("qos_class") or status.get("qosClass"),
        "host_ip": status.get("host_ip") or status.get("hostIP"),
        "pod_ip": status.get("pod_ip") or status.get("podIP"),
        "container": {
            "name": target_container.get("name"),
            "image": target_container.get("image"),
            "image_id": target_status.get("image_id") or target_status.get("imageID"),
            "container_id": target_status.get("container_id") or target_status.get("containerID"),
            "volume_mounts": safe_mounts,
            "ready": target_status.get("ready"),
            "restart_count": target_status.get("restart_count") or target_status.get("restartCount"),
            "state": _safe_container_state(target_status.get("state") or {}),
            "last_state": _safe_container_state(
                target_status.get("last_state") or target_status.get("lastState") or {}
            ),
        },
        "path_mappings": _path_mount_mappings(matched, safe_mounts),
        "matched_container_config_ids": [entry["container_config_id"] for entry in matched],
    }


def _selector_keys(matched: Iterable[dict[str, Any]]) -> set[str]:
    keys = {"kubernetes.io/os", "beta.kubernetes.io/os"}
    for item in matched:
        selector = (item.get("spec") or {}).get("labelSelector") or {}
        keys.update((selector.get("matchLabels") or selector.get("match_labels") or {}).keys())
        keys.update(
            expression.get("key")
            for expression in (selector.get("matchExpressions") or selector.get("match_expressions") or [])
            if expression.get("key")
        )
    return keys


def _safe_volume_mount(mount: dict[str, Any], volume: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: mount.get(key)
        for key in (
            "name",
            "mountPath",
            "mount_path",
            "subPath",
            "sub_path",
            "subPathExpr",
            "sub_path_expr",
            "readOnly",
            "read_only",
        )
        if key in mount
    }
    result["volume"] = _safe_volume_reference(volume)
    return result


def _safe_volume_reference(volume: dict[str, Any]) -> dict[str, Any]:
    for camel, snake, kind in (
        ("hostPath", "host_path", "host_path"),
        ("emptyDir", "empty_dir", "empty_dir"),
        ("persistentVolumeClaim", "persistent_volume_claim", "persistent_volume_claim"),
        ("configMap", "config_map", "config_map"),
        ("secret", "secret", "secret"),
        ("projected", "projected", "projected"),
        ("csi", "csi", "csi"),
    ):
        value = volume.get(camel) or volume.get(snake)
        if not isinstance(value, dict):
            continue
        if kind == "secret":
            return {"type": kind}
        if kind == "projected":
            sources = value.get("sources") or []
            source_types = sorted(
                {
                    key
                    for source in sources
                    if isinstance(source, dict)
                    for key in source
                    if key
                    in {
                        "configMap",
                        "config_map",
                        "secret",
                        "downwardAPI",
                        "downward_api",
                        "serviceAccountToken",
                        "service_account_token",
                    }
                }
            )
            return {"type": kind, "source_types": source_types}
        allowed = {
            "host_path": ("path", "type"),
            "empty_dir": ("medium", "sizeLimit", "size_limit"),
            "persistent_volume_claim": ("claimName", "claim_name", "readOnly", "read_only"),
            "config_map": ("name", "optional"),
            "csi": ("driver", "readOnly", "read_only"),
        }[kind]
        return {"type": kind, **{key: value.get(key) for key in allowed if value.get(key) is not None}}
    return {"type": "other"}


def _path_mount_mappings(matched: Iterable[dict[str, Any]], mounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mappings = []
    for item in matched:
        for path in (item.get("spec") or {}).get("path") or []:
            normalized = os.path.normpath(str(path))
            candidates = []
            for mount in mounts:
                mount_path = mount.get("mountPath") or mount.get("mount_path")
                if not mount_path:
                    continue
                normalized_mount = os.path.normpath(str(mount_path))
                if normalized == normalized_mount or normalized.startswith(normalized_mount.rstrip("/") + "/"):
                    candidates.append((len(normalized_mount), mount))
            selected = max(candidates, default=(0, None), key=lambda row: row[0])[1]
            mappings.append(
                {
                    "container_config_id": item.get("container_config_id"),
                    "path": path,
                    "normalized_path": normalized,
                    "within_visible_mount": selected is not None,
                    "mount": selected,
                    "scope_statement": "control-plane path visibility does not prove that the host file exists",
                }
            )
    return mappings


def _safe_container_state(value: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for state_name in ("running", "waiting", "terminated"):
        state = value.get(state_name)
        if not isinstance(state, dict):
            continue
        result[state_name] = {
            key: state.get(key)
            for key in (
                "reason",
                "exit_code",
                "exitCode",
                "signal",
                "started_at",
                "startedAt",
                "finished_at",
                "finishedAt",
            )
            if state.get(key) is not None
        }
    return result


def safe_events(items: Iterable[Any]) -> list[dict[str, Any]]:
    relevant_reasons = {
        "FailedMount",
        "FailedScheduling",
        "BackOff",
        "CrashLoopBackOff",
        "Failed",
        "FailedCreatePodSandBox",
        "FailedPullImage",
        "ErrImagePull",
        "ImagePullBackOff",
        "Unhealthy",
        "Killing",
    }
    rows = []
    for value in items:
        item = object_to_dict(value)
        reason = item.get("reason")
        event_type = item.get("type")
        if reason not in relevant_reasons and event_type != "Warning":
            continue
        rows.append(
            {
                "type": event_type,
                "reason": reason,
                "message": sanitize_sensitive_text(str(item.get("message") or ""))[:512],
                "count": item.get("count"),
                "first_timestamp": item.get("first_timestamp") or item.get("firstTimestamp"),
                "last_timestamp": item.get("last_timestamp") or item.get("lastTimestamp"),
            }
        )
    rows.sort(key=lambda row: str(row.get("last_timestamp") or row.get("first_timestamp") or ""), reverse=True)
    return rows[:20]


def discover_collector_candidates(
    daemon_sets: Iterable[Any],
    pods_by_namespace: dict[str, list[Any]],
    *,
    cluster_id: str,
    node_name: str,
    required_bk_envs: Iterable[str],
) -> tuple[list[CollectorCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[CollectorCandidate] = []
    matching_contracts: dict[tuple[str, str], dict[str, Any]] = {}
    rejected_contracts = []
    evaluated_contract_count = 0
    warnings = []
    for daemon_set_value in daemon_sets:
        daemon_set = object_to_dict(daemon_set_value)
        contract = collector_daemon_set_contract(daemon_set, required_bk_envs=required_bk_envs)
        evaluated_contract_count += 1
        if not contract["contract_matches"]:
            if len(rejected_contracts) < MAX_CONTRACT_EVIDENCE:
                rejected_contracts.append(contract)
            continue
        metadata = daemon_set.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        daemon_set_uid = str(metadata.get("uid") or "")
        matching_contracts[(namespace, daemon_set_uid)] = contract
        pod_rows = []
        for pod_value in pods_by_namespace.get(namespace, []):
            pod = object_to_dict(pod_value)
            pod_metadata = pod.get("metadata") or {}
            pod_spec = pod.get("spec") or {}
            if (pod_spec.get("node_name") or pod_spec.get("nodeName")) != node_name:
                continue
            if not _owned_by(pod_metadata, "DaemonSet", metadata.get("name"), daemon_set_uid):
                continue
            candidate = _candidate_from_pod(
                cluster_id=cluster_id,
                daemon_set=daemon_set,
                pod=pod,
                manual_installation=namespace != "kube-system",
            )
            if candidate:
                pod_rows.append((pod, candidate))
        selected, selection_warnings = _select_rolling_candidates(pod_rows, metadata.get("name"))
        candidates.extend(selected)
        warnings.extend(selection_warnings)
    candidates.sort(
        key=lambda item: (item.namespace != "kube-system", item.namespace, item.daemon_set_name, item.pod_name)
    )
    if len(candidates) > MAX_CANDIDATES:
        warnings.append(
            {
                "code": "collector_candidate_limit",
                "message": "collector candidates were capped at 20",
                "retryable": False,
            }
        )
        candidates = candidates[:MAX_CANDIDATES]
    selected_contracts = []
    seen_contracts = set()
    for candidate in candidates:
        key = (candidate.namespace, candidate.daemon_set_uid)
        if key in seen_contracts or key not in matching_contracts:
            continue
        seen_contracts.add(key)
        selected_contracts.append(matching_contracts[key])
    contracts = [*selected_contracts, *rejected_contracts[: max(0, MAX_CONTRACT_EVIDENCE - len(selected_contracts))]]
    if evaluated_contract_count > len(contracts):
        warnings.append(
            {
                "code": "collector_contract_evidence_limit",
                "message": "DaemonSet contract evidence was capped while all candidates were still evaluated",
                "retryable": False,
            }
        )
    return candidates, contracts, warnings


def collector_daemon_set_contract(daemon_set: dict[str, Any], *, required_bk_envs: Iterable[str]) -> dict[str, Any]:
    metadata = daemon_set.get("metadata") or {}
    spec = daemon_set.get("spec") or {}
    template_spec = (spec.get("template") or {}).get("spec") or {}
    containers = {item.get("name"): item for item in template_spec.get("containers") or []}
    collector = containers.get(COLLECTOR_CONTAINER_NAME) or {}
    sidecar = containers.get(SIDECAR_CONTAINER_NAME) or {}
    collector_argv = list(collector.get("command") or []) + list(collector.get("args") or [])
    sidecar_argv = list(sidecar.get("command") or []) + list(sidecar.get("args") or [])
    collector_mounts = _mount_map(collector)
    sidecar_mounts = _mount_map(sidecar)
    volumes = {item.get("name"): item for item in template_spec.get("volumes") or []}
    host_root_volume = volumes.get(sidecar_mounts.get("/var/host/")) or {}
    host_path = host_root_volume.get("host_path") or host_root_volume.get("hostPath") or {}
    required_envs = set(required_bk_envs)
    accepted_envs = {
        value.split("=", 1)[1]
        for value in sidecar_argv
        if isinstance(value, str) and value.startswith("--bk-env=") and value.split("=", 1)[1]
    }
    checks = {
        "share_process_namespace": bool(
            template_spec.get("share_process_namespace") or template_spec.get("shareProcessNamespace")
        ),
        "collector_container": bool(collector),
        "sidecar_container": bool(sidecar),
        "collector_binary": COLLECTOR_BINARY in collector_argv,
        "collector_main_config": "-c" in collector_argv and MAIN_CONFIG_PATH in collector_argv,
        "sidecar_binary": SIDECAR_BINARY in sidecar_argv,
        "sidecar_required_args": SIDECAR_REQUIRED_ARGS.issubset(set(sidecar_argv)),
        "shared_data_mount": bool(
            collector_mounts.get("/data/") and collector_mounts.get("/data/") == sidecar_mounts.get("/data/")
        ),
        "shared_child_config_mount": bool(
            collector_mounts.get("/data/etc/bkunifylogbeat")
            and collector_mounts.get("/data/etc/bkunifylogbeat") == sidecar_mounts.get("/data/etc/bkunifylogbeat")
        ),
        "host_root_mount": bool(sidecar_mounts.get("/var/host/") and host_path.get("path") == "/"),
        "bk_env_coverage": not required_envs or required_envs.issubset(accepted_envs),
    }
    return {
        "namespace": metadata.get("namespace"),
        "daemon_set_name": metadata.get("name"),
        "daemon_set_uid": metadata.get("uid"),
        "manual_installation": metadata.get("namespace") != "kube-system",
        "checks": checks,
        "contract_matches": all(checks.values()),
        "accepted_bk_envs": sorted(accepted_envs),
        "required_bk_envs": sorted(required_envs),
        "service_account_name": template_spec.get("service_account_name") or template_spec.get("serviceAccountName"),
    }


def daemon_set_selector(daemon_set: Any) -> str | None:
    value = object_to_dict(daemon_set)
    selector = (value.get("spec") or {}).get("selector") or {}
    parts = [
        f"{key}={item}"
        for key, item in sorted((selector.get("match_labels") or selector.get("matchLabels") or {}).items())
    ]
    for expression in selector.get("match_expressions") or selector.get("matchExpressions") or []:
        key = expression.get("key")
        operator = expression.get("operator")
        values = expression.get("values") or []
        if operator == "In":
            parts.append(f"{key} in ({','.join(values)})")
        elif operator == "NotIn":
            parts.append(f"{key} notin ({','.join(values)})")
        elif operator == "Exists":
            parts.append(str(key))
        elif operator == "DoesNotExist":
            parts.append(f"!{key}")
    return ",".join(parts) or None


def main_config_map_reference(daemon_set: Any) -> dict[str, str] | None:
    value = object_to_dict(daemon_set)
    template_spec = ((value.get("spec") or {}).get("template") or {}).get("spec") or {}
    containers = {item.get("name"): item for item in template_spec.get("containers") or []}
    collector = containers.get(COLLECTOR_CONTAINER_NAME) or {}
    volume_name = None
    for mount in collector.get("volume_mounts") or collector.get("volumeMounts") or []:
        path = mount.get("mount_path") or mount.get("mountPath")
        if path == "/data/etc/":
            volume_name = mount.get("name")
            break
    if not volume_name:
        return None
    for volume in template_spec.get("volumes") or []:
        if volume.get("name") != volume_name:
            continue
        config_map = volume.get("config_map") or volume.get("configMap") or {}
        if config_map.get("name"):
            return {"volume_name": volume_name, "config_map_name": config_map["name"]}
    return None


def _candidate_from_pod(
    *, cluster_id: str, daemon_set: dict[str, Any], pod: dict[str, Any], manual_installation: bool
) -> CollectorCandidate | None:
    metadata = pod.get("metadata") or {}
    spec = pod.get("spec") or {}
    status = pod.get("status") or {}
    container_statuses = status.get("container_statuses") or status.get("containerStatuses") or []
    collector_status = next((item for item in container_statuses if item.get("name") == COLLECTOR_CONTAINER_NAME), {})
    container_id = str(collector_status.get("container_id") or collector_status.get("containerID") or "")
    image_id = str(collector_status.get("image_id") or collector_status.get("imageID") or "")
    if not container_id:
        return None
    daemon_metadata = daemon_set.get("metadata") or {}
    return CollectorCandidate(
        cluster_id=cluster_id,
        namespace=str(metadata.get("namespace") or ""),
        daemon_set_name=str(daemon_metadata.get("name") or ""),
        daemon_set_uid=str(daemon_metadata.get("uid") or ""),
        pod_name=str(metadata.get("name") or ""),
        pod_uid=str(metadata.get("uid") or ""),
        node_name=str(spec.get("node_name") or spec.get("nodeName") or ""),
        collector_container_id=container_id,
        collector_image_id=image_id,
        manual_installation=manual_installation,
    )


def _select_rolling_candidates(
    rows: list[tuple[dict[str, Any], CollectorCandidate]], daemon_set_name: Any
) -> tuple[list[CollectorCandidate], list[dict[str, Any]]]:
    active_ready = []
    terminating = []
    for pod, candidate in rows:
        metadata = pod.get("metadata") or {}
        if metadata.get("deletion_timestamp") or metadata.get("deletionTimestamp"):
            terminating.append(candidate)
            continue
        statuses = (
            (pod.get("status") or {}).get("container_statuses")
            or (pod.get("status") or {}).get("containerStatuses")
            or []
        )
        collector_status = next((item for item in statuses if item.get("name") == COLLECTOR_CONTAINER_NAME), {})
        sidecar_status = next((item for item in statuses if item.get("name") == SIDECAR_CONTAINER_NAME), {})
        if collector_status.get("ready") and sidecar_status.get("ready"):
            active_ready.append(candidate)
    if len(active_ready) == 1:
        warnings = []
        if terminating:
            warnings.append(
                {
                    "code": "collector_rollout_old_pod_terminating",
                    "message": f"DaemonSet {daemon_set_name} has an old terminating Pod; the new Ready Pod was selected",
                    "retryable": False,
                }
            )
        return active_ready, warnings
    if len(active_ready) > 1:
        return active_ready, [
            {
                "code": "collector_pod_ambiguous",
                "message": f"DaemonSet {daemon_set_name} has multiple active Ready collector Pods on the target node",
                "retryable": True,
            }
        ]
    return [candidate for _pod, candidate in rows], []


def _mount_map(container: dict[str, Any]) -> dict[str, str]:
    result = {}
    for mount in container.get("volume_mounts") or container.get("volumeMounts") or []:
        path = mount.get("mount_path") or mount.get("mountPath")
        if path:
            result[str(path)] = str(mount.get("name") or "")
    return result


def _owned_by(metadata: dict[str, Any], kind: str, name: Any, uid: str) -> bool:
    refs = metadata.get("owner_references") or metadata.get("ownerReferences") or []
    return any(
        item.get("kind") == kind and item.get("name") == name and (not uid or str(item.get("uid") or "") == uid)
        for item in refs
    )


def _labels_match(labels: dict[str, Any], selector: dict[str, Any]) -> bool:
    match_labels = selector.get("matchLabels") or selector.get("match_labels") or {}
    if any(str(labels.get(key)) != str(value) for key, value in match_labels.items()):
        return False
    return _expressions_match(labels, selector.get("matchExpressions") or selector.get("match_expressions") or [])


def _expressions_match(values: dict[str, Any], expressions: Iterable[dict[str, Any]]) -> bool:
    for expression in expressions:
        key = expression.get("key")
        operator = expression.get("operator")
        accepted = expression.get("values") or expression.get("value") or []
        if isinstance(accepted, str):
            accepted = [item.strip() for item in accepted.strip("()").split(",") if item.strip()]
        present = key in values
        if operator in {LabelSelectorOperator.IN, "In"} and (not present or values.get(key) not in accepted):
            return False
        if operator in {LabelSelectorOperator.NOT_IN, "NotIn"} and present and values.get(key) in accepted:
            return False
        if operator in {LabelSelectorOperator.EXISTS, "Exists"} and not present:
            return False
        if operator in {LabelSelectorOperator.DOES_NOT_EXIST, "DoesNotExist"} and present:
            return False
    return True


def _safe_conditions(status: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            key: item.get(key)
            for key in ("type", "status", "reason", "lastTransitionTime", "last_transition_time")
            if item.get(key) is not None
        }
        for item in (status.get("conditions") or [])[:20]
        if isinstance(item, dict)
    ]
