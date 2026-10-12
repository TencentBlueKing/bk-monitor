"""Standalone CR inspection must not depend on a SaaS collector or business ownership."""

import copy
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.k8s_inspection import (
    CONFIG_LIST_FUNC_NAME,
    FUNCTIONS,
    START_FUNC_NAME,
    TARGET_LIST_FUNC_NAME,
    TARGET_LIST_RESPONSE_SCHEMA,
    _validate_candidate_binding,
    get_k8s_inspection_detail,
    list_k8s_inspection_configs,
    list_k8s_inspection_targets,
    start_k8s_inspection,
)
from apps.log_admin_resource.inspection_tasks import ResourceInspectionTaskRecord
from apps.log_admin_resource.k8s_cluster_context import ClusterInspectionContext, load_cluster_context
from apps.log_admin_resource.k8s_inspection import collector_child_config_hints, target_config_matches
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient
from apps.log_admin_resource.k8s_probe import FixedProbeError
from apps.log_admin_resource.k8s_tasks import (
    _control_plane_probe,
    _load_bound_collector,
    _public_candidates,
    _select_candidate,
    run_k8s_inspection,
)
from apps.log_admin_resource.schema import validate_params
from apps.tests.log_admin_resource.test_k8s_inspection import (
    TEST_CACHES,
    business_pod,
    candidate,
    collector_pod,
    daemon_set,
    probe,
    task_cache,
)


def config():
    return {
        "metadata": {
            "namespace": "production",
            "name": "manual-api",
            "uid": "cr-uid",
            "resourceVersion": "42",
            "labels": {"bk_env": "bkop"},
        },
        "spec": {
            "dataId": 1001,
            "namespace": "production",
            "logConfigType": "std_log_config",
            "labelSelector": {"matchLabels": {"app": "demo"}},
            "extOptions": {"password": "must-not-be-persisted"},
        },
    }


def params():
    return {"bcs_cluster_id": "BCS-K8S-1", "bklog_config": {"namespace": "production", "name": "manual-api"}}


def target():
    return {"type": "pod_container", "namespace": "production", "pod_name": "demo-abc", "container_name": "app"}


