"""Exercise production BCS sync logic with constructed data and no Django/DB bootstrap."""

import ast
import json
import re
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[3]


def load_definition(path, name, namespace, methods=None):
    tree = ast.parse((ROOT / path).read_text())
    node = next(node for node in tree.body if getattr(node, "name", None) == name)
    if methods is not None:
        node.bases = []
        node.body = [child for child in node.body if getattr(child, "name", None) in methods]
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class QuerySet(list):
    def filter(self, **kwargs):
        def matches(item):
            for key, value in kwargs.items():
                if key.endswith("__in"):
                    if getattr(item, key[:-4]) not in value:
                        return False
                elif getattr(item, key) != value:
                    return False
            return True

        return QuerySet(item for item in self if matches(item))

    def values_list(self, *fields):
        return [tuple(getattr(item, field) for field in fields) for item in self]

    def first(self):
        return self[0] if self else None

    def exclude(self, **kwargs):
        excluded = self.filter(**kwargs)
        return QuerySet(item for item in self if item not in excluded)

    def update(self, **kwargs):
        for item in self:
            for key, value in kwargs.items():
                setattr(item, key, value)


class TestDiscoveryFailureIsolation(unittest.TestCase):
    def setUp(self):
        self.records = QuerySet()
        self.model = SimpleNamespace(
            CLUSTER_STATUS_RUNNING="running",
            CLUSTER_RAW_STATUS_RUNNING="RUNNING",
            CLUSTER_STATUS_INIT_FAILED="init_failed",
            CLUSTER_RAW_STATUS_DELETED="DELETED",
            objects=self.records,
            register_cluster=Mock(side_effect=self.register),
        )
        self.settings = SimpleNamespace(
            NEW_ENV_START_CLUSTER_ID=None,
            NEW_ENV_CLUSTER_ID_RANGES=[],
            NEW_ENV_CLUSTER_BLACK_LIST=[],
            NEW_ENV_CLUSTER_WHITE_LIST=[],
            ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST=[],
            BCS_API_GATEWAY_TOKEN="fixture-token",
            DISABLE_BCS_CLUSTER_REFRESH_COMMON_RESOURCE=False,
        )
        self.api = SimpleNamespace(
            bk_login=SimpleNamespace(list_tenant=Mock(return_value=[{"id": "tenant-a"}])),
            kubernetes=SimpleNamespace(fetch_k8s_cluster_list=Mock(return_value=[])),
            bcs=SimpleNamespace(get_federation_clusters=Mock(return_value={})),
        )
        self.namespace = {
            "BCSClusterInfo": self.model,
            "models": SimpleNamespace(BCSClusterInfo=self.model),
            "settings": self.settings,
            "api": self.api,
            "metrics": Mock(),
            "logger": Mock(),
            "time": time,
            "BCS_CLUSTER_ID_PATTERN": re.compile(r"^BCS-K8S-(\d+)$"),
            "PERIODIC_TASK_DEFAULT_TTL": 60,
            "TASK_STARTED": "started",
            "TASK_FINISHED_SUCCESS": "success",
            "TASK_FINISHED_FAILURE": "failure",
            "share_lock": lambda **kwargs: lambda function: function,
            "bk_biz_id_to_bk_tenant_id": Mock(return_value="tenant-a"),
            "change_cluster_router": Mock(),
            "update_bcs_cluster_cloud_id_config": Mock(),
            "sync_and_schedule_federation_clusters": Mock(return_value=True),
        }
        for name in (
            "get_bcs_cluster_id_suffix",
            "get_discover_start_cluster_id_suffix",
            "get_discover_cluster_id_ranges",
            "is_discover_biz_blacklisted",
            "is_discover_biz_whitelisted",
            "is_discover_managed_cluster",
            "discover_bcs_clusters",
        ):
            load_definition("metadata/task/bcs.py", name, self.namespace)
        self.discover = self.namespace["discover_bcs_clusters"]

    def cluster(self, cluster_id, tenant="tenant-a", biz=1, status="RUNNING"):
        cluster = SimpleNamespace(
            cluster_id=cluster_id,
            bk_tenant_id=tenant,
            bk_biz_id=biz,
            status=status,
            project_id="fixture-project",
            api_key_content=self.settings.BCS_API_GATEWAY_TOKEN,
            bk_cloud_id=0,
            CustomMetricDataID=1,
            init_resource=Mock(return_value=True),
            refresh_common_resource=Mock(),
            save=Mock(),
        )
        self.records.append(cluster)
        return cluster

    def register(self, **kwargs):
        return self.cluster(kwargs["cluster_id"], kwargs["bk_tenant_id"], kwargs["bk_biz_id"])

    @staticmethod
    def discovered(cluster_id, biz=1):
        return {
            "cluster_id": cluster_id,
            "bk_biz_id": biz,
            "status": "RUNNING",
            "project_id": "fixture-project",
        }

    def assert_task_status(self, status):
        self.assertEqual(
            self.namespace["metrics"].METADATA_CRON_TASK_STATUS_TOTAL.labels.call_args.kwargs["status"], status
        )

    def test_multiple_ranges_override_legacy_threshold_and_exclude_boundaries(self):
        self.settings.NEW_ENV_START_CLUSTER_ID = "BCS-K8S-90000"
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [
            {"start": 25200, "end": 40000},
            {"start": 41200, "end": None},
        ]
        ranges = self.namespace["get_discover_cluster_id_ranges"]()
        self.assertEqual(ranges, self.settings.NEW_ENV_CLUSTER_ID_RANGES)
        for suffix, expected in (
            (25199, False),
            (25200, False),
            (25201, True),
            (39999, True),
            (40000, False),
            (41000, False),
            (41200, False),
            (41201, True),
            (100000, True),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    self.namespace["is_discover_managed_cluster"](f"BCS-K8S-{suffix}", ranges, 1), expected
                )
        self.assertFalse(self.namespace["is_discover_managed_cluster"]("invalid-cluster", ranges, 1))

    def test_arbitrary_multiple_ranges(self):
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [
            {"start": 80, "end": None},
            {"start": 10, "end": 20},
            {"start": 30, "end": 40},
        ]
        ranges = self.namespace["get_discover_cluster_id_ranges"]()
        for suffix in (11, 19, 31, 39, 81):
            self.assertTrue(self.namespace["is_discover_managed_cluster"](f"BCS-K8S-{suffix:05}", ranges, 1))
        for suffix in (10, 20, 25, 30, 40, 80):
            self.assertFalse(self.namespace["is_discover_managed_cluster"](f"BCS-K8S-{suffix:05}", ranges, 1))

    def test_empty_ranges_fall_back_to_legacy_threshold(self):
        for suffix in (0, 5):
            with self.subTest(suffix=suffix):
                self.settings.NEW_ENV_START_CLUSTER_ID = f"BCS-K8S-{suffix:05}"
                ranges = self.namespace["get_discover_cluster_id_ranges"]()
                self.assertEqual(ranges, [{"start": suffix, "end": None}])
                self.assertFalse(self.namespace["is_discover_managed_cluster"](f"BCS-K8S-{suffix:05}", ranges, 1))
                self.assertTrue(self.namespace["is_discover_managed_cluster"](f"BCS-K8S-{suffix + 1:05}", ranges, 1))

    def test_unconfigured_or_invalid_legacy_threshold_keeps_historical_behavior(self):
        for start_cluster_id in (None, "", "invalid-cluster"):
            with self.subTest(start_cluster_id=start_cluster_id):
                self.settings.NEW_ENV_START_CLUSTER_ID = start_cluster_id
                ranges = self.namespace["get_discover_cluster_id_ranges"]()
                self.assertEqual(ranges, [])
                for cluster_id in ("BCS-K8S-00001", "invalid-cluster"):
                    self.assertTrue(self.namespace["is_discover_managed_cluster"](cluster_id, ranges, 1))

    def test_blacklist_overrides_whitelist_and_whitelist_exempts_ranges(self):
        self.settings.NEW_ENV_CLUSTER_BLACK_LIST = ["3"]
        self.settings.NEW_ENV_CLUSTER_WHITE_LIST = [2, 3]
        ranges = [{"start": 10, "end": 20}]
        self.assertFalse(self.namespace["is_discover_managed_cluster"]("BCS-K8S-00001", ranges, 1))
        self.assertTrue(self.namespace["is_discover_managed_cluster"]("BCS-K8S-00001", ranges, "2"))
        for cluster_id in ("BCS-K8S-00001", "BCS-K8S-00011"):
            self.assertFalse(self.namespace["is_discover_managed_cluster"](cluster_id, ranges, 3))
        self.assertFalse(self.namespace["is_discover_managed_cluster"]("BCS-K8S-00011", [], 3))

    def test_discovery_registers_only_clusters_in_configured_ranges(self):
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [
            {"start": 25200, "end": 40000},
            {"start": 41200, "end": None},
        ]
        self.api.kubernetes.fetch_k8s_cluster_list.return_value = [
            self.discovered(f"BCS-K8S-{suffix}") for suffix in (25200, 25201, 39999, 40000, 41000, 41200, 41201)
        ]
        self.discover()
        self.assertEqual(
            {cluster.cluster_id for cluster in self.records}, {"BCS-K8S-25201", "BCS-K8S-39999", "BCS-K8S-41201"}
        )
        self.assert_task_status("success")

    def test_discovery_skips_updates_and_init_retries_outside_ranges(self):
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [{"start": 10, "end": 20}]
        managed = self.cluster("BCS-K8S-00011", status="init_failed")
        excluded = self.cluster("BCS-K8S-00020", status="init_failed")
        for cluster in (managed, excluded):
            cluster.api_key_content = "previous-token"
        self.api.kubernetes.fetch_k8s_cluster_list.return_value = [
            self.discovered(cluster.cluster_id) for cluster in (managed, excluded)
        ]
        self.discover()
        managed.init_resource.assert_called_once()
        managed.save.assert_called_once()
        self.assertEqual(managed.status, "RUNNING")
        self.assertEqual(managed.api_key_content, self.settings.BCS_API_GATEWAY_TOKEN)
        excluded.init_resource.assert_not_called()
        excluded.save.assert_not_called()
        self.assertEqual(excluded.status, "init_failed")
        self.assertEqual(excluded.api_key_content, "previous-token")
        self.assert_task_status("success")

    def test_missing_clusters_are_marked_deleted_only_within_ranges(self):
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [
            {"start": 25200, "end": 40000},
            {"start": 41200, "end": None},
        ]
        for suffix in (25200, 25201, 39999, 40000, 41000, 41200, 41201):
            self.cluster(f"BCS-K8S-{suffix}")
        self.discover()
        managed_cluster_ids = {"BCS-K8S-25201", "BCS-K8S-39999", "BCS-K8S-41201"}
        for cluster in self.records:
            with self.subTest(cluster_id=cluster.cluster_id):
                expected = "DELETED" if cluster.cluster_id in managed_cluster_ids else "RUNNING"
                self.assertEqual(cluster.status, expected)
        self.assert_task_status("success")

    def test_registration_failure_does_not_block_retry_or_next_tenant(self):
        retry = self.cluster("BCS-K8S-00002", status="init_failed")
        self.api.bk_login.list_tenant.return_value.append({"id": "tenant-b"})
        self.api.kubernetes.fetch_k8s_cluster_list.side_effect = [
            [self.discovered("BCS-K8S-00001"), self.discovered(retry.cluster_id)],
            [self.discovered("BCS-K8S-00003", biz=2)],
        ]
        self.namespace["bk_biz_id_to_bk_tenant_id"].side_effect = lambda biz: "tenant-a" if biz == 1 else "tenant-b"

        def register(**kwargs):
            if kwargs["cluster_id"] == "BCS-K8S-00001":
                raise RuntimeError("registration failed")
            return self.register(**kwargs)

        self.model.register_cluster.side_effect = register
        self.discover()
        retry.init_resource.assert_called_once_with(is_fed_cluster=False)
        self.assertEqual(retry.status, "RUNNING")
        self.assertIsNotNone(self.records.filter(cluster_id="BCS-K8S-00003").first())
        self.assert_task_status("failure")

    def test_migration_and_save_failures_do_not_block_later_retry(self):
        for failure in ("migration", "save"):
            with self.subTest(failure=failure):
                self.setUp()
                first = self.cluster("BCS-K8S-00001")
                retry = self.cluster("BCS-K8S-00002", status="init_failed")
                if failure == "migration":
                    self.namespace["change_cluster_router"].side_effect = RuntimeError("migration failed")
                    first_biz = 2
                else:
                    first.save.side_effect = RuntimeError("save failed")
                    first.api_key_content = "previous-token"
                    first_biz = 1
                self.api.kubernetes.fetch_k8s_cluster_list.return_value = [
                    self.discovered(first.cluster_id, first_biz),
                    self.discovered(retry.cluster_id),
                ]
                self.discover()
                retry.init_resource.assert_called_once()
                self.assertEqual(retry.status, "RUNNING")
                self.assert_task_status("failure")

    def test_tenant_validation_failure_preserves_init_failed_and_later_retries(self):
        for tenant_result in (RuntimeError("lookup failed"), "another-tenant"):
            with self.subTest(tenant_result=tenant_result):
                self.setUp()
                retry = self.cluster("BCS-K8S-00001", status="init_failed")
                healthy = self.cluster("BCS-K8S-00002", biz=2)
                self.api.kubernetes.fetch_k8s_cluster_list.return_value = [
                    self.discovered(retry.cluster_id),
                    self.discovered(healthy.cluster_id, biz=2),
                ]
                self.namespace["bk_biz_id_to_bk_tenant_id"].side_effect = [tenant_result, "tenant-a"]
                self.discover()
                self.assertEqual(retry.status, "init_failed")
                retry.init_resource.assert_not_called()
                self.namespace["bk_biz_id_to_bk_tenant_id"].side_effect = None
                self.discover()
                retry.init_resource.assert_called_once()
                self.assertEqual(retry.status, "RUNNING")

    def test_failed_tenant_excluded_from_deletion_and_successful_empty_snapshot_applies_filters(self):
        self.settings.NEW_ENV_START_CLUSTER_ID = "BCS-K8S-00005"
        self.settings.NEW_ENV_CLUSTER_WHITE_LIST = [2]
        self.settings.NEW_ENV_CLUSTER_BLACK_LIST = [3]
        self.settings.ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST = ["BCS-K8S-00009"]
        failed_tenant = self.cluster("BCS-K8S-00006", tenant="tenant-a")
        deleted = self.cluster("BCS-K8S-00007", tenant="tenant-b")
        whitelisted = self.cluster("BCS-K8S-00001", tenant="tenant-b", biz=2)
        below_threshold = self.cluster("BCS-K8S-00002", tenant="tenant-b")
        blacklisted = self.cluster("BCS-K8S-00008", tenant="tenant-b", biz=3)
        fake = self.cluster("BCS-K8S-00009", tenant="tenant-b")
        self.api.bk_login.list_tenant.return_value.append({"id": "tenant-b"})
        self.api.kubernetes.fetch_k8s_cluster_list.side_effect = [RuntimeError("list failed"), []]
        self.discover()
        self.assertEqual(deleted.status, "DELETED")
        self.assertEqual(whitelisted.status, "DELETED")
        for protected in (failed_tenant, below_threshold, blacklisted, fake):
            self.assertEqual(protected.status, "RUNNING")
        self.assert_task_status("failure")

    def test_live_cluster_moving_to_blacklisted_business_is_not_deleted(self):
        cluster = self.cluster("BCS-K8S-00001")
        self.settings.NEW_ENV_CLUSTER_BLACK_LIST = [2]
        self.api.kubernetes.fetch_k8s_cluster_list.return_value = [self.discovered(cluster.cluster_id, biz=2)]
        self.discover()
        self.assertEqual(cluster.status, "RUNNING")
        self.assertEqual(cluster.bk_biz_id, 1)
        cluster.save.assert_not_called()
        self.assert_task_status("success")

    def refresh(self):
        self.service = SimpleNamespace(PLURAL="ServiceMonitor", refresh_resource=Mock(), refresh_custom_resource=Mock())
        self.pod = SimpleNamespace(PLURAL="PodMonitor", refresh_resource=Mock(), refresh_custom_resource=Mock())
        self.namespace.update(ServiceMonitorInfo=self.service, PodMonitorInfo=self.pod)
        return load_definition("metadata/task/bcs.py", "refresh_bcs_monitor_info", self.namespace)

    def test_refresh_applies_ranges_and_business_lists(self):
        self.settings.NEW_ENV_CLUSTER_ID_RANGES = [
            {"start": 25200, "end": 40000},
            {"start": 41200, "end": None},
        ]
        self.settings.NEW_ENV_CLUSTER_WHITE_LIST = [2, 3]
        self.settings.NEW_ENV_CLUSTER_BLACK_LIST = [3]
        managed = [self.cluster("BCS-K8S-25201"), self.cluster("BCS-K8S-41201"), self.cluster("BCS-K8S-00001", biz=2)]
        excluded = [self.cluster(f"BCS-K8S-{suffix}") for suffix in (25200, 40000, 41000, 41200)]
        excluded.append(self.cluster("BCS-K8S-25202", biz=3))
        refresh = self.refresh()
        refresh()
        for cluster in managed:
            cluster.refresh_common_resource.assert_called_once()
        for cluster in excluded:
            cluster.refresh_common_resource.assert_not_called()
        for resource in (self.service, self.pod):
            self.assertEqual(
                {call.args[0] for call in resource.refresh_resource.call_args_list},
                {cluster.cluster_id for cluster in managed},
            )
            self.assertEqual(
                {call.kwargs["cluster_id"] for call in resource.refresh_custom_resource.call_args_list},
                {cluster.cluster_id for cluster in managed},
            )
        self.assert_task_status("success")

    def test_optional_pod_type_missing_still_refreshes_service_custom_dataid(self):
        cluster = self.cluster("BCS-K8S-00001")
        refresh = self.refresh()
        self.pod.refresh_resource.return_value = False
        refresh()
        cluster.refresh_common_resource.assert_called_once()
        self.service.refresh_custom_resource.assert_called_once_with(cluster_id=cluster.cluster_id)
        self.pod.refresh_custom_resource.assert_not_called()
        self.assert_task_status("success")

    def test_common_and_monitor_failures_do_not_stop_independent_refresh_stages(self):
        cluster = self.cluster("BCS-K8S-00001")
        refresh = self.refresh()
        cluster.refresh_common_resource.return_value = False
        self.service.refresh_resource.side_effect = RuntimeError("monitor authorization failed")
        self.service.refresh_custom_resource.return_value = False
        refresh()
        self.service.refresh_custom_resource.assert_called_once()
        self.pod.refresh_resource.assert_called_once()
        self.pod.refresh_custom_resource.assert_called_once()
        self.assert_task_status("failure")


