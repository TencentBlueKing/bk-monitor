import json
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.k8s_inspection import (
    DETAIL_FUNC_NAME,
    DETAIL_RESPONSE_SCHEMA,
    FUNCTIONS,
    START_FUNC_NAME,
    START_RESPONSE_SCHEMA,
    TARGET_LIST_FUNC_NAME,
    TARGET_LIST_RESPONSE_SCHEMA,
    _collect_bounded_pages,
    _validate_candidate_binding,
    get_k8s_inspection_detail,
    list_k8s_inspection_targets,
    start_k8s_inspection,
)
from apps.log_admin_resource.inspection_tasks import (
    TASK_TYPE_HOST_INSPECTION,
    TASK_TYPE_K8S_INSPECTION,
    K8sCollectorCandidateStore,
    K8sDeepProbeSlots,
    InspectionConcurrencyExceeded,
    ResourceInspectionTaskRecord,
)
from apps.log_admin_resource.k8s_inspection import (
    COLLECTOR_CONTAINER_NAME,
    SIDECAR_CONTAINER_NAME,
    CollectorCandidate,
    collector_child_config_hints,
    collector_daemon_set_contract,
    desired_config_evidence,
    discover_collector_candidates,
    discover_inspection_targets,
    main_config_map_reference,
    safe_events,
    safe_target_snapshot,
    target_config_matches,
    target_identity,
)
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient, bounded_text
from apps.log_admin_resource.collector_probe import (
    MAX_PROBE_OUTPUT_BYTES,
    PROBE_PROTOCOL,
    PROBE_SCRIPT_PATH,
    PROBE_VERSION,
    parse_and_validate_probe_output,
    parse_probe_output,
)
from apps.log_admin_resource.k8s_probe import (
    FixedProbeError,
    run_fixed_collector_probe,
)
from apps.log_admin_resource.collector_probe_evidence import build_collector_file_log_probe, build_probe_evidence
from apps.log_admin_resource.k8s_tasks import (
    _control_plane_probe,
    _load_bound_collector,
    _pod_logs_probe,
    _reload_observation_probe,
    _revalidate_candidate,
    _store_bounded_result,
    run_k8s_inspection,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_databus.constants import ContainerCollectorType, Environment


TEST_CACHES = {
    alias: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "resource-k8s-inspection-tests",
    }
    for alias in ("default", "redis")
}


def task_cache():
    return caches["redis"]


def collector(**overrides):
    values = {
        "collector_config_id": 123,
        "collector_config_name": "demo",
        "collector_config_name_en": "demo_log",
        "bk_biz_id": 2,
        "bk_data_id": 1001,
        "bcs_cluster_id": "BCS-K8S-1",
        "data_link_id": None,
        "extra_labels": [],
        "add_pod_label": False,
        "add_pod_annotation": False,
        "yaml_config_enabled": False,
        "is_active": True,
        "is_container_collector": True,
        "environment": Environment.CONTAINER,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def container_config(**overrides):
    values = {
        "id": 44,
        "collector_config_id": 123,
        "collector_type": ContainerCollectorType.CONTAINER,
        "raw_config": None,
        "params": {"paths": ["/var/host/data/*.log"]},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def probe(status="success", code="ok", evidence=None):
    now = timezone.now().isoformat()
    return {
        "status": status,
        "code": code,
        "summary": code,
        "evidence": evidence,
        "warnings": [],
        "started_at": now,
        "finished_at": now,
        "duration_ms": 1,
    }


def daemon_set(name="bk-log-collector", uid="ds-uid", namespace="kube-system"):
    return {
        "metadata": {"name": name, "namespace": namespace, "uid": uid},
        "spec": {
            "selector": {"matchLabels": {"name": "bkunifylogbeat-bklog"}},
            "template": {
                "spec": {
                    "shareProcessNamespace": True,
                    "serviceAccountName": "bk-log-collector",
                    "containers": [
                        {
                            "name": COLLECTOR_CONTAINER_NAME,
                            "command": ["/bin/bkunifylogbeat"],
                            "args": ["-c", "/data/etc/bkunifylogbeat.conf"],
                            "volumeMounts": [
                                {"name": "data", "mountPath": "/data/"},
                                {"name": "main", "mountPath": "/data/etc/"},
                                {"name": "child", "mountPath": "/data/etc/bkunifylogbeat"},
                            ],
                        },
                        {
                            "name": SIDECAR_CONTAINER_NAME,
                            "command": ["/bk-log-sidecar"],
                            "args": [
                                "--bkunifylogbeat-config=/data/etc/bkunifylogbeat",
                                "--bkunifylogbeat-pid-file=/data/run/bkunifylogbeat.pid",
                                "--host-path=/var/host/",
                                "--bk-env=bkte",
                            ],
                            "volumeMounts": [
                                {"name": "data", "mountPath": "/data/"},
                                {"name": "child", "mountPath": "/data/etc/bkunifylogbeat"},
                                {"name": "host", "mountPath": "/var/host/"},
                            ],
                        },
                    ],
                    "volumes": [
                        {"name": "main", "configMap": {"name": "bk-log-bkunifylogbeat"}},
                        {"name": "data", "emptyDir": {}},
                        {"name": "child", "emptyDir": {}},
                        {"name": "host", "hostPath": {"path": "/"}},
                    ],
                }
            },
        },
    }


def collector_pod(
    name="collector-node-a",
    uid="pod-uid",
    ds_uid="ds-uid",
    node="node-a",
    container_id="containerd://abc",
    deleting=False,
    ready=True,
):
    metadata = {
        "name": name,
        "namespace": "kube-system",
        "uid": uid,
        "ownerReferences": [{"kind": "DaemonSet", "name": "bk-log-collector", "uid": ds_uid, "controller": True}],
    }
    if deleting:
        metadata["deletionTimestamp"] = "2026-01-01T00:00:00Z"
    return {
        "metadata": metadata,
        "spec": {
            "nodeName": node,
            "containers": [{"name": COLLECTOR_CONTAINER_NAME}, {"name": SIDECAR_CONTAINER_NAME}],
        },
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {
                    "name": COLLECTOR_CONTAINER_NAME,
                    "ready": ready,
                    "containerID": container_id,
                    "imageID": "sha256:image",
                },
                {"name": SIDECAR_CONTAINER_NAME, "ready": ready, "containerID": "containerd://sidecar"},
            ],
        },
    }


def business_pod(namespace="production", name="demo-abc", container_name="app", node="node-a"):
    return {
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": f"uid-{name}",
            "labels": {"app": "demo", "private": "never-return"},
            "ownerReferences": [{"kind": "ReplicaSet", "name": "demo-7d8f", "controller": True}],
        },
        "spec": {
            "nodeName": node,
            "containers": [
                {
                    "name": container_name,
                    "env": [{"name": "SECRET", "value": "never-return"}],
                }
            ],
        },
        "status": {
            "phase": "Running",
            "containerStatuses": [{"name": container_name, "ready": True}],
        },
    }


def business_target_expected():
    return [
        {
            "container_config_id": 44,
            "spec": {
                "logConfigType": ContainerCollectorType.CONTAINER,
                "namespaceSelector": {"matchNames": ["production"], "excludeNames": []},
                "workloadType": "Deployment",
                "workloadName": "demo",
                "containerNameMatch": ["app"],
                "containerNameExclude": [],
                "labelSelector": {"matchLabels": {"app": "demo"}},
                "annotationSelector": {"matchExpressions": []},
            },
        }
    ]