def running_business_pod():
    pod = business_pod()
    pod["status"]["containerStatuses"][0]["containerID"] = "containerd://app-container"
    return pod


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class ClusterInspectionTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()
        self.identity = patch(
            "apps.log_admin_resource.handlers.k8s_inspection._request_identity", return_value=("reader-a", "tenant-a")
        ).start()
        self.cr_read = patch.object(K8sInspectionClient, "read_bklog_config", return_value=config()).start()
        # BCS client construction only; Kubernetes operations remain individually mocked.
        patch("apps.log_admin_resource.k8s_inspection_client.Bcs").start()
        self.dispatch = patch("apps.log_admin_resource.k8s_tasks.run_k8s_inspection.apply_async").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(task_cache().clear)

    def start(self, **overrides):
        result = start_k8s_inspection({**params(), "evidence_groups": ["control_plane"], **overrides})
        return ResourceInspectionTaskRecord.get(result["task_id"])

    def test_metadata_accepts_both_modes_and_rejects_ambiguous_identity(self):
        for func_name in (START_FUNC_NAME, TARGET_LIST_FUNC_NAME):
            schema = FUNCTIONS[func_name]["params_schema"]
            for value in (params(), {"collector_config_id": 123}):
                validate_params(value, schema)
            for value in (
                {},
                {"bcs_cluster_id": "BCS-K8S-1"},
                {**params(), "collector_config_id": 123},
                {**params(), "bk_data_id": 999},
                {**params(), "command": "cat /etc/passwd"},
            ):
                with self.subTest(func_name=func_name, value=value), self.assertRaises(ValidationError):
                    validate_params(value, schema)

    def test_independent_start_preserves_cr_identity_without_ownership_or_orm(self):
        with (
            patch("apps.log_admin_resource.handlers.k8s_inspection._get_collector") as get_collector,
            patch("apps.log_admin_resource.handlers.k8s_inspection._resolve_collector_identity") as resolve,
        ):
            record = self.start()
        get_collector.assert_not_called()
        resolve.assert_not_called()
        self.assertIsNone(record["target"]["collector_config_id"])
        self.assertEqual(record["target"]["bk_data_id"], 1001)
        self.assertEqual(record["target"]["bklog_config"]["bk_env"], "bkop")
        self.assertNotIn("must-not-be-persisted", str(record))
        self.dispatch.assert_called_once()

    def test_cr_change_does_not_reuse_previous_task(self):
        first = self.start()
        self.cr_read.return_value["spec"]["dataId"] = 2002
        second = self.start()
        self.assertNotEqual(first["task_id"], second["task_id"])

    def test_worker_refuses_replaced_or_modified_cr(self):
        record = self.start()
        original = copy.deepcopy(self.cr_read.return_value)
        for section, key, value in (("metadata", "uid", "replacement"), ("spec", "dataId", 2002)):
            self.cr_read.return_value = copy.deepcopy(original)
            self.cr_read.return_value[section][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValidationError, "changed_after_dispatch"):
                _load_bound_collector(record)
        self.cr_read.return_value = copy.deepcopy(original)
        self.cr_read.return_value["metadata"]["labels"]["bk_env"] = "bkte"
        with self.assertRaisesRegex(ValidationError, "changed_after_dispatch"):
            _load_bound_collector(record)

    def test_worker_ignores_resource_version_only_change(self):
        record = self.start()
        self.cr_read.return_value["metadata"]["resourceVersion"] = "43"
        self.assertEqual(_load_bound_collector(record).bk_data_id, 1001)

    def test_task_access_remains_app_and_tenant_isolated(self):
        record = self.start()
        for identity in (("other-reader", "tenant-a"), ("reader-a", "other-tenant")):
            self.identity.return_value = identity
            result = get_k8s_inspection_detail({"task_id": record["task_id"]})
            self.assertEqual(result["task_status"], "not_found")

    def test_missing_data_id_retains_control_plane_and_skips_deep_groups(self):
        self.cr_read.return_value["spec"].pop("dataId")
        record = self.start(target=target(), evidence_groups=["all"])
        self.assertIsNone(record["target"]["bk_data_id"])
        self.assertEqual(record["request_options"]["evidence_groups"], ["control_plane"])
        self.assertEqual(len(record["request_options"]["skipped_evidence_groups"]), 3)

    @patch.object(K8sInspectionClient, "list_bklog_config_page")
    def test_cluster_discovery_paginates_and_omits_private_ext_options(self, list_page):
        list_page.return_value = ([config()], "page-two")
        result = list_k8s_inspection_configs({"bcs_cluster_id": "BCS-K8S-1", "limit": 1})
        validate_params(result, FUNCTIONS[CONFIG_LIST_FUNC_NAME]["response_schema"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["continue_token"], "page-two")
        self.assertEqual(result["configs"][0]["bk_env"], "bkop")
        self.assertNotIn("must-not-be-persisted", str(result))
        list_k8s_inspection_configs({"bcs_cluster_id": "BCS-K8S-1", "continue_token": "page-two"})
        self.assertEqual(list_page.call_args.kwargs["continue_token"], "page-two")

    @patch.object(K8sInspectionClient, "list_bklog_config_page", side_effect=RuntimeError("unavailable"))
    def test_discovery_failure_is_not_an_empty_cluster(self, _list):
        with self.assertRaises(RuntimeError):
            list_k8s_inspection_configs({"bcs_cluster_id": "BCS-K8S-1"})

    @patch.object(K8sInspectionClient, "list_pod_page")
    def test_target_discovery_uses_actual_namespace_and_selector(self, list_page):
        list_page.return_value = ([business_pod(), business_pod(namespace="elsewhere")], None)
        result = list_k8s_inspection_targets(params())
        validate_params(result, TARGET_LIST_RESPONSE_SCHEMA)
        self.assertEqual(len(result["pod_targets"]), 1)
        self.assertEqual(result["pod_targets"][0]["target"], target())
        self.assertEqual(result["container_config_ids"], [])
        self.assertFalse(result["partial"])

    def test_legacy_namespace_follows_sidecar_selector_precedence(self):
        context = ClusterInspectionContext("BCS-K8S-1", config())
        other = business_pod(namespace="elsewhere")
        other_target = {**target(), "namespace": "elsewhere"}
        for selector, expected_match in (
            ({}, False),
            ({"any": True}, True),
            ({"matchNames": ["elsewhere"]}, True),
            ({"excludeNames": ["production"], "matchNames": ["production"]}, True),
            ({"any": True, "excludeNames": ["elsewhere"]}, True),
        ):
            context.config["spec"]["namespaceSelector"] = selector
            with self.subTest(selector=selector):
                self.assertEqual(bool(target_config_matches(other_target, other, context.expected)), expected_match)

    @override_settings(CONTAINER_COLLECTOR_CR_LABEL_BKENV="bkte")
    def test_control_plane_uses_cr_environment_and_reports_observation_only(self):
        context = load_cluster_context(**{"cluster_id": "BCS-K8S-1", "reference": params()["bklog_config"]})
        client = MagicMock()
        client.read_crd.return_value = {"spec": {"preserveUnknownFields": True}}
        client.read_bklog_config.return_value = config()
        with patch("apps.log_admin_resource.k8s_tasks.BcsHandler.list_bcs_cluster") as ownership:
            probe, node, envs = _control_plane_probe(
                record={}, collector=context, expected=context.expected, client=client
            )
        ownership.assert_not_called()
        client.list_bklog_configs.assert_not_called()
        client.read_bklog_config.assert_called_once_with("production", "manual-api")
        self.assertEqual(envs, ["bkop"])
        self.assertEqual(probe["status"], "success")
        self.assertNotIn("desired_config", probe["evidence"])
        self.assertFalse(probe["evidence"]["observed_config"]["saas_desired_comparison_performed"])

    def test_child_hints_use_cr_namespace_not_default(self):
        context = ClusterInspectionContext("BCS-K8S-1", config())
        hints = collector_child_config_hints(
            {"type": "pod_container", "container": {"container_id": "containerd://abc123"}}, context.expected
        )
        self.assertEqual(hints, ["abc123_std_log_config_production_manual-api.conf"])

    def test_candidate_from_other_cr_cannot_be_used(self):
        from apps.log_admin_resource.k8s_inspection import CollectorCandidate

        record = self.start(target=target())
        candidate = CollectorCandidate(
            cluster_id="BCS-K8S-1",
            namespace="kube-system",
            daemon_set_name="collector",
            daemon_set_uid="ds-uid",
            pod_name="collector-node-a",
            pod_uid="pod-uid",
            node_name="node-a",
            collector_container_id="containerd://collector",
            collector_image_id="image",
            manual_installation=False,
        )
        candidate_id = _public_candidates(record, [candidate])[0]["collector_candidate_id"]
        record["request_options"]["collector_candidate_id"] = candidate_id
        self.assertEqual(_select_candidate(record, [candidate]), candidate)
        record["target"]["bklog_config"]["name"] = "another-config"
        with self.assertRaises(FixedProbeError):
            _select_candidate(record, [candidate])
        context = ClusterInspectionContext("BCS-K8S-1", config())
        with self.assertRaises(ValidationError):
            _validate_candidate_binding(
                candidate_id=candidate_id,
                app_code="reader-a",
                tenant_id="tenant-a",
                collector=context,
                target=target(),
                identity={"bcs_cluster_id": "BCS-K8S-1", "bklog_config": record["target"]["bklog_config"]},
            )

    @patch.object(K8sInspectionClient, "read_crd", return_value={"spec": {"preserveUnknownFields": True}})
    def test_independent_task_runs_to_completion_without_models(self, _crd):
        record = self.start()
        with (
            patch("apps.log_admin_resource.k8s_tasks.CollectorConfig.objects.get") as get,
            patch("apps.log_admin_resource.k8s_tasks.ContainerCollectorConfig.objects.filter") as configs,
            patch("apps.log_admin_resource.k8s_tasks.BcsHandler.list_bcs_cluster") as ownership,
        ):
            run_k8s_inspection.run(record["task_id"])
        get.assert_not_called()
        configs.assert_not_called()
        ownership.assert_not_called()
        detail = get_k8s_inspection_detail({"task_id": record["task_id"]})
        self.assertEqual(detail["task_status"], "success")
        self.assertEqual(detail["evidence"]["target"]["bk_data_id"], 1001)
        self.assertNotIn("must-not-be-persisted", str(detail))

    @patch.object(K8sInspectionClient, "read_crd", return_value={"spec": {"preserveUnknownFields": True}})
    @patch.object(K8sInspectionClient, "read_pod", return_value=running_business_pod())
    @patch.object(
        K8sInspectionClient, "read_node", return_value={"metadata": {"labels": {"kubernetes.io/os": "linux"}}}
    )
    @patch.object(K8sInspectionClient, "list_events", return_value=[])
    @patch("apps.log_admin_resource.k8s_tasks._discover_candidates", return_value=([candidate()], [], []))
    @patch("apps.log_admin_resource.k8s_tasks._revalidate_candidate", return_value=(daemon_set(), collector_pod()))
    @patch("apps.log_admin_resource.k8s_tasks._config_map_probe", return_value=(probe(), {}))
    @patch("apps.log_admin_resource.k8s_tasks._pod_logs_probe", return_value=probe())
    @patch("apps.log_admin_resource.k8s_tasks.build_probe_evidence", return_value={"collector": probe()})
    @patch("apps.log_admin_resource.k8s_tasks.run_fixed_collector_probe", return_value={})
    def test_deep_probe_uses_actual_cr_dataid_and_child_path(self, fixed_probe, build, *mocks):
        record = self.start(target=target(), evidence_groups=["collector"])
        run_k8s_inspection.run(record["task_id"])
        detail = get_k8s_inspection_detail({"task_id": record["task_id"]})
        self.assertEqual(detail["task_status"], "success", detail.get("error"))
        self.assertEqual(fixed_probe.call_args.kwargs["bk_data_id"], 1001)
        hints = fixed_probe.call_args.kwargs["child_config_hints"]
        self.assertTrue(hints)
        self.assertTrue(all(item.endswith("_std_log_config_production_manual-api.conf") for item in hints))
        self.assertEqual(build.call_args.kwargs["bk_data_id"], 1001)
        self.assertEqual(build.call_args.kwargs["expected_specs"], [config()["spec"]])


class ClusterClientTest(SimpleTestCase):
    @patch("apps.log_admin_resource.k8s_inspection_client.Bcs")
    def test_config_list_uses_namespaced_or_cluster_api_and_timeout(self, bcs):
        api = bcs.return_value.crd_api
        api.list_cluster_custom_object.return_value = {"items": [], "metadata": {"continue": "next"}}
        api.list_namespaced_custom_object.return_value = {"items": [], "metadata": {}}
        client = K8sInspectionClient("BCS-K8S-1")
        self.assertEqual(client.list_bklog_config_page(limit=50), ([], "next"))
        client.list_bklog_config_page("production", limit=10, continue_token="next")
        args = api.list_namespaced_custom_object.call_args.kwargs
        self.assertEqual(args["namespace"], "production")
        self.assertEqual(args["_continue"], "next")
        self.assertEqual(args["limit"], 10)
        self.assertEqual(args["_request_timeout"], 10)
