"""Exercise production readers without application/database bootstrap."""

import ast
import collections
import tracemalloc
import unittest
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[2]


def load(path, name, env, methods=None, bases=False):
    node = next(n for n in ast.parse((ROOT / path).read_text()).body if getattr(n, "name", None) == name)
    if methods is not None:
        if not bases:
            node.bases = []
        node.body = [n for n in node.body if getattr(n, "name", None) in methods]
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), env)
    return env[name]


def parsers():
    env = {"cached_property": cached_property, "translate_timestamp_since": lambda _: "age"}
    load("bkmonitor/utils/kubernetes.py", "KubernetesV1ObjectJsonParser", env, {"__init__", "label_list", "age"})
    load(
        "bkmonitor/utils/kubernetes.py",
        "KubernetesNodeJsonParser",
        env,
        {"status", "node_ip", "role_list", "service_status", "taints", "taint_labels"},
        bases=True,
    )
    load(
        "bkmonitor/utils/kubernetes.py",
        "KubernetesPodJsonParser",
        env,
        {"status", "pod_ip", "node_ip", "image_list", "restart_count", "ready_total", "ready_count", "service_status"},
        bases=True,
    )
    # Resource quantities are verified separately; this test focuses on reader ownership/streaming.
    env["KubernetesPodJsonParser"].resources = property(
        lambda self: {"requests_cpu": 0, "limits_cpu": 0, "requests_memory": 0, "limits_memory": 0}
    )
    return env