def candidate(**overrides):
    values = {
        "cluster_id": "BCS-K8S-1",
        "namespace": "kube-system",
        "daemon_set_name": "bk-log-collector",
        "daemon_set_uid": "ds-uid",
        "pod_name": "collector-node-a",
        "pod_uid": "pod-uid",
        "node_name": "node-a",
        "collector_container_id": "containerd://abc",
        "collector_image_id": "sha256:image",
        "manual_installation": False,
    }
    values.update(overrides)
    return CollectorCandidate(**values)


def valid_probe_output() -> str:
    return "\n".join(
        [
            f"BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}",
            f"BKLOG_KV\tprobe_version\t{PROBE_VERSION}",
            "BKLOG_KV\tmanifest_kv_count\t2",
            "BKLOG_KV\tmanifest_stream_count\t0",
            f"BKLOG_KV\toutput_budget_bytes\t{MAX_PROBE_OUTPUT_BYTES}",
            "BKLOG_KV\toutput_budget_exhausted\tfalse",
            "BKLOG_KV\tcompleted\ttrue",
        ]
    )


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class SharedInspectionTaskTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    def test_task_type_deadline_and_full_request_fingerprint_are_independent(self):
        target = {"collector_config_id": 1, "bk_host_id": 2}
        host, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="app",
            bk_tenant_id="tenant-a",
            target=target,
            request_options={},
            task_type=TASK_TYPE_HOST_INSPECTION,
        )
        k8s, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="app",
            bk_tenant_id="tenant-a",
            target=target,
            request_options={},
            task_type=TASK_TYPE_K8S_INSPECTION,
        )
        changed, reused = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="app",
            bk_tenant_id="tenant-a",
            target=target,
            request_options={"runtime_log_options": {"keywords": ["error"]}},
            task_type=TASK_TYPE_HOST_INSPECTION,
        )

        self.assertEqual(host["deadline_seconds"], 90)
        self.assertEqual(k8s["deadline_seconds"], 120)
        self.assertNotEqual(host["request_fingerprint"], k8s["request_fingerprint"])
        self.assertFalse(reused)
        self.assertNotEqual(host["task_id"], changed["task_id"])
        active_key = ResourceInspectionTaskRecord._active_key(
            task_type=changed["task_type"], fingerprint=changed["request_fingerprint"]
        )
        self.assertEqual(task_cache().get(active_key), changed["task_id"])
        self.assertNotIn("error", active_key)

    def test_candidate_binding_and_deep_slots_are_short_lived_and_bounded(self):
        candidate_id = K8sCollectorCandidateStore.create({"pod_uid": "pod-uid"})
        self.assertEqual(K8sCollectorCandidateStore.get(candidate_id)["pod_uid"], "pod-uid")

        first = K8sDeepProbeSlots.claim("pod-uid", "task-1")
        second = K8sDeepProbeSlots.claim("pod-uid", "task-2")
        third = K8sDeepProbeSlots.claim("pod-uid", "task-3")

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertIsNone(third)
        self.assertGreaterEqual(K8sDeepProbeSlots.TTL_SECONDS, 120)
        K8sDeepProbeSlots.release(first, "task-1")
        self.assertTrue(K8sDeepProbeSlots.claim("pod-uid", "task-3"))

    def test_owner_concurrency_limit_cannot_be_bypassed_with_request_variants(self):
        records = []
        for index in range(ResourceInspectionTaskRecord.MAX_ACTIVE_TASKS_PER_OWNER):
            record, reused = ResourceInspectionTaskRecord.create_or_reuse(
                app_code="reader-a",
                bk_tenant_id="tenant-a",
                target={"collector_config_id": index + 1},
                request_options={"runtime_log_options": {"keywords": [f"error-{index}"]}},
                task_type=TASK_TYPE_HOST_INSPECTION,
            )
            self.assertFalse(reused)
            records.append(record)

        with self.assertRaises(InspectionConcurrencyExceeded):
            ResourceInspectionTaskRecord.create_or_reuse(
                app_code="reader-a",
                bk_tenant_id="tenant-a",
                target={"collector_config_id": 999},
                request_options={"runtime_log_options": {"keywords": ["different"]}},
                task_type=TASK_TYPE_HOST_INSPECTION,
            )

        ResourceInspectionTaskRecord.release_active(records[0])
        replacement, reused = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 999},
            request_options={"runtime_log_options": {"keywords": ["different"]}},
            task_type=TASK_TYPE_HOST_INSPECTION,
        )
        self.assertFalse(reused)
        self.assertTrue(replacement["owner_slot_key"])


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class K8sInspectionHandlerTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch("apps.log_admin_resource.handlers.k8s_inspection.Space.get_tenant_id", return_value=None)
    def test_collector_without_tenant_mapping_fails_closed(self, _tenant):
        from apps.log_admin_resource.handlers.k8s_inspection import _validate_collector

        with self.assertRaisesRegex(BklogPermissionError, "tenant is not configured"):
            _validate_collector(collector(), "tenant-a")

    @patch("apps.log_admin_resource.k8s_tasks.run_k8s_inspection.apply_async")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_control_plane_only_is_always_async_without_target(self, _identity, _get, _validate, apply_async):
        result = start_k8s_inspection({"collector_config_id": 123, "evidence_groups": ["control_plane"]})

        validate_params(result, START_RESPONSE_SCHEMA, "response")
        apply_async.assert_called_once()
        record = ResourceInspectionTaskRecord.get(result["task_id"])
        self.assertEqual(record["task_type"], TASK_TYPE_K8S_INSPECTION)
        self.assertEqual(record["deadline_seconds"], 120)

    @patch("apps.log_admin_resource.k8s_tasks.run_k8s_inspection.apply_async")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_omitted_groups_defaults_to_control_plane(self, _identity, _get, _validate, apply_async):
        result = start_k8s_inspection({"collector_config_id": 123})

        record = ResourceInspectionTaskRecord.get(result["task_id"])
        self.assertEqual(record["request_options"]["evidence_groups"], ["control_plane"])
        apply_async.assert_called_once()

    @patch("apps.log_admin_resource.handlers.k8s_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_deep_evidence_requires_business_target(self, _identity, _get, _validate):
        with self.assertRaisesRegex(ValidationError, "target is required"):
            start_k8s_inspection({"collector_config_id": 123, "evidence_groups": ["collector"]})

    @patch("apps.log_admin_resource.handlers.k8s_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_source_sample_requires_explicit_source(self, _identity, _get, _validate):
        with self.assertRaisesRegex(ValidationError, "explicit source"):
            start_k8s_inspection(
                {
                    "collector_config_id": 123,
                    "target": {"type": "node", "node_name": "node-a"},
                    "include_source_sample": True,
                }
            )

    def test_schema_rejects_caller_supplied_collector_or_command_fields(self):
        schema = FUNCTIONS[START_FUNC_NAME]["params_schema"]
        for key, value in (
            ("collector_namespace", "kube-system"),
            ("collector_pod_name", "collector-a"),
            ("command", ["id"]),
            ("script", "cat /etc/passwd"),
        ):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_params(
                    {
                        "collector_config_id": 123,
                        "target": {"type": "node", "node_name": "node-a"},
                        key: value,
                    },
                    schema,
                )

    def test_target_discovery_supports_namespace_filter_and_all_namespaces(self):
        configs = MagicMock()
        configs.order_by.return_value = [container_config()]
        client = MagicMock()
        client.list_pod_page.side_effect = [([business_pod()], None), ([business_pod()], None)]
        with (
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._request_identity",
                return_value=("reader-a", "tenant-a"),
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._get_collector",
                return_value=collector(),
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._validate_collector",
                return_value="tenant-a",
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.ContainerCollectorConfig.objects.filter",
                return_value=configs,
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.expected_bklog_configs",
                return_value=business_target_expected(),
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.K8sInspectionClient",
                return_value=client,
            ),
        ):
            scoped = list_k8s_inspection_targets({"collector_config_id": 123, "namespace": "production", "limit": 10})
            cluster_wide = list_k8s_inspection_targets({"collector_config_id": 123, "limit": 10})

        validate_params(scoped, TARGET_LIST_RESPONSE_SCHEMA, "response")
        validate_params(cluster_wide, TARGET_LIST_RESPONSE_SCHEMA, "response")
        self.assertEqual(
            client.list_pod_page.call_args_list,
            [
                call("production", limit=500, continue_token=None),
                call(None, limit=500, continue_token=None),
            ],
        )
        client.list_node_page.assert_not_called()
        self.assertEqual(
            scoped["pod_targets"][0]["target"],
            {
                "type": "pod_container",
                "namespace": "production",
                "pod_name": "demo-abc",
                "container_name": "app",
            },
        )
        self.assertEqual(cluster_wide["namespace"], None)
        self.assertNotIn("never-return", json.dumps(scoped))

    def test_target_discovery_lists_matching_nodes_without_pod_scan(self):
        configs = MagicMock()
        configs.order_by.return_value = [container_config(collector_type=ContainerCollectorType.NODE)]
        client = MagicMock()
        client.list_node_page.return_value = (
            [
                {
                    "metadata": {"name": "node-a", "uid": "node-uid", "labels": {"role": "log"}},
                    "status": {"conditions": [{"type": "Ready", "status": "True"}]},
                }
            ],
            None,
        )
        expected = [
            {
                "container_config_id": 45,
                "spec": {
                    "logConfigType": ContainerCollectorType.NODE,
                    "labelSelector": {"matchLabels": {"role": "log"}},
                },
            }
        ]
        with (
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._request_identity",
                return_value=("reader-a", "tenant-a"),
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._get_collector",
                return_value=collector(),
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection._validate_collector",
                return_value="tenant-a",
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.ContainerCollectorConfig.objects.filter",
                return_value=configs,
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.expected_bklog_configs",
                return_value=expected,
            ),
            patch(
                "apps.log_admin_resource.handlers.k8s_inspection.K8sInspectionClient",
                return_value=client,
            ),
        ):
            result = list_k8s_inspection_targets({"collector_config_id": 123})

        validate_params(result, TARGET_LIST_RESPONSE_SCHEMA, "response")
        client.list_pod_page.assert_not_called()
        self.assertEqual(result["node_targets"][0]["target"], {"type": "node", "node_name": "node-a"})
        self.assertTrue(result["node_targets"][0]["ready"])

    def test_target_discovery_schema_is_bounded_and_rejects_extra_fields(self):
        schema = FUNCTIONS[TARGET_LIST_FUNC_NAME]["params_schema"]
        validate_params({"collector_config_id": 123}, schema)
        validate_params({"collector_config_id": 123, "namespace": "production", "limit": 100}, schema)
        for params in (
            {"collector_config_id": 123, "limit": 101},
            {"collector_config_id": 123, "command": ["kubectl", "get", "pods"]},
        ):
            with self.subTest(params=params), self.assertRaises(ValidationError):
                validate_params(params, schema)

    @patch(
        "apps.log_admin_resource.handlers.k8s_inspection._request_identity",
        return_value=("reader-a", "tenant-a"),
    )
    @patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.k8s_inspection._validate_collector", return_value="tenant-a")
    def test_target_discovery_rejects_blank_namespace_instead_of_scanning_cluster(
        self, _validate_collector, _get_collector, _identity
    ):
        with self.assertRaisesRegex(ValidationError, "namespace must not be blank"):
            list_k8s_inspection_targets({"collector_config_id": 123, "namespace": "   "})

    def test_target_discovery_scan_is_paginated_and_hard_bounded(self):
        fetch_page = MagicMock()
        fetch_page.side_effect = [([index] * 500, f"token-{index}") for index in range(10)]

        items, truncated = _collect_bounded_pages(fetch_page)

        self.assertEqual(len(items), 5000)
        self.assertTrue(truncated)
        self.assertEqual(fetch_page.call_count, 10)

        oversized_page = MagicMock(return_value=(list(range(6000)), None))
        items, truncated = _collect_bounded_pages(oversized_page)
        self.assertEqual(len(items), 5000)
        self.assertTrue(truncated)

    def test_candidate_binding_cannot_cross_app_target_or_collector(self):
        binding = {
            "app_code": "reader-a",
            "bk_tenant_id": "tenant-a",
            "collector_config_id": 123,
            "cluster_id": "BCS-K8S-1",
            "target_identity": target_identity({"type": "node", "node_name": "node-a"}),
            **candidate().binding(),
        }
        candidate_id = K8sCollectorCandidateStore.create(binding)

        _validate_candidate_binding(
            candidate_id=candidate_id,
            app_code="reader-a",
            tenant_id="tenant-a",
            collector=collector(),
            target={"type": "node", "node_name": "node-a"},
        )
        with self.assertRaisesRegex(ValidationError, "expired_or_unknown"):
            _validate_candidate_binding(
                candidate_id=candidate_id,
                app_code="reader-b",
                tenant_id="tenant-a",
                collector=collector(),
                target={"type": "node", "node_name": "node-a"},
            )

    @patch("apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-b", "tenant-a"))
    def test_detail_hides_cross_app_task_existence(self, _identity):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 123},
            request_options={},
            task_type=TASK_TYPE_K8S_INSPECTION,
        )
        result = get_k8s_inspection_detail({"task_id": record["task_id"]})
        validate_params(result, DETAIL_RESPONSE_SCHEMA, "response")
        self.assertEqual(result["task_status"], "not_found")
        self.assertIsNone(result["target"])

    def test_registry_exposes_k8s_start_and_detail(self):
        metadata = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="reader-a")
        self.assertIn(TARGET_LIST_FUNC_NAME, metadata["functions"])
        self.assertIn(START_FUNC_NAME, metadata["functions"])
        self.assertIn(DETAIL_FUNC_NAME, metadata["functions"])


