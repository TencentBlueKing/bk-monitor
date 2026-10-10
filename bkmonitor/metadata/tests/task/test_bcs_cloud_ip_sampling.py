"""Run with stdlib unittest; load production logic without Django/DB bootstrap."""

import ast
import collections
import itertools
import unittest
from functools import cached_property
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


class TestCloudIpSampling(unittest.TestCase):
    def setUp(self):
        parser_namespace = {"cached_property": cached_property}
        base = load_definition(
            "bkmonitor/utils/kubernetes.py", "KubernetesV1ObjectJsonParser", parser_namespace, {"__init__"}
        )
        parser = load_definition(
            "bkmonitor/utils/kubernetes.py", "KubernetesNodeJsonParser", parser_namespace, {"status", "node_ip"}
        )
        parser.__init__ = base.__init__
        self.fetch = Mock()
        self.api = SimpleNamespace(bcs_storage=SimpleNamespace(fetch_page=self.fetch))
        resource = load_definition(
            "api/kubernetes/default.py",
            "FetchK8sNodeIpListByClusterResource",
            {"api": self.api, "KubernetesNodeJsonParser": parser},
            {"perform_request"},
        )
        self.sample = resource().perform_request
        self.params = {"bk_tenant_id": "tenant", "bcs_cluster_id": "BCS-K8S-00000", "limit": 100}

    @staticmethod
    def node(ip):
        return {"status": {"addresses": [{"type": "InternalIP", "address": ip}]}}

    def test_large_cluster_stops_after_first_page(self):
        def page(params):
            self.assertEqual(params["type"], "Node")
            self.assertEqual(params["field"], "data.status.addresses")
            self.assertEqual(params["bk_tenant_id"], "tenant")
            self.assertEqual(params["cluster_id"], self.params["bcs_cluster_id"])
            self.assertEqual(params["limit"], 100)
            return [self.node(str(i)) for i in range(params["offset"], min(params["offset"] + 100, 150000))]

        self.fetch.side_effect = page
        result = self.sample(self.params)
        self.assertEqual(result, [{"bcs_cluster_id": "BCS-K8S-00000", "node_ip": str(i)} for i in range(100)])
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(self.fetch.call_args.args[0]["offset"], 0)

    def test_missing_addresses_continue_and_stop_at_sample_limit(self):
        first = self.node("::1")
        first["status"]["addresses"].append({"type": "InternalIP", "address": "second"})
        external = {"status": {"addresses": [{"type": "ExternalIP", "address": "external"}]}}
        self.fetch.side_effect = [[{}, external, first], [self.node("::1"), self.node("last"), self.node("unused")]]
        result = self.sample({**self.params, "limit": 3})
        self.assertEqual([item["node_ip"] for item in result], ["::1", "::1", "last"])
        self.assertEqual([call.args[0]["offset"] for call in self.fetch.call_args_list], [0, 3])

    def test_empty_short_page_and_failure(self):
        for page in ([], [{}], [self.node("")], [self.node("one")]):
            with self.subTest(page=page):
                self.fetch.return_value = page
                self.assertEqual(len(self.sample(self.params)), int(page == [self.node("one")]))
        self.fetch.side_effect = RuntimeError("storage unavailable")
        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            self.sample(self.params)

    def test_cloud_update_uses_bounded_sample_and_skips_failed_cluster(self):
        model = Mock(CLUSTER_STATUS_RUNNING="RUNNING", CLUSTER_RAW_STATUS_RUNNING="running")
        model.objects.filter.return_value.values.return_value = [
            {"bk_tenant_id": "tenant", "bk_biz_id": 1, "cluster_id": cluster}
            for cluster in ("BCS-K8S-00000", "BCS-K8S-00001")
        ]
        nodes = Mock(return_value=[[{"bcs_cluster_id": "BCS-K8S-00000", "node_ip": "::1"}], None])
        hosts = Mock(
            return_value=[[SimpleNamespace(bk_biz_id=1, bk_host_innerip="", bk_host_innerip_v6="::1", bk_cloud_id=0)]]
        )
        self.api.kubernetes = SimpleNamespace(fetch_k8s_node_ip_list_by_cluster=SimpleNamespace(bulk_request=nodes))
        self.api.cmdb = SimpleNamespace(get_host_by_ip=SimpleNamespace(bulk_request=hosts))
        update = load_definition(
            "metadata/task/bcs.py",
            "update_bcs_cluster_cloud_id_config",
            {
                "api": self.api,
                "BCSClusterInfo": model,
                "BCS_SYNC_SYNC_CONCURRENCY": 20,
                "CMDB_IP_SEARCH_MAX_SIZE": 100,
                "collections": collections,
                "itertools": itertools,
                "logger": Mock(),
            },
        )
        update()
        self.assertTrue(nodes.call_args.kwargs["ignore_exceptions"])
        self.assertTrue(all(params["limit"] == 100 for params in nodes.call_args.args[0]))
        hosts.assert_called_once_with([{"bk_biz_id": 1, "ips": [{"ip": "::1"}]}])
        model.objects.filter.assert_called_with(cluster_id__in=["BCS-K8S-00000"])
        model.objects.filter.return_value.update.assert_called_once_with(bk_cloud_id=0)
        model.objects.filter.return_value.update.reset_mock()
        hosts.return_value = [[]]
        update()
        model.objects.filter.return_value.update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