class TestBcsSyncReaders(unittest.TestCase):
    def setUp(self):
        self.env = parsers()
        self.fetch = Mock(side_effect=AssertionError("whole-resource fetch is forbidden"))
        self.pages = Mock()
        self.env.update(
            {
                "api": SimpleNamespace(bcs_storage=SimpleNamespace(fetch=self.fetch, fetch_iterator=self.pages)),
                "collections": collections,
                "get_bytes_unit_human_readable": str,
            }
        )
        self.params = {"bk_tenant_id": "tenant", "bcs_cluster_id": "cluster"}

    @staticmethod
    def node(name, role=None, ip="::1", ready=True, unschedulable=False):
        return {
            "metadata": {"name": name, "labels": {"node-role.kubernetes.io/" + role: ""} if role else {}},
            "status": {
                "addresses": [{"type": "InternalIP", "address": ip}],
                "conditions": [{"type": "Ready", "status": str(ready)}],
            },
            "spec": {"unschedulable": unschedulable},
        }

    def resource(self, name, methods):
        return load("api/kubernetes/default.py", name, self.env, methods)()

    def test_large_count_has_bounded_memory_and_preserves_role_semantics(self):
        self.pages.side_effect = lambda **_: (
            self.node(str(i), "master" if i % 3 == 0 else "control-plane") for i in range(150000)
        )
        resource = self.resource("FetchK8sNodeCountByClusterResource", {"perform_request"})
        tracemalloc.start()
        try:
            result = resource.perform_request(self.params)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(result, {"master_count": 50000, "node_count": 100000})
        self.assertLess(peak, 2 * 1024 * 1024)
        self.pages.assert_called_once_with(
            bk_tenant_id="tenant",
            cluster_id="cluster",
            resource_type="Node",
            field="data.metadata.name,data.metadata.labels",
        )

    def test_count_failure_is_not_a_valid_zero(self):
        resource = self.resource("FetchK8sNodeCountByClusterResource", {"perform_request"})

        def broken(**_):
            yield self.node("first")
            raise RuntimeError("page unavailable")

        self.pages.side_effect = broken
        with self.assertRaisesRegex(RuntimeError, "page unavailable"):
            resource.perform_request(self.params)
        self.pages.side_effect = None
        self.pages.return_value = iter([{}])
        with self.assertRaisesRegex(ValueError, "identity"):
            resource.perform_request(self.params)

    def test_access_ip_filters_and_stops_early(self):
        def nodes(**_):
            yield self.node("not-ready", ready=False)
            yield self.node("disabled", unschedulable=True)
            yield self.node("no-address", ip="")
            yield self.node("ready", ip="selected")
            raise AssertionError("reader must stop after matching node")

        self.pages.side_effect = nodes
        resource = self.resource("FetchK8sNodeAccessIpResource", {"perform_request"})
        self.assertEqual(resource.perform_request(self.params), "selected")

    def test_node_sync_indexes_endpoints_once_and_streams_nodes(self):
        consumed = []

        def pages(**params):
            if params["resource_type"] == "Endpoints":
                yield {"subsets": None}
                yield {
                    "subsets": [
                        {
                            "ports": [{"port": 80}, {"port": 81}],
                            "addresses": [{"nodeName": "first"}, {"nodeName": "first"}, {"nodeName": "second"}],
                        }
                    ]
                }
            else:
                for name in ["first", "second", "last"]:
                    consumed.append(name)
                    yield self.node(name)

        self.pages.side_effect = pages
        self.env["FetchK8sNodeListByClusterResource"] = SimpleNamespace(
            get_node_field=lambda: "node-fields",
            get_pod_count_statistics=Mock(return_value={"::1": 7}),
        )
        reader = load("api/kubernetes/default.py", "iter_k8s_nodes_for_sync", self.env)
        rows = reader("tenant", "cluster")
        first = next(rows)
        self.assertEqual(consumed, ["first"])
        self.assertEqual(first["endpoint_count"], 4)
        self.assertEqual(first["pod_count"], 7)
        self.assertNotIn("node", first)
        self.assertEqual([row["endpoint_count"] for row in rows], [2, 0])
        self.assertEqual([call.kwargs["resource_type"] for call in self.pages.call_args_list], ["Endpoints", "Node"])

    def test_pod_owner_index_is_namespaced_and_uses_no_full_lists(self):
        def pages(**params):
            kind = params["resource_type"]
            if kind == "Node":
                yield self.node("node")
            elif kind == "ReplicaSet":
                for ns in ["a", "b"]:
                    yield {
                        "metadata": {
                            "name": "same",
                            "namespace": ns,
                            "ownerReferences": [{"kind": "Deployment", "name": "deployment-" + ns}],
                        }
                    }
            elif kind == "Pod":
                yield {
                    "metadata": {
                        "name": "pod",
                        "namespace": "b",
                        "ownerReferences": [{"kind": "ReplicaSet", "name": "same"}],
                    },
                    "spec": {},
                    "status": {"phase": "Running", "hostIP": "::1"},
                }

        self.pages.side_effect = pages
        resource = self.resource(
            "FetchK8sPodListByClusterResource",
            {"perform_request", "get_node_field", "get_replica_set_field", "get_job_field", "get_pod_field"},
        )
        rows = list(resource.perform_request({**self.params, "namespace_list": []}))
        self.assertEqual(rows[0]["workload_name"], "deployment-b")
        self.assertEqual(rows[0]["node_name"], "node")
        self.assertEqual(
            [c.kwargs["resource_type"] for c in self.pages.call_args_list], ["Pod", "Node", "ReplicaSet", "Job"]
        )

    def test_namespace_workload_count_does_not_fetch_pods_or_enrich(self):
        self.env["api"].kubernetes = SimpleNamespace(fetch_k8s_workload_type_list=Mock(return_value=["Job", "CronJob"]))
        self.pages.side_effect = lambda **params: iter(
            [
                {"metadata": {"name": params["resource_type"], "namespace": "a"}},
                {"metadata": {"name": "other", "namespace": "b"}},
            ]
        )
        resource = self.resource("FetchK8sWorkloadCountByNamespaceResource", {"perform_request"})
        self.assertEqual(resource.perform_request(self.params), {"a": 2, "b": 2})
        self.assertEqual([c.kwargs["resource_type"] for c in self.pages.call_args_list], ["Job", "CronJob"])

    def test_deepflow_client_pages_and_stops_after_first_ip(self):
        def page(nodes, token):
            return SimpleNamespace(items=nodes, metadata=SimpleNamespace(_continue=token))

        def node(kind, value):
            return SimpleNamespace(status=SimpleNamespace(addresses=[SimpleNamespace(type=kind, address=value)]))

        list_node = Mock(
            side_effect=[page([node("ExternalIP", "ignored")], "next"), page([node("InternalIP", "found")], "more")]
        )
        self.env["BcsKubeClient"] = lambda _: SimpleNamespace(core_api=SimpleNamespace(list_node=list_node))
        handler = load(
            "apm_ebpf/handlers/deepflow.py", "DeepflowHandler", self.env, {"_get_cluster_access_ip_by_client"}
        )()
        self.assertEqual(handler._get_cluster_access_ip_by_client("cluster"), "found")
        self.assertEqual(list_node.call_args_list[0].kwargs, {"limit": 100, "_continue": None})
        self.assertEqual(list_node.call_args_list[1].kwargs, {"limit": 100, "_continue": "next"})


if __name__ == "__main__":
    unittest.main()