class K8sInspectionDomainTest(SimpleTestCase):
    def test_official_and_older_collector_contract_does_not_require_container_flag(self):
        result = collector_daemon_set_contract(daemon_set(), required_bk_envs=["bkte"])

        self.assertTrue(result["contract_matches"])
        self.assertNotIn("-container", daemon_set()["spec"]["template"]["spec"]["containers"][0]["args"])

    def test_lookalike_daemonset_without_shared_pid_namespace_is_rejected(self):
        value = daemon_set()
        value["spec"]["template"]["spec"]["shareProcessNamespace"] = False

        result = collector_daemon_set_contract(value, required_bk_envs=[])

        self.assertFalse(result["contract_matches"])
        self.assertFalse(result["checks"]["share_process_namespace"])

    def test_required_bk_env_must_be_accepted_by_sidecar(self):
        result = collector_daemon_set_contract(daemon_set(), required_bk_envs=["bkop"])
        self.assertFalse(result["checks"]["bk_env_coverage"])

    def test_host_root_mount_must_be_backed_by_root_host_path(self):
        value = daemon_set()
        value["spec"]["template"]["spec"]["volumes"][-1] = {"name": "host", "emptyDir": {}}

        result = collector_daemon_set_contract(value, required_bk_envs=["bkte"])

        self.assertFalse(result["checks"]["host_root_mount"])
        self.assertFalse(result["contract_matches"])

    def test_desired_config_reports_exact_hash_and_safe_diff_without_secret_values(self):
        expected = [
            {
                "name": "demo-2-44",
                "container_config_id": 44,
                "spec": {
                    "dataId": 1001,
                    "path": ["/data/*.log"],
                    "extOptions": {"output.kafka": {"password": "secret"}},
                },
                "safe_spec": {"dataId": 1001, "path": ["/data/*.log"]},
            }
        ]
        actual = {
            "metadata": {"name": "demo-2-44", "labels": {"bk_env": "bkte"}},
            "spec": {
                "dataId": 1001,
                "path": ["/data/changed.log"],
                "extOptions": {"output.kafka": {"password": "secret"}},
            },
        }

        result = desired_config_evidence(expected=expected, actual_items=[actual], configured_namespace="default")

        self.assertFalse(result["all_exact_match"])
        self.assertIn("$.path[0]", result["items"][0]["different_paths"])
        self.assertNotIn("password", json.dumps(result["items"][0]["safe_expected_spec"]))
        self.assertEqual(result["required_bk_envs"], ["bkte"])

    def test_business_pod_target_matches_actual_config_without_exposing_env(self):
        target = {
            "type": "pod_container",
            "namespace": "production",
            "pod_name": "demo-abc",
            "container_name": "app",
        }
        pod = {
            "metadata": {
                "name": "demo-abc",
                "namespace": "production",
                "uid": "business-pod",
                "resourceVersion": "10",
                "creationTimestamp": "2026-01-01T00:00:00Z",
                "labels": {"app": "demo"},
                "ownerReferences": [{"kind": "ReplicaSet", "name": "demo-7d8f", "controller": True}],
            },
            "spec": {
                "nodeName": "node-a",
                "containers": [
                    {
                        "name": "app",
                        "image": "demo:v1",
                        "env": [{"name": "SECRET", "value": "never-return"}],
                        "volumeMounts": [
                            {"name": "logs", "mountPath": "/data", "readOnly": False},
                            {"name": "secret", "mountPath": "/var/run/secret", "readOnly": True},
                        ],
                    }
                ],
                "volumes": [
                    {"name": "logs", "persistentVolumeClaim": {"claimName": "business-logs"}},
                    {"name": "secret", "secret": {"secretName": "never-return-secret-name"}},
                ],
            },
            "status": {
                "phase": "Running",
                "startTime": "2026-01-01T00:00:01Z",
                "qosClass": "Burstable",
                "hostIP": "host-ip",
                "podIP": "pod-ip",
                "conditions": [{"type": "Ready", "status": "True", "message": "not returned"}],
                "containerStatuses": [
                    {
                        "name": "app",
                        "ready": True,
                        "imageID": "sha256:image",
                        "containerID": "containerd://business",
                        "state": {"running": {"startedAt": "2026-01-01T00:00:02Z"}},
                    }
                ],
            },
        }
        expected = [
            {
                "container_config_id": 44,
                "spec": {
                    "dataId": 1001,
                    "path": ["/data/app.log"],
                    "logConfigType": ContainerCollectorType.CONTAINER,
                    "namespaceSelector": {"matchNames": ["production"], "excludeNames": []},
                    "workloadType": "Deployment",
                    "workloadName": "demo",
                    "containerNameMatch": ["app"],
                    "containerNameExclude": [],
                    "labelSelector": {"matchLabels": {"app": "demo"}},
                    "annotationSelector": {"matchExpressions": []},
                },
            }
        ]

        matched = target_config_matches(target, pod, expected)
        snapshot = safe_target_snapshot(target, pod, matched)

        self.assertEqual([item["container_config_id"] for item in matched], [44])
        self.assertNotIn("env", json.dumps(snapshot))
        self.assertNotIn("never-return", json.dumps(snapshot))
        self.assertEqual(snapshot["node_name"], "node-a")
        self.assertEqual(snapshot["creation_timestamp"], "2026-01-01T00:00:00Z")
        self.assertEqual(snapshot["start_time"], "2026-01-01T00:00:01Z")
        self.assertTrue(snapshot["path_mappings"][0]["within_visible_mount"])
        self.assertEqual(snapshot["container"]["volume_mounts"][1]["volume"], {"type": "secret"})
        self.assertNotIn("never-return-secret-name", json.dumps(snapshot))

    def test_events_only_return_bounded_diagnostic_reasons(self):
        events = [
            {"type": "Normal", "reason": "Pulled", "message": "ok"},
            {"type": "Warning", "reason": "FailedMount", "message": "mount failed"},
        ]

        result = safe_events(events)

        self.assertEqual([item["reason"] for item in result], ["FailedMount"])

    def test_node_target_requires_node_collector_type_and_label_scope(self):
        target = {"type": "node", "node_name": "node-a"}
        node = {"metadata": {"name": "node-a", "labels": {"role": "log"}}, "status": {}}
        expected = [
            {
                "container_config_id": 44,
                "spec": {
                    "logConfigType": ContainerCollectorType.NODE,
                    "labelSelector": {"matchLabels": {"role": "log"}},
                },
            }
        ]

        self.assertEqual(target_config_matches(target, node, expected), expected)

    def test_target_discovery_returns_only_matched_safe_targets_and_applies_limit(self):
        expected = [
            *business_target_expected(),
            {
                "container_config_id": 45,
                "spec": {
                    "logConfigType": ContainerCollectorType.NODE,
                    "labelSelector": {"matchLabels": {"role": "log"}},
                },
            },
        ]
        pods = [
            business_pod(name="demo-b"),
            business_pod(name="demo-a"),
            business_pod(namespace="other", name="ignored"),
        ]
        nodes = [
            {
                "metadata": {"name": "node-a", "uid": "node-a-uid", "labels": {"role": "log"}},
                "status": {"conditions": [{"type": "Ready", "status": "True", "message": "never-return"}]},
            },
            {"metadata": {"name": "node-b", "labels": {"role": "other"}}, "status": {}},
        ]

        result = discover_inspection_targets(pods=pods, nodes=nodes, expected=expected, limit=1)

        self.assertEqual(result["pod_target_count"], 2)
        self.assertEqual(result["node_target_count"], 1)
        self.assertTrue(result["pod_targets_truncated"])
        self.assertFalse(result["node_targets_truncated"])
        self.assertEqual(result["pod_targets"][0]["target"]["pod_name"], "demo-a")
        self.assertEqual(result["node_targets"][0]["target"], {"type": "node", "node_name": "node-a"})
        self.assertNotIn("never-return", json.dumps(result))

    def test_rolling_update_selects_new_ready_pod_and_keeps_warning(self):
        old = collector_pod(name="collector-old", uid="old", deleting=True)
        new = collector_pod(name="collector-new", uid="new")
        candidates, _contracts, warnings = discover_collector_candidates(
            [daemon_set()],
            {"kube-system": [old, new]},
            cluster_id="BCS-K8S-1",
            node_name="node-a",
            required_bk_envs=["bkte"],
        )

        self.assertEqual([item.pod_name for item in candidates], ["collector-new"])
        self.assertIn("collector_rollout_old_pod_terminating", {item["code"] for item in warnings})

    def test_multiple_active_ready_pods_are_ambiguous(self):
        first = collector_pod(name="collector-a", uid="a")
        second = collector_pod(name="collector-b", uid="b")
        candidates, _contracts, warnings = discover_collector_candidates(
            [daemon_set()],
            {"kube-system": [first, second]},
            cluster_id="BCS-K8S-1",
            node_name="node-a",
            required_bk_envs=["bkte"],
        )

        self.assertEqual(len(candidates), 2)
        self.assertIn("collector_pod_ambiguous", {item["code"] for item in warnings})

    def test_candidate_discovery_supports_containerd_and_docker_container_ids(self):
        containerd = collector_pod(name="collector-containerd", uid="containerd", container_id="containerd://abc")
        docker = collector_pod(name="collector-docker", uid="docker", container_id="docker://def")

        candidates, _contracts, _warnings = discover_collector_candidates(
            [daemon_set()],
            {"kube-system": [containerd, docker]},
            cluster_id="BCS-K8S-1",
            node_name="node-a",
            required_bk_envs=["bkte"],
        )

        self.assertEqual({item.collector_container_id for item in candidates}, {"containerd://abc", "docker://def"})

    def test_candidate_discovery_is_capped_at_twenty(self):
        daemon_sets = []
        pods = []
        for index in range(21):
            name = f"collector-{index}"
            uid = f"ds-{index}"
            ds = daemon_set(name=name, uid=uid)
            pod = collector_pod(name=f"pod-{index}", uid=f"pod-{index}", ds_uid=uid)
            pod["metadata"]["ownerReferences"][0]["name"] = name
            daemon_sets.append(ds)
            pods.append(pod)

        candidates, contracts, warnings = discover_collector_candidates(
            daemon_sets,
            {"kube-system": pods},
            cluster_id="BCS-K8S-1",
            node_name="node-a",
            required_bk_envs=["bkte"],
        )

        self.assertEqual(len(candidates), 20)
        self.assertLessEqual(len(contracts), 100)
        self.assertIn("collector_candidate_limit", {item["code"] for item in warnings})
        self.assertIn("collector_contract_evidence_limit", {item["code"] for item in warnings})

    def test_main_configmap_is_derived_from_daemonset_mount_not_fixed_name(self):
        value = daemon_set()
        value["spec"]["template"]["spec"]["volumes"][0]["configMap"]["name"] = "custom-main"
        self.assertEqual(main_config_map_reference(value), {"volume_name": "main", "config_map_name": "custom-main"})