class ApiException(Exception):
    def __init__(self, status, body=None):
        super().__init__(f"API error {status}")
        self.status = status
        self.body = body


class TestMonitorResourceFailureAccounting(unittest.TestCase):
    def setUp(self):
        self.custom_api = Mock()
        self.crd_api = Mock()
        self.k8s_client = SimpleNamespace(
            ApiClient=object,
            CustomObjectsApi=Mock(return_value=self.custom_api),
            ApiextensionsV1Api=Mock(return_value=self.crd_api),
        )
        self.namespace = {
            "k8s_client": self.k8s_client,
            "ApiException": ApiException,
            "json": json,
            "logger": Mock(),
            "config": SimpleNamespace(
                DATABASE_CONNECTION_NAME="metadata",
                BCS_RESOURCE_GROUP_NAME="example.test",
                BCS_RESOURCE_VERSION="v1",
                BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL="dataids",
            ),
            "atomic": lambda database: lambda function: function,
            "ensure_data_id_resource": Mock(return_value=False),
            "is_equal_config": lambda source, target: source == target,
        }
        load_definition("metadata/models/bcs/utils.py", "is_missing_custom_resource_definition", self.namespace)
        self.resource = load_definition(
            "metadata/models/bcs/resource.py",
            "BCSResource",
            self.namespace,
            {"refresh_resource", "refresh_custom_resource"},
        )
        self.resource.GROUP = "monitoring.coreos.com"
        self.resource.VERSION = "v1"
        self.resource.PLURALS = "podmonitors"
        self.resource.PLURAL = "PodMonitor"
        self.resource.objects = Mock()
        self.resource.make_bcs_client = Mock(return_value=object())

    def test_confirmed_missing_optional_crd_preserves_existing_mappings(self):
        self.custom_api.list_cluster_custom_object.side_effect = ApiException(404)
        self.crd_api.read_custom_resource_definition.side_effect = ApiException(
            404,
            json.dumps(
                {
                    "kind": "Status",
                    "reason": "NotFound",
                    "details": {
                        "group": "apiextensions.k8s.io",
                        "kind": "customresourcedefinitions",
                        "name": "podmonitors.monitoring.coreos.com",
                    },
                }
            ),
        )
        self.assertFalse(self.resource.refresh_resource("BCS-K8S-00001", 1))
        self.resource.objects.filter.assert_not_called()
        self.resource.objects.bulk_create.assert_not_called()

    def test_authorization_gateway_and_network_errors_are_not_missing_crd(self):
        for error in (ApiException(403), ApiException(404, "gateway not found"), OSError("network failed")):
            with self.subTest(error=error):
                self.custom_api.list_cluster_custom_object.side_effect = error
                self.crd_api.read_custom_resource_definition.side_effect = error
                with self.assertRaises(type(error)):
                    self.resource.refresh_resource("BCS-K8S-00001", 1)
        self.custom_api.list_cluster_custom_object.side_effect = ApiException(404)
        self.crd_api.read_custom_resource_definition.side_effect = None
        with self.assertRaises(ApiException):
            self.resource.refresh_resource("BCS-K8S-00001", 1)

    def test_custom_dataid_write_false_raises_without_logging_success(self):
        item = SimpleNamespace(config_name="fixture-dataid", config={}, should_refresh_own_dataid=lambda: True)
        self.resource.objects.filter.return_value = [item]
        self.custom_api.list_cluster_custom_object.return_value = {"items": []}
        with self.assertRaisesRegex(RuntimeError, "failed to create dataid"):
            self.resource.refresh_custom_resource("BCS-K8S-00001")
        self.assertFalse(
            any("add new resource" in call.args[0] for call in self.namespace["logger"].info.call_args_list)
        )

    def test_common_dataid_write_false_raises_without_logging_success(self):
        cluster_class = load_definition(
            "metadata/models/bcs/cluster.py", "BCSClusterInfo", self.namespace, {"refresh_common_resource"}
        )
        cluster = cluster_class()
        cluster.cluster_id = "BCS-K8S-00001"
        cluster.api_client = object()
        cluster.DATASOURCE_REGISTER_INFO = {"metric": {"datasource_name": "MetricDataID"}}
        cluster.compose_dataid_resource_name = lambda name, **kwargs: name
        cluster.make_config = Mock(return_value={})
        cluster._ensure_relation_dataid_resource = Mock()
        self.custom_api.list_cluster_custom_object.return_value = {"items": []}
        with self.assertRaisesRegex(RuntimeError, "failed to create dataid"):
            cluster.refresh_common_resource()
        self.assertFalse(
            any("add new resource" in call.args[0] for call in self.namespace["logger"].info.call_args_list)
        )

    def test_relation_dataid_write_false_raises_without_logging_success(self):
        data_source = SimpleNamespace(bk_data_id=1)
        self.namespace["DataSource"] = SimpleNamespace(
            objects=SimpleNamespace(get=Mock(return_value=data_source)),
            DoesNotExist=type("DoesNotExist", (Exception,), {}),
        )
        self.namespace["config"].BCS_RESOURCE_DATA_ID_RESOURCE_KIND = "DataID"
        cluster_class = load_definition(
            "metadata/models/bcs/cluster.py", "BCSClusterInfo", self.namespace, {"_ensure_relation_dataid_resource"}
        )
        cluster = cluster_class()
        cluster.cluster_id = "BCS-K8S-00001"
        cluster.bk_biz_id = 1
        cluster.api_client = object()
        cluster.operator_ns = "fixture-operator"
        cluster.compose_dataid_resource_name = lambda name: name
        cluster.compose_dataid_resource_label = lambda labels: labels
        self.custom_api.list_namespaced_custom_object.return_value = {
            "items": [{"metadata": {"name": "fixture-operator-relation"}}]
        }
        with self.assertRaisesRegex(RuntimeError, "failed to update dataid"):
            cluster._ensure_relation_dataid_resource()
        self.assertFalse(
            any(
                "ensure relation DataID CRD done" in call.args[0]
                for call in self.namespace["logger"].info.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
