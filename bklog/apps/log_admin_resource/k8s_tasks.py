"""Celery executor for bounded Resource Call Kubernetes inspections."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Iterable
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.log_admin_resource.handlers.inspection import sanitize_json, sanitize_sensitive_text
from apps.log_admin_resource.inspection_runtime import apply_runtime_log_filter
from apps.log_admin_resource.collector_probe_evidence import build_collector_file_log_probe, build_probe_evidence
from apps.log_admin_resource.inspection_tasks import (
    TASK_TYPE_K8S_INSPECTION,
    K8sCollectorCandidateStore,
    K8sDeepProbeSlots,
    ResourceInspectionTaskRecord,
    store_bounded_inspection_result,
)
from apps.log_admin_resource.k8s_inspection import (
    BKLOG_CONFIG_CRD_NAME,
    BKLOG_CONFIG_NAMESPACE,
    COLLECTOR_CONTAINER_NAME,
    SIDECAR_CONTAINER_NAME,
    CollectorCandidate,
    collector_child_config_hints,
    collector_daemon_set_contract,
    desired_config_evidence,
    discover_collector_candidates,
    expected_bklog_configs,
    main_config_map_reference,
    safe_events,
    safe_target_snapshot,
    target_config_matches,
    target_identity,
)
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient, bounded_text, object_to_dict
from apps.log_admin_resource.k8s_probe import FixedProbeError, run_fixed_collector_probe
from apps.log_bcs.handlers.bcs_handler import BcsHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import Space
from apps.utils.task import high_priority_task


logger = logging.getLogger(__name__)
PUBLIC_COLLECTOR_LOG_BYTES = 4 * 1024 * 1024
PUBLIC_SIDECAR_LOG_BYTES = 512 * 1024


@high_priority_task(ignore_result=True, soft_time_limit=120, time_limit=130)
def run_k8s_inspection(task_id: str) -> None:
    record = ResourceInspectionTaskRecord.get(task_id)
    if not record or record.get("task_type") != TASK_TYPE_K8S_INSPECTION:
        return
    record = ResourceInspectionTaskRecord.normalize_timeout(record)
    if not ResourceInspectionTaskRecord.is_active(record):
        ResourceInspectionTaskRecord.release_active(record)
        return
    if not ResourceInspectionTaskRecord.claim_execution(task_id):
        return

    probes: dict[str, dict[str, Any]] = {}
    deep_slot = None
    try:
        record = ResourceInspectionTaskRecord.update(
            task_id,
            task_status="running",
            phase="control_plane",
            started_at=timezone.now().isoformat(),
            error=None,
        )
        if not record:
            raise RuntimeError("inspection task metadata disappeared before execution")
        options = record.get("request_options") or {}
        collector = _load_bound_collector(record)
        container_configs = list(
            ContainerCollectorConfig.objects.filter(collector_config_id=collector.collector_config_id).order_by("id")
        )
        expected = expected_bklog_configs(collector, container_configs)
        client = K8sInspectionClient(cluster_id=collector.bcs_cluster_id)

        control_probe, target_node, required_bk_envs = _control_plane_probe(
            record=record,
            collector=collector,
            expected=expected,
            client=client,
        )
        probes["control_plane"] = control_probe
        _save_probe(task_id, "control_plane", control_probe)
        if control_probe["status"] == "failed":
            _finish(task_id, record, probes, "failed", _task_error(control_probe["code"]))
            return

        groups = set(options.get("evidence_groups") or [])
        observed_target = options.get("target")
        if not observed_target:
            _finish(task_id, record, probes, "success", None)
            return
        if not target_node:
            _finish(task_id, record, probes, "failed", _task_error("target_node_unavailable"))
            return

        ResourceInspectionTaskRecord.update(task_id, phase="collector_discovery")
        candidates, contracts, discovery_warnings = _discover_candidates(
            client=client,
            cluster_id=collector.bcs_cluster_id,
            node_name=target_node,
            required_bk_envs=required_bk_envs,
        )
        selected = _select_candidate(record, candidates)
        control_evidence = control_probe.get("evidence") or {}
        control_evidence["collector_contracts"] = contracts
        control_evidence["collector_candidates"] = _public_candidates(record, candidates)
        control_probe["warnings"].extend(discovery_warnings)
        control_probe["evidence"] = control_evidence
        if selected is None:
            if not candidates:
                code = "unsupported_collector_layout" if contracts else "collector_candidate_not_found"
                control_probe.update(
                    status="warning",
                    code=code,
                    summary="no collector DaemonSet satisfied the fixed runtime identity contract",
                )
            else:
                control_probe.update(
                    status="warning",
                    code="collector_target_narrowing_required",
                    summary="multiple collector candidates require a server-issued candidate ID",
                )
            _save_probe(task_id, "control_plane", control_probe)
            terminal_status = "success" if groups == {"control_plane"} else "partial"
            error = None if terminal_status == "success" else _task_error(control_probe["code"])
            _finish(task_id, record, probes, terminal_status, error)
            return

        daemon_set, collector_pod = _revalidate_candidate(client, selected, required_bk_envs)
        control_evidence["selected_collector"] = _candidate_public(selected)
        control_evidence["selected_collector"]["pod"] = _safe_collector_pod(collector_pod)
        try:
            control_evidence["selected_collector"]["events"] = safe_events(
                client.list_events(selected.namespace, selected.pod_uid)
            )
        except Exception:
            control_probe["warnings"].append(
                {
                    "code": "collector_events_unavailable",
                    "message": "bounded collector Pod events are unavailable",
                    "retryable": True,
                }
            )
        if len(candidates) > 1:
            control_probe["warnings"].append(
                {
                    "code": "additional_collector_candidates_present",
                    "message": "the selected collector remains one of multiple valid candidates on the target node",
                    "retryable": False,
                }
            )
        control_probe["evidence"] = control_evidence
        _save_probe(task_id, "control_plane", control_probe)

        if "sidecar" in groups:
            ResourceInspectionTaskRecord.update(task_id, phase="sidecar")
            sidecar_probe = _pod_logs_probe(
                client,
                selected,
                container_name=SIDECAR_CONTAINER_NAME,
                public_limit=PUBLIC_SIDECAR_LOG_BYTES,
                probe_code="sidecar_logs_inspected",
            )
            probes["sidecar"] = sidecar_probe
            _save_probe(task_id, "sidecar", sidecar_probe)
            reload_probe = _reload_observation_probe(sidecar_probe)
            probes["reload_observation"] = reload_probe
            _save_probe(task_id, "reload_observation", reload_probe)

        config_map_main = None
        if groups.intersection({"collector", "progress"}):
            deep_slot = K8sDeepProbeSlots.claim(selected.pod_uid, task_id)
            if not deep_slot:
                busy_probe = _probe(
                    "failed",
                    "collector_probe_concurrency_exceeded",
                    "at most two deep probes may run against one collector Pod",
                    {"maximum_concurrency": K8sDeepProbeSlots.MAX_SLOTS},
                )
                probes["collector"] = busy_probe
                _save_probe(task_id, "collector", busy_probe)
                _finish(task_id, record, probes, "partial", _task_error("collector_probe_concurrency_exceeded"))
                return

            ResourceInspectionTaskRecord.update(task_id, phase="collector")
            config_map_probe, config_map_main = _config_map_probe(client, selected, daemon_set)
            probes["desired_main_config"] = config_map_probe
            _save_probe(task_id, "desired_main_config", config_map_probe)

            collector_logs = _pod_logs_probe(
                client,
                selected,
                container_name=COLLECTOR_CONTAINER_NAME,
                public_limit=PUBLIC_COLLECTOR_LOG_BYTES,
                probe_code="collector_logs_inspected",
            )
            probes["collector_logs"] = collector_logs
            apply_runtime_log_filter(
                probes,
                options.get("runtime_log_options"),
                probe_names=("collector_logs",),
            )
            _save_probe(task_id, "collector_logs", collector_logs)

            parsed_probe = run_fixed_collector_probe(
                client,
                selected,
                bk_data_id=collector.bk_data_id,
                include_source_sample=bool(options.get("include_source_sample")),
                child_config_hints=collector_child_config_hints(control_evidence.get("target"), expected),
            )
            _daemon_after, _pod_after = _revalidate_candidate(client, selected, required_bk_envs)
            if collector_logs["status"] == "failed":
                collector_logs = _timed_probe(build_collector_file_log_probe(parsed_probe))
                probes["collector_logs"] = collector_logs
                apply_runtime_log_filter(
                    probes,
                    options.get("runtime_log_options"),
                    probe_names=("collector_logs",),
                )
                _save_probe(task_id, "collector_logs", collector_logs)
            deep_probes = build_probe_evidence(
                parsed_probe,
                bk_data_id=collector.bk_data_id,
                source=options.get("source"),
                include_source_sample=bool(options.get("include_source_sample")),
                config_map_main=config_map_main,
                expected_specs=[item["spec"] for item in expected],
            )
            if "reload_observation" in probes:
                rendered_configs = ((deep_probes.get("main_config_mounted") or {}).get("evidence") or {}).get(
                    "child_configs"
                ) or []
                probes["reload_observation"]["evidence"]["rendered_child_configs"] = [
                    {key: item.get(key) for key in ("path", "mtime_epoch", "sha256", "matching_input_count")}
                    for item in rendered_configs
                ]
                _save_probe(task_id, "reload_observation", probes["reload_observation"])
            for name, probe in deep_probes.items():
                if name == "progress" and "progress" not in groups:
                    continue
                if name != "progress" and "collector" not in groups:
                    continue
                if name == "progress":
                    ResourceInspectionTaskRecord.update(task_id, phase="progress")
                probe["probe_metadata"] = parsed_probe.get("metadata")
                probe = _timed_probe(probe)
                probes[name] = probe
                _save_probe(task_id, name, probe)

        task_status = _aggregate_status(probes)
        error = _task_error("no_usable_evidence") if task_status == "failed" else None
        _finish(task_id, record, probes, task_status, error)
    except SoftTimeLimitExceeded:
        _finish(task_id, record, probes, "timed_out", _task_error("task_timed_out"))
    except FixedProbeError as error:
        logger.warning("Resource Kubernetes fixed probe failed, task_id=%s code=%s", task_id, error.code)
        failed_probe = _probe("failed", error.code, str(error), None)
        probes["collector_probe"] = failed_probe
        _save_probe(task_id, "collector_probe", failed_probe)
        _finish(
            task_id,
            record,
            probes,
            "partial" if _has_usable_probe(probes) else "failed",
            {"code": error.code, "message": sanitize_sensitive_text(str(error)), "retryable": error.retryable},
        )
    except Exception:
        logger.exception("Resource Kubernetes inspection failed, task_id=%s", task_id)
        _finish(
            task_id,
            record,
            probes,
            "partial" if _has_usable_probe(probes) else "failed",
            _task_error("inspection_execution_failed"),
        )
    finally:
        K8sDeepProbeSlots.release(deep_slot, task_id)
        ResourceInspectionTaskRecord.release_execution(task_id)
        current = ResourceInspectionTaskRecord.get(task_id) or record
        ResourceInspectionTaskRecord.release_active(current)


def _load_bound_collector(record: dict[str, Any]) -> CollectorConfig:
    target = record.get("target") or {}
    collector = CollectorConfig.objects.get(collector_config_id=target["collector_config_id"])
    expected_binding = {
        "bk_biz_id": target.get("bk_biz_id"),
        "bk_data_id": target.get("bk_data_id"),
        "bcs_cluster_id": target.get("bcs_cluster_id"),
    }
    actual_binding = {key: getattr(collector, key, None) for key in expected_binding}
    if actual_binding != expected_binding or not collector.is_active or not collector.is_container_collector:
        raise RuntimeError("collector binding changed after inspection dispatch")

    if settings.ENABLE_MULTI_TENANT_MODE:
        tenant_id = Space.get_tenant_id(bk_biz_id=collector.bk_biz_id, is_need_default=False)
        if not tenant_id or tenant_id != record.get("bk_tenant_id"):
            raise RuntimeError("collector tenant binding changed after inspection dispatch")
    return collector


def _control_plane_probe(
    *, record: dict[str, Any], collector: CollectorConfig, expected: list[dict[str, Any]], client: K8sInspectionClient
) -> tuple[dict[str, Any], str | None, list[str]]:
    started_at = timezone.now().isoformat()
    started = time.monotonic()
    warnings = []
    cluster_info = None
    try:
        clusters = BcsHandler.list_bcs_cluster(bk_biz_id=collector.bk_biz_id)
        cluster_info = next((item for item in clusters if item.get("cluster_id") == collector.bcs_cluster_id), None)
        if not cluster_info:
            warnings.append(
                {
                    "code": "cluster_not_visible_from_business",
                    "message": "the collector cluster was not returned by the current business cluster view",
                    "retryable": True,
                }
            )
    except Exception:
        warnings.append(
            {
                "code": "cluster_metadata_unavailable",
                "message": "BCS cluster metadata is unavailable",
                "retryable": True,
            }
        )

    try:
        crd = object_to_dict(client.read_crd(BKLOG_CONFIG_CRD_NAME))
    except Exception as error:
        return (
            _probe(
                "failed",
                "bklog_config_crd_unavailable",
                "BkLogConfig CRD could not be read",
                {"error_type": error.__class__.__name__},
                started_at=started_at,
                started=started,
            ),
            None,
            [],
        )
    try:
        crs = client.list_bklog_configs(BKLOG_CONFIG_NAMESPACE)
        actual_items = crs.get("items") or []
    except Exception as error:
        return (
            _probe(
                "failed",
                "bklog_config_list_failed",
                "BkLogConfig resources could not be listed from the configured namespace",
                {"namespace": BKLOG_CONFIG_NAMESPACE, "error_type": error.__class__.__name__},
                started_at=started_at,
                started=started,
            ),
            None,
            [],
        )
    desired = desired_config_evidence(
        expected=expected, actual_items=actual_items, configured_namespace=BKLOG_CONFIG_NAMESPACE
    )
    configured_bk_env = str(getattr(settings, "CONTAINER_COLLECTOR_CR_LABEL_BKENV", "") or "").strip()
    if configured_bk_env:
        desired["required_bk_envs"] = sorted({*desired["required_bk_envs"], configured_bk_env})
    observed_target = (record.get("request_options") or {}).get("target")
    target_node = None
    target_snapshot = None
    target_events = []
    if observed_target:
        if record.get("task_id"):
            ResourceInspectionTaskRecord.update(record["task_id"], phase="target_resolution")
        try:
            if observed_target["type"] == "node":
                target_value = client.read_node(observed_target["node_name"])
                target_node = observed_target["node_name"]
                node_dict = object_to_dict(target_value)
            else:
                target_value = client.read_pod(observed_target["namespace"], observed_target["pod_name"])
                target_dict = object_to_dict(target_value)
                target_node = (target_dict.get("spec") or {}).get("node_name") or (target_dict.get("spec") or {}).get(
                    "nodeName"
                )
                node_dict = object_to_dict(client.read_node(target_node)) if target_node else {}
            node_os = str(
                ((node_dict.get("metadata") or {}).get("labels") or {}).get("kubernetes.io/os")
                or ((node_dict.get("metadata") or {}).get("labels") or {}).get("beta.kubernetes.io/os")
                or ""
            ).lower()
            if node_os == "windows":
                return (
                    _probe(
                        "failed",
                        "unsupported_os",
                        "Windows collector nodes are not supported by the fixed Linux read-only probe",
                        {"observed_object": observed_target, "node_name": target_node, "node_os": node_os},
                        started_at=started_at,
                        started=started,
                    ),
                    target_node,
                    desired["required_bk_envs"],
                )
            if not node_os:
                warnings.append(
                    {
                        "code": "node_os_unknown",
                        "message": "node OS label is unavailable; collector identity validation will remain mandatory",
                        "retryable": True,
                    }
                )
            target_dict = object_to_dict(target_value)
            matching = target_config_matches(observed_target, target_dict, expected)
            if not matching:
                return (
                    _probe(
                        "failed",
                        "target_not_in_collector_scope",
                        "the selected node or Pod container does not match the actual collector configuration",
                        {"observed_object": observed_target},
                        started_at=started_at,
                        started=started,
                    ),
                    target_node,
                    desired["required_bk_envs"],
                )
            target_snapshot = safe_target_snapshot(observed_target, target_value, matching)
            if observed_target["type"] == "pod_container":
                target_snapshot["node"] = _safe_node_runtime(node_dict)
            if observed_target["type"] == "pod_container":
                try:
                    target_events = safe_events(
                        client.list_events(observed_target["namespace"], target_snapshot["pod_uid"])
                    )
                except Exception:
                    warnings.append(
                        {
                            "code": "target_events_unavailable",
                            "message": "bounded Pod events are unavailable",
                            "retryable": True,
                        }
                    )
        except Exception as error:
            return (
                _probe(
                    "failed",
                    "target_resolution_failed",
                    "the selected node or Pod container could not be resolved without substitution",
                    {"observed_object": observed_target, "error_type": error.__class__.__name__},
                    started_at=started_at,
                    started=started,
                ),
                None,
                desired["required_bk_envs"],
            )

    crd_spec = crd.get("spec") or {}
    crd_status = crd.get("status") or {}
    evidence = {
        "collector": {
            "collector_config_id": collector.collector_config_id,
            "bk_biz_id": collector.bk_biz_id,
            "bk_data_id": collector.bk_data_id,
            "bcs_cluster_id": collector.bcs_cluster_id,
            "collector_config_name": collector.collector_config_name,
            "is_active": collector.is_active,
            "container_config_ids": [item["container_config_id"] for item in expected],
        },
        "cluster": cluster_info,
        "crd": {
            "name": (crd.get("metadata") or {}).get("name"),
            "resource_version": (crd.get("metadata") or {}).get("resource_version")
            or (crd.get("metadata") or {}).get("resourceVersion"),
            "versions": [
                {key: item.get(key) for key in ("name", "served", "storage")} for item in crd_spec.get("versions") or []
            ],
            "conditions": [
                {
                    key: condition.get(key)
                    for key in ("type", "status", "reason", "lastTransitionTime", "last_transition_time")
                    if condition.get(key) is not None
                }
                for condition in (crd_status.get("conditions") or [])[:20]
                if isinstance(condition, dict)
            ],
        },
        "desired_config": desired,
        "target": target_snapshot,
        "target_events": target_events,
    }
    status = "success" if desired["all_present"] and desired["all_exact_match"] else "warning"
    code = "control_plane_resolved" if status == "success" else "desired_config_drift"
    probe = _probe(
        status,
        code,
        "collector control-plane, desired configuration and selected target were inspected",
        evidence,
        started_at=started_at,
        started=started,
    )
    probe["warnings"] = warnings
    return probe, target_node, desired["required_bk_envs"]


def _discover_candidates(
    *, client: K8sInspectionClient, cluster_id: str, node_name: str, required_bk_envs: Iterable[str]
) -> tuple[list[CollectorCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
    warnings = []
    daemon_sets = client.list_daemon_sets("kube-system")
    try:
        all_daemon_sets = client.list_daemon_sets()
    except Exception:
        all_daemon_sets = []
        warnings.append(
            {
                "code": "manual_installation_discovery_unavailable",
                "message": "cluster-wide DaemonSet listing is unavailable; kube-system discovery was retained",
                "retryable": True,
            }
        )
    by_uid = {}
    for value in [*daemon_sets, *all_daemon_sets]:
        item = object_to_dict(value)
        metadata = item.get("metadata") or {}
        key = metadata.get("uid") or f"{metadata.get('namespace')}/{metadata.get('name')}"
        by_uid[str(key)] = value
    pods_by_namespace: dict[str, list[Any]] = {}
    candidate_namespaces = set()
    for value in by_uid.values():
        contract = collector_daemon_set_contract(object_to_dict(value), required_bk_envs=required_bk_envs)
        if contract["contract_matches"] and contract.get("namespace"):
            candidate_namespaces.add(str(contract["namespace"]))
    for namespace in sorted(candidate_namespaces):
        try:
            pods_by_namespace[namespace] = client.list_pods(namespace)
        except Exception:
            pods_by_namespace[namespace] = []
            warnings.append(
                {
                    "code": "collector_pod_list_failed",
                    "message": f"collector Pods could not be listed in namespace {namespace}",
                    "retryable": True,
                }
            )
    candidates, contracts, selection_warnings = discover_collector_candidates(
        by_uid.values(),
        pods_by_namespace,
        cluster_id=cluster_id,
        node_name=node_name,
        required_bk_envs=required_bk_envs,
    )
    warnings.extend(selection_warnings)
    return candidates, contracts, warnings


def _select_candidate(record: dict[str, Any], candidates: list[CollectorCandidate]) -> CollectorCandidate | None:
    candidate_id = (record.get("request_options") or {}).get("collector_candidate_id")
    if not candidate_id:
        return candidates[0] if len(candidates) == 1 else None
    binding = K8sCollectorCandidateStore.get(candidate_id)
    if not binding:
        raise FixedProbeError("collector_candidate_expired_or_unknown", "collector candidate binding expired")
    expected_context = {
        "app_code": record.get("app_code"),
        "bk_tenant_id": record.get("bk_tenant_id"),
        "collector_config_id": (record.get("target") or {}).get("collector_config_id"),
        "cluster_id": (record.get("target") or {}).get("bcs_cluster_id"),
        "target_identity": target_identity((record.get("request_options") or {}).get("target")),
    }
    if any(binding.get(key) != value for key, value in expected_context.items()):
        raise FixedProbeError(
            "collector_candidate_binding_mismatch",
            "collector candidate is not bound to this Resource request",
            retryable=False,
        )
    selected_fields = CollectorCandidate.__dataclass_fields__
    selected_values = {key: binding.get(key) for key in selected_fields}
    try:
        selected = CollectorCandidate(**selected_values)
    except TypeError as error:
        raise FixedProbeError(
            "collector_candidate_invalid", "collector candidate binding is invalid", retryable=False
        ) from error
    if selected not in candidates:
        same_pod_name = next(
            (
                item
                for item in candidates
                if item.namespace == selected.namespace and item.pod_name == selected.pod_name
            ),
            None,
        )
        if same_pod_name and same_pod_name.pod_uid != selected.pod_uid:
            code = "collector_candidate_pod_uid_changed"
        elif same_pod_name and same_pod_name.collector_container_id != selected.collector_container_id:
            code = "collector_candidate_container_changed"
        else:
            code = "collector_candidate_disappeared"
        raise FixedProbeError(code, "collector candidate changed after it was issued")
    return selected


def _public_candidates(record: dict[str, Any], candidates: list[CollectorCandidate]) -> list[dict[str, Any]]:
    options = record.get("request_options") or {}
    results = []
    for candidate in candidates:
        binding = {
            "app_code": record["app_code"],
            "bk_tenant_id": record["bk_tenant_id"],
            "collector_config_id": (record.get("target") or {}).get("collector_config_id"),
            "cluster_id": candidate.cluster_id,
            "target_identity": target_identity(options.get("target")),
            **candidate.binding(),
        }
        candidate_id = K8sCollectorCandidateStore.create(binding)
        results.append({"collector_candidate_id": candidate_id, **_candidate_public(candidate)})
    return results


def _candidate_public(candidate: CollectorCandidate) -> dict[str, Any]:
    return {
        "namespace": candidate.namespace,
        "daemon_set_name": candidate.daemon_set_name,
        "daemon_set_uid": candidate.daemon_set_uid,
        "pod_name": candidate.pod_name,
        "pod_uid": candidate.pod_uid,
        "node_name": candidate.node_name,
        "collector_image_id": candidate.collector_image_id,
        "manual_installation": candidate.manual_installation,
    }


def _revalidate_candidate(
    client: K8sInspectionClient, candidate: CollectorCandidate, required_bk_envs: Iterable[str]
) -> tuple[Any, Any]:
    daemon_set = client.read_daemon_set(candidate.namespace, candidate.daemon_set_name)
    daemon_set_dict = object_to_dict(daemon_set)
    daemon_metadata = daemon_set_dict.get("metadata") or {}
    if str(daemon_metadata.get("uid") or "") != candidate.daemon_set_uid:
        raise FixedProbeError("collector_candidate_daemonset_uid_changed", "collector DaemonSet UID changed")
    contract = collector_daemon_set_contract(daemon_set_dict, required_bk_envs=required_bk_envs)
    if not contract["contract_matches"]:
        raise FixedProbeError(
            "collector_candidate_contract_changed", "collector DaemonSet no longer matches the fixed contract"
        )

    pod = client.read_pod(candidate.namespace, candidate.pod_name)
    pod_dict = object_to_dict(pod)
    metadata = pod_dict.get("metadata") or {}
    spec = pod_dict.get("spec") or {}
    status = pod_dict.get("status") or {}
    if str(metadata.get("uid") or "") != candidate.pod_uid:
        raise FixedProbeError("collector_candidate_pod_uid_changed", "collector Pod UID changed")
    if metadata.get("deletion_timestamp") or metadata.get("deletionTimestamp"):
        raise FixedProbeError("collector_candidate_pod_terminating", "collector Pod is terminating")
    if str(spec.get("node_name") or spec.get("nodeName") or "") != candidate.node_name:
        raise FixedProbeError("collector_candidate_node_changed", "collector Pod moved away from the target node")
    refs = metadata.get("owner_references") or metadata.get("ownerReferences") or []
    if not any(
        ref.get("kind") == "DaemonSet"
        and ref.get("name") == candidate.daemon_set_name
        and str(ref.get("uid") or "") == candidate.daemon_set_uid
        for ref in refs
    ):
        raise FixedProbeError("collector_candidate_owner_changed", "collector Pod owner identity changed")
    statuses = status.get("container_statuses") or status.get("containerStatuses") or []
    collector_status = next((item for item in statuses if item.get("name") == COLLECTOR_CONTAINER_NAME), {})
    current_container_id = str(collector_status.get("container_id") or collector_status.get("containerID") or "")
    if current_container_id != candidate.collector_container_id:
        raise FixedProbeError("collector_candidate_container_changed", "collector container identity changed")
    container_names = {item.get("name") for item in spec.get("containers") or []}
    if {COLLECTOR_CONTAINER_NAME, SIDECAR_CONTAINER_NAME} - container_names:
        raise FixedProbeError("collector_candidate_container_missing", "required collector containers are missing")
    return daemon_set, pod


def _safe_collector_pod(value: Any) -> dict[str, Any]:
    pod = object_to_dict(value)
    metadata = pod.get("metadata") or {}
    spec = pod.get("spec") or {}
    status = pod.get("status") or {}
    statuses = {
        item.get("name"): {
            "ready": item.get("ready"),
            "restart_count": item.get("restart_count") or item.get("restartCount"),
            "image": item.get("image"),
            "image_id": item.get("image_id") or item.get("imageID"),
            "container_id": item.get("container_id") or item.get("containerID"),
            "state": item.get("state"),
            "last_state": item.get("last_state") or item.get("lastState"),
        }
        for item in status.get("container_statuses") or status.get("containerStatuses") or []
        if item.get("name") in {COLLECTOR_CONTAINER_NAME, SIDECAR_CONTAINER_NAME}
    }
    resources = {
        item.get("name"): item.get("resources") or {}
        for item in spec.get("containers") or []
        if item.get("name") in {COLLECTOR_CONTAINER_NAME, SIDECAR_CONTAINER_NAME}
    }
    return {
        "namespace": metadata.get("namespace"),
        "name": metadata.get("name"),
        "uid": metadata.get("uid"),
        "resource_version": metadata.get("resource_version") or metadata.get("resourceVersion"),
        "creation_timestamp": metadata.get("creation_timestamp") or metadata.get("creationTimestamp"),
        "deletion_timestamp": metadata.get("deletion_timestamp") or metadata.get("deletionTimestamp"),
        "node_name": spec.get("node_name") or spec.get("nodeName"),
        "phase": status.get("phase"),
        "start_time": status.get("start_time") or status.get("startTime"),
        "conditions": [
            {
                key: condition.get(key)
                for key in ("type", "status", "reason", "lastTransitionTime", "last_transition_time")
                if condition.get(key) is not None
            }
            for condition in (status.get("conditions") or [])[:20]
        ],
        "qos_class": status.get("qos_class") or status.get("qosClass"),
        "host_ip": status.get("host_ip") or status.get("hostIP"),
        "pod_ip": status.get("pod_ip") or status.get("podIP"),
        "container_statuses": statuses,
        "container_resources": resources,
    }


def _safe_node_runtime(value: dict[str, Any]) -> dict[str, Any]:
    metadata = value.get("metadata") or {}
    status = value.get("status") or {}
    labels = metadata.get("labels") or {}
    node_info = status.get("node_info") or status.get("nodeInfo") or {}
    return {
        "name": metadata.get("name"),
        "uid": metadata.get("uid"),
        "operating_system": labels.get("kubernetes.io/os")
        or labels.get("beta.kubernetes.io/os")
        or node_info.get("operating_system")
        or node_info.get("operatingSystem"),
        "architecture": labels.get("kubernetes.io/arch")
        or labels.get("beta.kubernetes.io/arch")
        or node_info.get("architecture"),
        "container_runtime_version": node_info.get("container_runtime_version")
        or node_info.get("containerRuntimeVersion"),
        "kernel_version": node_info.get("kernel_version") or node_info.get("kernelVersion"),
        "os_image": node_info.get("os_image") or node_info.get("osImage"),
    }


def _config_map_probe(
    client: K8sInspectionClient, candidate: CollectorCandidate, daemon_set: Any
) -> tuple[dict[str, Any], str | None]:
    started_at = timezone.now().isoformat()
    started = time.monotonic()
    reference = main_config_map_reference(daemon_set)
    if not reference:
        return (
            _probe(
                "failed",
                "main_config_map_reference_missing",
                "collector DaemonSet does not mount a discoverable main ConfigMap",
                None,
                started_at=started_at,
                started=started,
            ),
            None,
        )
    try:
        value = object_to_dict(client.read_config_map(candidate.namespace, reference["config_map_name"]))
    except Exception as error:
        return (
            _probe(
                "failed",
                "main_config_map_unavailable",
                "collector main ConfigMap could not be read from the DaemonSet namespace",
                {**reference, "error_type": error.__class__.__name__},
                started_at=started_at,
                started=started,
            ),
            None,
        )
    data = value.get("data") or {}
    main_key = (
        "bkunifylogbeat.conf"
        if "bkunifylogbeat.conf" in data
        else next((key for key in sorted(data) if key.endswith("bkunifylogbeat.conf")), None)
    )
    main_content = str(data.get(main_key)) if main_key else None
    evidence = {
        **reference,
        "namespace": candidate.namespace,
        "name": (value.get("metadata") or {}).get("name"),
        "uid": (value.get("metadata") or {}).get("uid"),
        "resource_version": (value.get("metadata") or {}).get("resource_version")
        or (value.get("metadata") or {}).get("resourceVersion"),
        "creation_timestamp": (value.get("metadata") or {}).get("creation_timestamp")
        or (value.get("metadata") or {}).get("creationTimestamp"),
        "deletion_timestamp": (value.get("metadata") or {}).get("deletion_timestamp")
        or (value.get("metadata") or {}).get("deletionTimestamp"),
        "keys": sorted(data),
        "data_sha256": {
            key: hashlib.sha256(str(data[key]).encode("utf-8", errors="replace")).hexdigest() for key in sorted(data)
        },
        "main_key": main_key,
    }
    status = "success" if main_key else "warning"
    return (
        _probe(
            status,
            "main_config_map_resolved" if main_key else "main_config_key_missing",
            "main ConfigMap was derived from the selected DaemonSet Pod template",
            evidence,
            started_at=started_at,
            started=started,
        ),
        main_content,
    )


def _pod_logs_probe(
    client: K8sInspectionClient,
    candidate: CollectorCandidate,
    *,
    container_name: str,
    public_limit: int,
    probe_code: str,
) -> dict[str, Any]:
    if container_name not in {COLLECTOR_CONTAINER_NAME, SIDECAR_CONTAINER_NAME}:
        raise FixedProbeError(
            "collector_container_not_allowed", "only fixed collector containers may be read", retryable=False
        )
    started_at = timezone.now().isoformat()
    started = time.monotonic()
    files = []
    warnings = []
    remaining = public_limit
    current_succeeded = False
    for previous in (False, True):
        try:
            evidence = client.read_pod_log(
                candidate.namespace,
                candidate.pod_name,
                container_name,
                previous=previous,
            )
            current_succeeded = current_succeeded or not previous
            for item in evidence.get("files") or []:
                scanned_size = item.get("returned_size_bytes")
                content, truncated = bounded_text(item.pop("content", ""), max(0, remaining))
                size = len(content.encode("utf-8", errors="replace"))
                remaining -= size
                files.append(
                    {
                        **item,
                        "content": content,
                        "scanned_size_bytes": scanned_size,
                        "returned_size_bytes": size,
                        "truncated": bool(item.get("truncated") or truncated),
                    }
                )
        except Exception as error:
            warnings.append(
                {
                    "code": "previous_pod_log_unavailable" if previous else "current_pod_log_unavailable",
                    "message": f"{'previous' if previous else 'current'} {container_name} pods/log is unavailable: {error.__class__.__name__}",
                    "retryable": not previous,
                }
            )
    status = "success" if current_succeeded else "failed"
    return _probe(
        status,
        probe_code if status == "success" else "current_pod_log_unavailable",
        f"bounded current and previous logs were requested for fixed container {container_name}",
        {
            "files": files,
            "returned_size_bytes": public_limit - remaining,
            "public_return_limit_bytes": public_limit,
            "per_request_limit_bytes": 5 * 1024 * 1024,
            "truncated": remaining == 0 or any(item.get("truncated") for item in files),
        },
        warnings=warnings,
        started_at=started_at,
        started=started,
    )


def _reload_observation_probe(sidecar_probe: dict[str, Any]) -> dict[str, Any]:
    """Keep desired state separate from sidecar-observed reload evidence."""

    markers = ("reload", "reloaded", "config updated", "config changed", "sync config", "render config")
    files = (sidecar_probe.get("evidence") or {}).get("files") or []
    matches = []
    for item in files:
        path = item.get("path")
        for line in str(item.get("content") or "").splitlines():
            normalized = line.lower()
            if any(marker in normalized for marker in markers):
                action = next(
                    (
                        value
                        for value in ("delete", "create", "update", "render", "reload", "sync")
                        if value in normalized
                    ),
                    "config_change",
                )
                outcome = (
                    "failed"
                    if any(value in normalized for value in ("fail", "error"))
                    else "succeeded"
                    if any(value in normalized for value in ("success", "succeed", "complete", "completed"))
                    else "observed"
                )
                matches.append({"path": path, "action": action, "outcome": outcome, "line": line[:1024]})
                if len(matches) >= 50:
                    break
        if len(matches) >= 50:
            break
    if sidecar_probe.get("status") == "failed":
        status = "failed"
        code = "reload_observation_unavailable"
        summary = "sidecar logs were unavailable, so config reload could not be observed"
    elif matches:
        status = "success"
        code = "reload_event_observed"
        summary = "bounded sidecar logs contain config reload evidence"
    else:
        status = "warning"
        code = "reload_event_not_observed"
        summary = "no config reload marker was observed in the bounded sidecar log window"
    return _probe(
        status,
        code,
        summary,
        {
            "matches": matches,
            "maximum_matches": 50,
            "scope_statement": "absence in the bounded log window does not prove that reload never occurred",
        },
        warnings=list(sidecar_probe.get("warnings") or []),
    )


def _save_probe(task_id: str, name: str, probe: dict[str, Any]) -> None:
    if not ResourceInspectionTaskRecord.set_probe(task_id, name, probe):
        raise RuntimeError("inspection task metadata disappeared while saving probe summaries")


def _probe(
    status: str,
    code: str,
    summary: str,
    evidence: Any,
    *,
    warnings: list[dict[str, Any]] | None = None,
    started_at: str | None = None,
    started: float | None = None,
) -> dict[str, Any]:
    started_at = started_at or timezone.now().isoformat()
    duration_ms = round((time.monotonic() - started) * 1000, 2) if started is not None else 0
    return {
        "status": status,
        "code": code,
        "summary": summary,
        "evidence": sanitize_json(evidence, redact_text=True),
        "warnings": warnings or [],
        "started_at": started_at,
        "finished_at": timezone.now().isoformat(),
        "duration_ms": duration_ms,
    }


def _timed_probe(value: dict[str, Any]) -> dict[str, Any]:
    value = dict(value)
    value.setdefault("warnings", [])
    value.setdefault("started_at", timezone.now().isoformat())
    value.setdefault("finished_at", timezone.now().isoformat())
    value.setdefault("duration_ms", 0)
    value["evidence"] = sanitize_json(value.get("evidence"), redact_text=True)
    return value


def _aggregate_status(probes: dict[str, dict[str, Any]]) -> str:
    statuses = [probe.get("status") for probe in probes.values() if isinstance(probe, dict)]
    if not any(status in {"success", "warning"} for status in statuses):
        return "failed"
    if any(status == "failed" for status in statuses):
        return "partial"
    return "success"


def _has_usable_probe(probes: dict[str, dict[str, Any]]) -> bool:
    return any(probe.get("status") in {"success", "warning"} for probe in probes.values())


def _finish(
    task_id: str,
    record: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    task_status: str,
    error: dict[str, Any] | None,
) -> None:
    current = ResourceInspectionTaskRecord.get(task_id) or record
    if ResourceInspectionTaskRecord.is_deadline_exceeded(current):
        task_status = "timed_out"
        error = _task_error("task_timed_out")
    partial = task_status == "partial" or (task_status == "timed_out" and _has_usable_probe(probes))
    result = {
        "problem_env": getattr(settings, "ENVIRONMENT", ""),
        "source_env": getattr(settings, "ENVIRONMENT", ""),
        "observed_at": timezone.now().isoformat(),
        "target": sanitize_json(current.get("target") or {}, redact_text=True),
        "remote_execution": {
            "executor": "K8S_API",
            "mode": "server_fixed_read_only_probe",
            "mutations_permitted": False,
        },
        "probes": sanitize_json(probes, redact_text=True),
        "partial": partial,
        "error": error,
    }
    response_compacted = _store_bounded_result(task_id, result)
    if response_compacted and task_status == "success":
        task_status = "partial"
        error = _task_error("response_compacted")
    finished_at = timezone.now().isoformat()
    ResourceInspectionTaskRecord.update(
        task_id,
        task_status=task_status,
        phase="completed" if task_status in {"success", "partial"} else task_status,
        finished_at=finished_at,
        error=error,
    )


def _store_bounded_result(task_id: str, result: dict[str, Any]) -> bool:
    return store_bounded_inspection_result(
        task_id,
        result,
        compaction_probe=_probe(
            "warning",
            "response_compacted",
            "oversized string and list evidence was compacted to preserve a valid final response",
            {"maximum_response_bytes": ResourceInspectionTaskRecord.MAX_RESULT_BYTES},
        ),
        compaction_error=_task_error("response_compacted"),
    )


def _task_error(code: str) -> dict[str, Any]:
    messages = {
        "task_timed_out": "Kubernetes inspection task exceeded its 120 second deadline",
        "target_node_unavailable": "the selected target did not resolve to one collector node",
        "collector_candidate_not_found": "no collector candidate satisfied the fixed runtime identity contract",
        "unsupported_collector_layout": "collector DaemonSets do not satisfy the fixed runtime identity contract",
        "collector_target_narrowing_required": "multiple collector candidates require explicit narrowing",
        "collector_probe_concurrency_exceeded": "the collector Pod already has two active deep probes",
        "no_usable_evidence": "inspection completed without usable evidence",
        "inspection_execution_failed": "inspection execution failed after preserving completed probes",
        "bklog_config_crd_unavailable": "BkLogConfig CRD is unavailable",
        "bklog_config_list_failed": "BkLogConfig resources are unavailable",
        "target_not_in_collector_scope": "the selected target is outside the collector configuration scope",
        "target_resolution_failed": "the selected target could not be resolved",
        "unsupported_os": "Windows collector nodes are not supported",
        "response_compacted": "oversized evidence was compacted to preserve the final response",
    }
    return {
        "code": code,
        "message": sanitize_sensitive_text(messages.get(code, code)),
        "retryable": code not in {"target_not_in_collector_scope", "unsupported_os"},
    }