class K8sInspectionClientTest(SimpleTestCase):
    @patch("apps.log_admin_resource.k8s_inspection_client.Bcs")
    def test_pod_listing_supports_namespace_and_all_namespaces_and_nodes(self, bcs_class):
        response = SimpleNamespace(
            items=[{"metadata": {"name": "one"}}],
            metadata=SimpleNamespace(_continue="next-token"),
            to_dict=lambda: {"items": [], "metadata": {}},
        )
        bcs = bcs_class.return_value
        bcs.api_instance_core_v1.list_namespaced_pod.return_value = response
        bcs.api_instance_core_v1.list_pod_for_all_namespaces.return_value = response
        bcs.api_instance_core_v1.list_node.return_value = response
        client = K8sInspectionClient("BCS-K8S-1")

        self.assertEqual(len(client.list_pods("production")), 1)
        self.assertEqual(len(client.list_pods()), 1)
        self.assertEqual(len(client.list_nodes()), 1)
        self.assertEqual(client.list_pod_page("production", limit=50), (response.items, "next-token"))
        self.assertEqual(client.list_pod_page(limit=50, continue_token="next-token"), (response.items, "next-token"))
        self.assertEqual(client.list_node_page(limit=50), (response.items, "next-token"))
        bcs.api_instance_core_v1.list_namespaced_pod.assert_has_calls(
            [
                call(namespace="production", _request_timeout=10),
                call(namespace="production", limit=50, _request_timeout=10),
            ]
        )
        bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_has_calls(
            [
                call(_request_timeout=10),
                call(limit=50, _request_timeout=10, _continue="next-token"),
            ]
        )
        bcs.api_instance_core_v1.list_node.assert_has_calls(
            [call(_request_timeout=10), call(limit=50, _request_timeout=10)]
        )


class FixedK8sProbeTest(SimpleTestCase):
    def test_script_accepts_only_typed_server_arguments_and_performs_no_file_writes(self):
        script = PROBE_SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("accepts only server-controlled typed arguments", script)
        self.assertIn('[ "$#" -ne 3 ]', script)
        self.assertIn("TARGET_DATA_ID=$1", script)
        self.assertIn("INCLUDE_SOURCE_SAMPLE=$2", script)
        self.assertIn("TARGET_CONFIG_HINTS=$3", script)
        self.assertNotIn("$@", script)
        self.assertNotIn("/tmp", script)
        self.assertNotIn("mktemp", script)
        self.assertNotIn("kubectl", script)
        self.assertNotIn("eval ", script)
        self.assertNotIn(' > "', script)
        self.assertNotIn('[ ! -L "$source_path" ]', script)

    def test_line_protocol_parser_reconstructs_bounded_streams(self):
        parsed = parse_probe_output(
            "\n".join(
                [
                    "BKLOG_KV\tprotocol\tbklog.collector.inspection.probe.v1",
                    "BKLOG_STREAM\tmain_config\t/data/etc/bkunifylogbeat.conf\t10\t10\tfalse",
                    "BKLOG_LINE\tmain_config\tpath.data: /data/lib/",
                    "BKLOG_END_STREAM\tmain_config",
                ]
            )
        )

        self.assertEqual(parsed["values"]["protocol"], "bklog.collector.inspection.probe.v1")
        self.assertEqual(parsed["streams"]["main_config"]["content"], "path.data: /data/lib/")

    def test_base64_protocol_preserves_exact_stream_bytes(self):
        parsed = parse_probe_output(
            "\n".join(
                [
                    "BKLOG_STREAM\tmain_config\t/data/etc/bkunifylogbeat.conf\t17\t17\tfalse\t24",
                    "BKLOG_B64\tmain_config\tcGF0aC5kYXRhOiAvZGF0YS8K",
                    "BKLOG_END_STREAM\tmain_config",
                ]
            )
        )

        self.assertEqual(parsed["streams"]["main_config"]["content"], "path.data: /data/\n")

    def test_bounded_text_never_reopens_an_exhausted_or_multibyte_budget(self):
        self.assertEqual(bounded_text("previous", 0), ("", True))
        content, truncated = bounded_text("你a", 2)
        self.assertTrue(truncated)
        self.assertLessEqual(len(content.encode("utf-8")), 2)

    @patch("apps.log_admin_resource.k8s_probe.stream")
    def test_exec_transport_is_fixed_to_validated_collector_container_and_shell(self, mock_stream):
        response = MagicMock()
        response.is_open.side_effect = [True, False, False, False]
        response.peek_stdout.return_value = True
        response.read_stdout.return_value = valid_probe_output()
        response.peek_stderr.return_value = False
        response.returncode = 0
        mock_stream.return_value = response
        client = SimpleNamespace(
            bcs=SimpleNamespace(api_instance_core_v1=SimpleNamespace(connect_get_namespaced_pod_exec=object()))
        )

        result = run_fixed_collector_probe(
            client,
            candidate(),
            bk_data_id=1001,
            include_source_sample=False,
            child_config_hints=["node_log_config_default_demo-node.conf"],
        )

        kwargs = mock_stream.call_args.kwargs
        self.assertEqual(kwargs["container"], COLLECTOR_CONTAINER_NAME)
        self.assertEqual(
            kwargs["command"],
            ["/bin/sh", "-s", "--", "1001", "0", "node_log_config_default_demo-node.conf"],
        )
        self.assertEqual(kwargs["name"], "collector-node-a")
        self.assertEqual(result["values"]["protocol"], "bklog.collector.inspection.probe.v1")
        self.assertEqual(result["metadata"]["child_config_hint_count"], 1)

    def test_sidecar_config_hints_are_exact_for_node_and_pod_targets(self):
        expected = [
            {"name": "demo-node", "container_config_id": 44, "collector_type": ContainerCollectorType.NODE},
            {
                "name": "demo-container",
                "container_config_id": 45,
                "collector_type": ContainerCollectorType.CONTAINER,
            },
        ]

        node_hints = collector_child_config_hints({"type": "node", "matched_container_config_ids": [44]}, expected)
        pod_hints = collector_child_config_hints(
            {
                "type": "pod_container",
                "matched_container_config_ids": [45],
                "container": {"container_id": "containerd://abc123"},
            },
            expected,
        )

        self.assertEqual(node_hints, ["node_log_config_default_demo-node.conf"])
        self.assertEqual(pod_hints, ["abc123_container_log_config_default_demo-container.conf"])

    @patch("apps.log_admin_resource.k8s_probe.stream")
    def test_exec_rejects_protocol_header_without_completion_marker(self, mock_stream):
        response = MagicMock()
        response.is_open.side_effect = [True, False, False, False]
        response.peek_stdout.return_value = True
        response.read_stdout.return_value = (
            f"BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}\nBKLOG_KV\tprobe_version\t{PROBE_VERSION}\n"
        )
        response.peek_stderr.return_value = False
        response.returncode = 0
        mock_stream.return_value = response
        client = SimpleNamespace(
            bcs=SimpleNamespace(api_instance_core_v1=SimpleNamespace(connect_get_namespaced_pod_exec=object()))
        )

        with self.assertRaisesRegex(FixedProbeError, "completion marker"):
            run_fixed_collector_probe(client, candidate(), bk_data_id=1001, include_source_sample=False)

    @patch("apps.log_admin_resource.k8s_probe.stream")
    def test_exec_reports_missing_shell_as_dependency_degradation(self, mock_stream):
        response = MagicMock()
        response.is_open.side_effect = [True, False, False, False]
        response.peek_stdout.return_value = True
        response.read_stdout.return_value = (
            f"BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}\nBKLOG_KV\tprobe_version\t{PROBE_VERSION}\n"
        )
        response.peek_stderr.return_value = True
        response.read_stderr.return_value = "/bin/sh: not found"
        response.returncode = 127
        mock_stream.return_value = response
        client = SimpleNamespace(
            bcs=SimpleNamespace(api_instance_core_v1=SimpleNamespace(connect_get_namespaced_pod_exec=object()))
        )

        with self.assertRaisesRegex(FixedProbeError, "probe dependency") as context:
            run_fixed_collector_probe(client, candidate(), bk_data_id=1001, include_source_sample=False)
        self.assertEqual(context.exception.code, "probe_dependency_missing")

    def test_fixed_script_static_raw_budget_stays_below_transport_limit(self):
        script = PROBE_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("MAX_CHILD_CONFIG_BYTES=65536", script)
        self.assertIn("MAX_REGISTRAR_BYTES=524288", script)
        self.assertIn(f"OUTPUT_BUDGET_BYTES={MAX_PROBE_OUTPUT_BYTES}", script)
        self.assertIn("BKLOG_B64", script)

    def test_probe_manifest_rejects_a_whole_stream_removed_from_the_middle(self):
        output = valid_probe_output().replace(
            "BKLOG_KV\tmanifest_stream_count\t0", "BKLOG_KV\tmanifest_stream_count\t1"
        )

        with self.assertRaisesRegex(FixedProbeError, "stream manifest"):
            parse_and_validate_probe_output(output)

    def test_probe_manifest_rejects_truncated_base64_stream(self):
        output = "\n".join(
            [
                f"BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}",
                f"BKLOG_KV\tprobe_version\t{PROBE_VERSION}",
                "BKLOG_STREAM\tmain_config\t/data/etc/bkunifylogbeat.conf\t3\t3\tfalse\t4",
                "BKLOG_B64\tmain_config\tYW",
                "BKLOG_END_STREAM\tmain_config",
                "BKLOG_KV\tmanifest_kv_count\t2",
                "BKLOG_KV\tmanifest_stream_count\t1",
                f"BKLOG_KV\toutput_budget_bytes\t{MAX_PROBE_OUTPUT_BYTES}",
                "BKLOG_KV\toutput_budget_exhausted\tfalse",
                "BKLOG_KV\tcompleted\ttrue",
            ]
        )

        with self.assertRaises(FixedProbeError):
            parse_and_validate_probe_output(output)

    def test_probe_rejects_output_above_the_transport_safe_budget(self):
        output = valid_probe_output() + ("x" * MAX_PROBE_OUTPUT_BYTES)

        with self.assertRaisesRegex(FixedProbeError, "4 MiB"):
            parse_and_validate_probe_output(output)

    def test_probe_accepts_the_exact_transport_safe_budget_boundary(self):
        valid = valid_probe_output()
        filler = "x" * (MAX_PROBE_OUTPUT_BYTES - len(valid.encode("utf-8")) - 1)
        output = f"{filler}\n{valid}"

        parsed = parse_and_validate_probe_output(output)

        self.assertEqual(parsed["returned_size_bytes"], MAX_PROBE_OUTPUT_BYTES)

    def test_probe_evidence_filters_rendered_config_by_data_id_and_explicit_source(self):
        config = """local:
  - dataid: 1001
    paths:
      - /var/host/data/*.log
  - dataid: 2002
    paths:
      - /var/host/other/*.log
"""
        registrar = '{"source":"/var/host/data/app.log","offset":10,"FileStateOS":{"inode":7,"device":8}}'
        parsed = {
            "values": {
                "protocol": "bklog.collector.inspection.probe.v1",
                "main_config_path": "/data/etc/bkunifylogbeat.conf",
                "first.source_count": "1",
                "first.source.0.pattern": "/var/host/data/*.log",
                "first.source.0.path": "/var/host/data/app.log",
                "first.source.0.device": "8",
                "first.source.0.inode": "7",
                "first.source.0.size_bytes": "20",
                "second.source_count": "1",
                "second.source.0.pattern": "/var/host/data/*.log",
                "second.source.0.path": "/var/host/data/app.log",
                "second.source.0.device": "8",
                "second.source.0.inode": "7",
                "second.source.0.size_bytes": "30",
                "first.collector.process_pid": "1",
                "first.collector.start_ticks": "10",
                "first.collector.cpu_ticks": "10",
                "first.collector.rss_pages": "2",
                "second.collector.process_pid": "1",
                "second.collector.start_ticks": "10",
                "second.collector.cpu_ticks": "20",
                "second.collector.rss_pages": "3",
                "page_size": "4096",
                "observation_seconds": "5",
                "observation_required_seconds": "4",
                "registrar_path": "/data/lib/bkunifylogbeat.bkpipe.db",
                "child_config.0.mtime_epoch": "100",
                "first.sidecar.process_pid": "2",
                "first.sidecar.start_ticks": "20",
                "first.sidecar.cpu_ticks": "5",
                "first.sidecar.rss_pages": "1",
                "first.sidecar.threads": "4",
                "first.sidecar.fd_count": "5",
                "first.sidecar.fd_soft_limit": "1024",
                "first.sidecar.fd_hard_limit": "4096",
                "first.sidecar.fd_deleted": "1",
                "second.sidecar.process_pid": "2",
                "second.sidecar.start_ticks": "20",
                "second.sidecar.cpu_ticks": "7",
                "second.sidecar.rss_pages": "1",
                "second.sidecar.threads": "5",
                "second.sidecar.fd_count": "6",
                "second.sidecar.fd_soft_limit": "1024",
                "second.sidecar.fd_hard_limit": "4096",
                "second.sidecar.fd_deleted": "1",
                "second.sidecar.cgroup.memory.current": "4096",
            },
            "streams": {
                "main_config": {"content": "path.data: /data/lib\n", "path": "/data/etc/bkunifylogbeat.conf"},
                "child_config.0": {"content": config, "path": "/data/etc/bkunifylogbeat/a.conf"},
                "first.registrar_strings": {"content": registrar},
                "second.registrar_strings": {"content": registrar.replace("10", "20")},
                "second.source.0.sample": {"content": "one\ntwo"},
                "first.collector.cgroup": {"content": "0::/collector"},
                "second.collector.cgroup": {"content": "0::/collector"},
                "first.sidecar.cgroup": {"content": "0::/sidecar"},
                "second.sidecar.cgroup": {"content": "0::/sidecar"},
            },
        }

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source="/var/host/data/app.log",
            include_source_sample=True,
            config_map_main="path.data: /data/lib\n",
            expected_specs=[{"path": ["/var/host/data/*.log"]}],
        )

        config_evidence = probes["main_config_mounted"]["evidence"]
        self.assertEqual(config_evidence["matching_patterns"], ["/var/host/data/*.log"])
        self.assertTrue(config_evidence["render_comparison"]["equivalent"])
        self.assertEqual(config_evidence["child_configs"][0]["mtime_epoch"], 100)
        self.assertNotIn("/var/host/other", json.dumps(config_evidence))
        self.assertEqual(probes["source_path"]["evidence"]["files"][0]["sample"]["lines"], ["one", "two"])
        self.assertEqual(probes["progress"]["evidence"]["items"][0]["status"], "progress_advancing")
        self.assertEqual(probes["sidecar_process"]["code"], "sidecar_process_sampled")
        self.assertEqual(probes["sidecar_process"]["evidence"]["cgroup"]["first"]["membership"], "0::/sidecar")
        self.assertEqual(
            probes["sidecar_process"]["evidence"]["cgroup"]["second"]["metrics"]["memory.current"],
            "4096",
        )
        self.assertEqual(probes["sidecar_process"]["evidence"]["delta"]["threads"], 1)

    def test_probe_evidence_rejects_source_outside_selected_data_id(self):
        parsed = {
            "values": {"first.source_count": "0", "second.source_count": "0"},
            "streams": {
                "child_config.0": {
                    "path": "/data/etc/bkunifylogbeat/a.conf",
                    "content": "local:\n  - dataid: 1001\n    paths: ['/data/allowed/*.log']\n",
                }
            },
        }

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source="/etc/passwd",
            include_source_sample=False,
            config_map_main=None,
        )

        self.assertEqual(probes["source_path"]["code"], "source_not_in_rendered_config")

    def test_probe_evidence_reports_sample_omitted_by_output_budget(self):
        parsed = {
            "values": {
                "first.source_count": "1",
                "first.source.0.pattern": "/data/*.log",
                "first.source.0.path": "/data/app.log",
                "second.source_count": "1",
                "second.source.0.pattern": "/data/*.log",
                "second.source.0.path": "/data/app.log",
                "second.source.0.sample.unavailable": "output_budget_exhausted",
            },
            "streams": {
                "child_config.0": {
                    "path": "/data/etc/bkunifylogbeat/a.conf",
                    "content": "local:\n  - dataid: 1001\n    paths: ['/data/*.log']\n",
                }
            },
        }

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source="/data/app.log",
            include_source_sample=True,
            config_map_main=None,
        )

        source_probe = probes["source_path"]
        self.assertEqual(
            source_probe["evidence"]["files"][0]["sample"]["unavailable_reason"],
            "output_budget_exhausted",
        )
        self.assertEqual(source_probe["warnings"][0]["code"], "source_sample_unavailable")

    def test_probe_evidence_requires_narrowing_when_remote_source_limit_is_exceeded(self):
        parsed = {
            "values": {
                "source_narrowing_required": "true",
                "first.source_count": "0",
                "second.source_count": "0",
            },
            "streams": {
                "child_config.0": {
                    "path": "/data/etc/bkunifylogbeat/a.conf",
                    "content": "local:\n  - dataid: 1001\n    paths: ['/data/allowed/*.log']\n",
                }
            },
        }

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
        )

        self.assertEqual(probes["source_path"]["status"], "warning")
        self.assertEqual(probes["source_path"]["code"], "source_narrowing_required")

        requested = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source="/data/allowed/app.log",
            include_source_sample=True,
            config_map_main=None,
        )
        self.assertEqual(requested["source_path"]["code"], "source_narrowing_required")

    def test_fixed_collector_file_logs_are_only_a_bounded_fallback(self):
        parsed = {
            "values": {"collector_file_log_count": "1"},
            "streams": {
                "collector_file_log.0": {
                    "path": "/data/logs/bkunifylogbeat.log",
                    "content": "collector error",
                    "returned_size_bytes": 15,
                    "total_size_bytes": 15,
                    "truncated": False,
                }
            },
        }

        result = build_collector_file_log_probe(parsed)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "collector_file_logs_fallback")
        self.assertTrue(result["evidence"]["fallback"])

    def test_reload_observation_does_not_infer_success_from_desired_config(self):
        no_marker = probe(evidence={"files": [{"path": "pods/log", "content": "sidecar is healthy"}]})
        observed = probe(evidence={"files": [{"path": "pods/log", "content": "config reloaded successfully"}]})

        self.assertEqual(_reload_observation_probe(no_marker)["code"], "reload_event_not_observed")
        self.assertEqual(_reload_observation_probe(observed)["code"], "reload_event_observed")


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class K8sInspectionWorkerTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    @patch(
        "apps.log_admin_resource.k8s_tasks.CollectorConfig.objects.get",
        return_value=collector(bcs_cluster_id="BCS-K8S-CHANGED"),
    )
    def test_worker_rejects_collector_binding_changed_after_dispatch(self, _get):
        with self.assertRaisesRegex(RuntimeError, "collector binding changed"):
            _load_bound_collector(
                {
                    "bk_tenant_id": "tenant-a",
                    "target": {
                        "collector_config_id": 123,
                        "bk_biz_id": 2,
                        "bk_data_id": 1001,
                        "bcs_cluster_id": "BCS-K8S-1",
                    },
                }
            )

    def _record(self, *, target=None, groups=None, candidate_id=None):
        return ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={
                "collector_config_id": 123,
                "bk_biz_id": 2,
                "bk_data_id": 1001,
                "bcs_cluster_id": "BCS-K8S-1",
                "observed_object": target,
            },
            request_options={
                "target": target,
                "evidence_groups": groups or ["control_plane"],
                "collector_candidate_id": candidate_id,
                "source": None,
                "include_source_sample": False,
                "runtime_log_options": {"keywords": [], "match": "any", "case_sensitive": False, "context_lines": 0},
            },
            task_type=TASK_TYPE_K8S_INSPECTION,
        )[0]

    @patch("apps.log_admin_resource.k8s_tasks.K8sInspectionClient")
    @patch("apps.log_admin_resource.k8s_tasks.expected_bklog_configs", return_value=[])
    @patch("apps.log_admin_resource.k8s_tasks.ContainerCollectorConfig.objects.filter")
    @patch("apps.log_admin_resource.k8s_tasks.CollectorConfig.objects.get", return_value=collector())
    @patch("apps.log_admin_resource.k8s_tasks._control_plane_probe")
    def test_control_plane_only_task_finishes_success(self, control, _get, configs_filter, _expected, _client):
        configs_filter.return_value.order_by.return_value = []
        control.return_value = (probe(evidence={}), None, [])
        record = self._record()

        run_k8s_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(stored["task_status"], "success")
        self.assertEqual(result["remote_execution"]["executor"], "K8S_API")
        self.assertFalse(result["remote_execution"]["mutations_permitted"])

    @patch("apps.log_admin_resource.k8s_tasks._revalidate_candidate")
    @patch("apps.log_admin_resource.k8s_tasks._discover_candidates")
    @patch("apps.log_admin_resource.k8s_tasks.K8sInspectionClient")
    @patch("apps.log_admin_resource.k8s_tasks.expected_bklog_configs", return_value=[])
    @patch("apps.log_admin_resource.k8s_tasks.ContainerCollectorConfig.objects.filter")
    @patch("apps.log_admin_resource.k8s_tasks.CollectorConfig.objects.get", return_value=collector())
    @patch("apps.log_admin_resource.k8s_tasks._control_plane_probe")
    def test_multiple_candidates_return_narrowing_without_exec(
        self, control, _get, configs_filter, _expected, _client, discover, revalidate
    ):
        configs_filter.return_value.order_by.return_value = []
        control.return_value = (probe(evidence={}), "node-a", ["bkte"])
        discover.return_value = (
            [candidate(pod_name="a", pod_uid="a"), candidate(pod_name="b", pod_uid="b")],
            [],
            [],
        )
        record = self._record(target={"type": "node", "node_name": "node-a"}, groups=["collector"])

        run_k8s_inspection.run(record["task_id"])

        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(ResourceInspectionTaskRecord.get(record["task_id"])["task_status"], "partial")
        self.assertEqual(result["probes"]["control_plane"]["code"], "collector_target_narrowing_required")
        self.assertEqual(len(result["probes"]["control_plane"]["evidence"]["collector_candidates"]), 2)
        revalidate.assert_not_called()

    def test_revalidation_rejects_changed_container_identity_before_probe(self):
        changed_pod = collector_pod(container_id="containerd://changed")
        client = SimpleNamespace(
            read_daemon_set=lambda namespace, name: daemon_set(),
            read_pod=lambda namespace, name: changed_pod,
        )

        with self.assertRaisesRegex(Exception, "container identity changed"):
            _revalidate_candidate(client, candidate(), ["bkte"])

    @patch("apps.log_admin_resource.k8s_tasks.BcsHandler.list_bcs_cluster", return_value=[])
    def test_control_plane_rejects_windows_target_before_collector_exec(self, _clusters):
        client = SimpleNamespace(
            read_crd=lambda _name: {"metadata": {"name": "bklogconfigs.bk.tencent.com"}, "spec": {}},
            list_bklog_configs=lambda _namespace: {"items": []},
            read_node=lambda _name: {
                "metadata": {"name": "node-a", "labels": {"kubernetes.io/os": "windows"}},
                "status": {},
            },
        )
        record = {"request_options": {"target": {"type": "node", "node_name": "node-a"}}}

        result, node_name, _envs = _control_plane_probe(
            record=record,
            collector=collector(),
            expected=[],
            client=client,
        )

        self.assertEqual(result["code"], "unsupported_os")
        self.assertEqual(node_name, "node-a")

    @override_settings(CONTAINER_COLLECTOR_CR_LABEL_BKENV="bkte")
    @patch("apps.log_admin_resource.k8s_tasks.BcsHandler.list_bcs_cluster", return_value=[])
    def test_control_plane_requires_configured_bk_env_even_when_cr_is_missing(self, _clusters):
        client = SimpleNamespace(
            read_crd=lambda _name: {"metadata": {"name": "bklogconfigs.bk.tencent.com"}, "spec": {}},
            list_bklog_configs=lambda _namespace: {"items": []},
        )

        _result, _node_name, required_envs = _control_plane_probe(
            record={"request_options": {}},
            collector=collector(),
            expected=[],
            client=client,
        )

        self.assertEqual(required_envs, ["bkte"])

    def test_pod_logs_read_only_fixed_collector_container_and_bound_total(self):
        calls = []

        class Client:
            def read_pod_log(self, namespace, pod_name, container_name, *, previous):
                calls.append((namespace, pod_name, container_name, previous))
                return {
                    "files": [{"path": "pods/log", "content": "x" * 100, "truncated": False}],
                    "truncated": False,
                }

        result = _pod_logs_probe(
            Client(),
            candidate(),
            container_name=COLLECTOR_CONTAINER_NAME,
            public_limit=120,
            probe_code="collector_logs_inspected",
        )

        self.assertEqual([item[2] for item in calls], [COLLECTOR_CONTAINER_NAME, COLLECTOR_CONTAINER_NAME])
        self.assertEqual(result["evidence"]["returned_size_bytes"], 120)
        self.assertTrue(result["evidence"]["truncated"])

    def test_oversized_final_result_is_compacted_instead_of_leaving_task_running(self):
        record = self._record()
        result = {
            "problem_env": "bkte",
            "source_env": "bkte",
            "observed_at": timezone.now().isoformat(),
            "target": {},
            "remote_execution": {
                "executor": "K8S_API",
                "mode": "server_fixed_read_only_probe",
                "mutations_permitted": False,
            },
            "probes": {"collector_logs": probe(evidence={"files": [{"content": "x" * (11 * 1024 * 1024)}]})},
            "partial": False,
            "error": None,
        }

        compacted = _store_bounded_result(record["task_id"], result)
        stored = ResourceInspectionTaskRecord.load_result(record["task_id"])

        self.assertTrue(compacted)
        self.assertTrue(stored["partial"])
        self.assertEqual(stored["probes"]["response_limit"]["code"], "response_compacted")
