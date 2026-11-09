"""Run real Pod query builders and consumers without application/DB bootstrap."""

from __future__ import annotations

import ast
import copy
import re
import unittest
from collections import defaultdict
from enum import Enum
from json.encoder import encode_basestring
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
META = "packages/monitor_web/k8s/core/meta.py"
PANELS = "packages/monitor_web/scene_view/builtin/kubernetes.py"
RESOURCES = "packages/monitor_web/k8s/resources.py"
CLUSTER = "BCS-K8S-00000"
METRIC = "container_memory_working_set_bytes"


def load(path, namespace, name=None, members=None, bases=None):
    tree = ast.parse((ROOT / path).read_text())
    if name:
        node = next(node for node in tree.body if getattr(node, "name", None) == name)
        if members is not None:
            node.body = [
                child
                for child in node.body
                if getattr(child, "name", None) in members
                or (
                    isinstance(child, ast.Assign)
                    and any(getattr(target, "id", None) in members for target in child.targets)
                )
            ]
        if bases is not None:
            node.bases = [ast.Name(id=base, ctx=ast.Load()) for base in bases]
        tree.body = [node]
    else:
        tree.body = [node for node in tree.body if not isinstance(node, ast.Import | ast.ImportFrom)]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    exec(compile(ast.fix_missing_locations(tree), str(ROOT / path), "exec"), namespace)
    return namespace.get(name)


class Pod:
    def to_meta_dict(self):
        return {"namespace": self.namespace, "pod": self.name}


def builders():
    namespace = {
        "re": re,
        "encode_basestring": encode_basestring,
        "K8sResourceNotFound": ValueError,
        "MultiWorkloadError": ValueError,
        "BCSPod": Pod,
        "cached_property": property,
        "get_interval_number": lambda *_args, **_kwargs: 60,
        "gpu_or": lambda metric, filters: f"{metric}{{{filters}}}",
        "NetworkWithRelation": object,
        "BuiltinProcessor": object,
        "Resource": object,
        "K8sOverviewResource": object,
        "defaultdict": defaultdict,
        "copy": copy,
        "Enum": Enum,
        "_lazy": lambda value: value,
        "_": lambda value: value,
        "FieldError": ValueError,
        "NAMESPACED_RESOURCES": {"pod"},
        "get_federated_resource_scope": Mock(return_value=None),
        "validate_k8s_namespace": lambda namespace: namespace,
    }
    load("bkmonitor/utils/time_tools.py", namespace, "hms_string")
    load("packages/monitor_web/k8s/core/pod_memory.py", namespace)
    load("packages/monitor_web/k8s/core/filters.py", namespace)
    load(META, namespace, "FilterCollection", {"filter_string", "add", "remove"}, bases=[])
    load(
        META,
        namespace,
        "K8sResourceMeta",
        {
            "method",
            "federated_resource_filter",
            "resource_field_list",
            "set_agg_interval",
            "set_agg_method",
            "agg_method",
            "meta_prom_with_container_memory_working_set_bytes",
            "meta_prom_by_sort",
            "get_from_promql",
            "get_resource_name",
            "clean_resource_obj",
            "add_filter",
            "bcs_cluster_id_filter",
            "pod_limits_with_sidecar_expr",
        },
        bases=[],
    )
    load(
        META,
        namespace,
        "K8sPodMeta",
        {
            "resource_field",
            "resource_class",
            "column_mapping",
            "only_fields",
            "pod_memory_usage",
            "tpl_prom_with_nothing",
            "meta_prom_with_kube_pod_memory_requests_ratio",
            "meta_prom_with_kube_pod_memory_limits_ratio",
            "meta_prom_with_kube_pod_container_resource_requests_memory_bytes",
        },
    )
    for name in ("K8sContainerMeta", "K8sWorkloadMeta", "K8sNamespaceMeta"):
        load(META, namespace, name, {"tpl_prom_with_nothing"}, bases=["K8sResourceMeta"])
    load(RESOURCES, namespace, "ListK8SResources", {"perform_request", "add_filter"})
    load(
        RESOURCES,
        namespace,
        "ResourceTrendResource",
        {"perform_request", "build_namespaced_trend_query", "iter_namespaced_trend_series", "get_series_with_promql"},
    )
    load("packages/monitor_web/scene_view/builtin/constants/kubernetes.py", namespace)
    load(
        PANELS,
        namespace,
        "KubernetesBuiltinProcessor",
        {
            "get_panel_default_param",
            "patch_group_panels",
            "pod_memory_panel_target",
            "copy_replace_panels_with_where",
            "get_pod_view_config",
            "get_order",
            "get_order_groups",
            "get_order_item_hidden_by_default",
            "is_panel_in_order_groups",
            "get_metric_prefixes",
            "get_available_metric_list",
            "get_view_id",
            "add_event_panel",
        },
    )
    return namespace


def make_meta(env, cls="K8sPodMeta", **filters):
    meta = env[cls]()
    meta.filter = object.__new__(env["FilterCollection"])
    meta.filter.filters = {}
    meta.bk_biz_id = 2
    meta.bcs_cluster_id = CLUSTER
    meta.method = "sum"
    meta.agg_interval = ""
    for field, value in {"bcs_cluster_id": CLUSTER, "container_exclude": "", **filters}.items():
        meta.filter.add(env["load_resource_filter"](field, value))
    meta.get_from_meta = Mock(return_value=[])
    return meta


def panel_queries(view):
    return {
        panel["id"].rsplit(".", 1)[-1]: panel["targets"][0]["data"]
        for group in view["panels"]
        for panel in group["panels"]
        if panel["type"] == "graph"
    }


class TestPodMemoryQueries(unittest.TestCase):
    def setUp(self):
        self.ns = builders()
        self.meta = make_meta(self.ns, namespace="default", pod="demo-pod", workload="Deployment:demo")
        self.query = Mock(return_value={"series": []})
        self.ns["resource"] = SimpleNamespace(
            grafana=SimpleNamespace(graph_unify_query=self.query),
            k8s=SimpleNamespace(get_scenario_metric=lambda **_: {"unit": "bytes", "name": "memory"}),
        )
        self.ns["load_resource_meta"] = lambda *_: self.meta

    def test_each_gauge_selects_its_own_parent_and_keeps_identity(self):
        for metric in self.ns["POD_MEMORY_METRICS"]:
            with self.subTest(metric=metric):
                query = self.meta.tpl_prom_with_nothing(metric)
                self.assertIn(metric.replace("container_", "pod_"), query)
                self.assertIn('metrics_path="/metrics/cadvisor"', query)
                self.assertIn('container_name!="",container_name!="POD"', query)
                self.assertIn("or on (bcs_cluster_id, namespace, pod_name)", query)
                self.assertEqual(query.count('namespace="default"'), 2)
                self.assertEqual(query.count('workload_name="demo"'), 2)
                self.assertNotIn("> 0", query)
                self.assertNotIn("max(", query)

    def test_total_is_selected_before_each_time_statistic(self):
        for method, function in (("max", "max"), ("min", "min"), ("avg", "avg"), ("sum", "last")):
            self.meta.set_agg_method(method)
            self.meta.set_agg_interval(0, 600)
            query = self.meta.meta_prom_with_container_memory_working_set_bytes
            self.assertTrue(query.startswith(f"{function}_over_time((sum by"))
            self.assertEqual(query.count(f"{function}_over_time"), 1)
            self.assertIn("or on (bcs_cluster_id, namespace, pod_name)", query)

    def test_explicit_container_selection_reads_selected_children_only(self):
        self.meta.add_filter(self.ns["load_resource_filter"]("container", ["main", "sidecar"]))
        for metric in self.ns["POD_MEMORY_METRICS"]:
            query = self.meta.tpl_prom_with_nothing(metric)
            self.assertNotIn("pod_memory_", query)
            self.assertIn('container_name=~"^(main|sidecar)$"', query)
            self.assertIn('namespace="default"', query)

    def test_empty_container_selection_does_not_disable_parent(self):
        self.meta.add_filter(self.ns["load_resource_filter"]("container", []))
        query = self.meta.meta_prom_with_container_memory_working_set_bytes
        self.assertIn("pod_memory_working_set_bytes", query)
        self.assertNotIn('container_name=~"^()$"', query)

    def test_ratio_identity_anchor_uses_selected_usage_and_keeps_denominator(self):
        for kind in ("requests", "limits"):
            query = getattr(self.meta, f"meta_prom_with_kube_pod_memory_{kind}_ratio")
            self.assertEqual(query.count("pod_memory_working_set_bytes"), 2)
            self.assertIn("count by (workload_kind, workload_name, pod_name, namespace)", query)
            self.assertIn("* 0 + 1", query)
            self.assertIn("group_right(workload_kind, workload_name)", query)
            self.assertIn(f"kube_pod_container_resource_{kind}", query)
            if kind == "limits":
                self.assertIn("kube_pod_init_container_resource_limits", query)
                self.assertIn("kube_pod_init_container_status_running", query)

    def test_other_resource_views_and_non_gauges_keep_original_queries(self):
        for cls in ("K8sContainerMeta", "K8sWorkloadMeta", "K8sNamespaceMeta"):
            meta = make_meta(self.ns, cls)
            for metric in self.ns["POD_MEMORY_METRICS"]:
                self.assertNotIn("pod_memory_", meta.tpl_prom_with_nothing(metric))
        for metric in (
            "container_memory_max_usage_bytes",
            "container_memory_failcnt",
            "container_memory_failures_total",
        ):
            self.assertNotIn("pod_memory_", self.meta.tpl_prom_with_nothing(metric))

    def test_list_sort_and_zero_use_real_meta_query(self):
        self.query.return_value = {
            "series": [
                {"dimensions": {"namespace": "default", "pod_name": "zero"}, "datapoints": [[0, 60000]]},
                {"dimensions": {"namespace": "default", "pod_name": "demo-pod"}, "datapoints": [[20, 60000]]},
            ]
        }
        response = self.ns["ListK8SResources"]().perform_request(
            {
                "bk_biz_id": 2,
                "bcs_cluster_id": CLUSTER,
                "with_history": True,
                "resource_type": "pod",
                "query_string": "",
                "filter_dict": {},
                "page": 1,
                "page_size": 2,
                "scenario": "performance",
                "order_by": "desc",
                "column": METRIC,
                "start_time": 0,
                "end_time": 600,
                "method": "max",
            }
        )
        self.assertEqual(
            response,
            {
                "count": 2,
                "items": [
                    {"namespace": "default", "pod": "demo-pod"},
                    {"namespace": "default", "pod": "zero"},
                ],
            },
        )
        query = self.query.call_args.args[0]["query_configs"][0]["promql"]
        self.assertTrue(query.startswith("topk(2, max_over_time((sum by"))
        self.assertIn("pod_memory_working_set_bytes", query)

    def test_real_trend_preserves_namespace_filters_on_each_branch(self):
        self.query.return_value = {
            "series": [
                {"dimensions": {"namespace": ns, "pod_name": "demo-pod"}, "datapoints": [[value, 60000]]}
                for ns, value in (("default", 0), ("other", 20))
            ]
        }
        response = self.ns["ResourceTrendResource"]().perform_request(
            {
                "bk_biz_id": 2,
                "bcs_cluster_id": CLUSTER,
                "resource_type": "pod",
                "scenario": "performance",
                "resource_list": ["default|demo-pod", "other|demo-pod"],
                "start_time": 0,
                "end_time": 600,
                "method": "sum",
                "filter_dict": {},
                "column": METRIC,
            }
        )
        self.assertEqual({line["resource_name"] for line in response}, {"default|demo-pod", "other|demo-pod"})
        self.assertEqual(response[0][METRIC]["datapoints"], [[0, 60000]])
        query = self.query.call_args.args[0]["query_configs"][0]["promql"]
        self.assertIn('namespace="other"', query)
        self.assertEqual(query.count("pod_memory_working_set_bytes"), 2)

    def test_query_failure_is_propagated(self):
        self.query.side_effect = RuntimeError("query failed")
        with self.assertRaisesRegex(RuntimeError, "query failed"):
            self.meta.get_from_promql(0, 600, order_by=f"-{METRIC}")

    def test_count_keeps_the_child_series_count_in_both_consumers(self):
        self.ns["ListK8SResources"]().perform_request(
            {
                "bk_biz_id": 2,
                "bcs_cluster_id": CLUSTER,
                "with_history": True,
                "resource_type": "pod",
                "query_string": "",
                "filter_dict": {},
                "page": 1,
                "page_size": 2,
                "scenario": "performance",
                "order_by": "desc",
                "column": METRIC,
                "start_time": 0,
                "end_time": 600,
                "method": "count",
            }
        )
        query = self.query.call_args.args[0]["query_configs"][0]["promql"]
        self.assertTrue(query.startswith("topk(2, count by"))
        self.assertNotIn("pod_memory_", query)
        self.ns["ResourceTrendResource"]().perform_request(
            {
                "bk_biz_id": 2,
                "bcs_cluster_id": CLUSTER,
                "resource_type": "pod",
                "scenario": "performance",
                "resource_list": ["default|demo-pod"],
                "start_time": 0,
                "end_time": 600,
                "method": "count",
                "filter_dict": {},
                "column": METRIC,
            }
        )
        query = self.query.call_args.args[0]["query_configs"][0]["promql"]
        self.assertIn("count by (workload_kind, workload_name, namespace, pod_name)", query)
        self.assertNotIn("pod_memory_", query)


class TestPodMemoryBuiltinPanels(unittest.TestCase):
    def setUp(self):
        self.ns = builders()
        self.processor = self.ns["KubernetesBuiltinProcessor"]
        self.processor.get_metrics_list = Mock(return_value=list(self.ns["POD_MEMORY_METRICS"]))

    def view(self, order=None):
        return self.processor.get_pod_view_config(
            SimpleNamespace(id="pod", bk_biz_id=2, order=order or []), {"id": "pod"}
        )

    def test_default_fields_ids_and_rss_ratio_meaning_are_preserved(self):
        queries = panel_queries(self.view())
        self.assertIn("container_memory_working_set_bytes", queries)
        self.assertIn("container_memory_rss", queries)
        self.assertNotIn("container_memory_swap", queries)
        for metric in ("container_memory_working_set_bytes", "container_memory_rss"):
            self.assertEqual(queries[metric]["unit"], "bytes")
            config = queries[metric]["query_configs"][0]
            self.assertIn(metric.replace("container_", "pod_"), config["promql"])
            self.assertEqual(config["data_source_label"], "prometheus")
            self.assertEqual(config["interval"], "$interval")
            self.assertIn("$method by ($group_by)", config["promql"])
            self.assertIn("$time_shift", config["promql"])
            self.assertIn("${namespace:regex}", config["promql"])
            self.assertEqual(
                {condition["key"] for condition in config["where"]}, {"bcs_cluster_id", "namespace", "pod_name"}
            )
        for kind in ("requests", "limits"):
            ratio = queries[f"kube_pod_memory_{kind}_ratio"]["query_configs"][0]["promql"]
            self.assertIn("pod_memory_rss", ratio)
            self.assertNotIn("pod_memory_working_set_bytes", ratio)
            self.assertIn(f"kube_pod_container_resource_{kind}_memory_bytes", ratio)
            self.assertIn("sum by (bcs_cluster_id, namespace, pod_name, $group_by)", ratio)
            self.assertIn("group_right(workload_kind, workload_name)", ratio)
            self.assertIn("* 0 + 1", ratio)
            self.assertEqual(queries[f"kube_pod_memory_{kind}_ratio"]["expression"], "A")

    def test_saved_optional_gauge_panels_are_adapted_without_new_defaults(self):
        order = [
            {
                "id": "bk_monitor.time_series.k8s.pod.memory",
                "title": "memory",
                "panels": [
                    {"id": f"bk_monitor.time_series.k8s.pod.{metric}", "title": metric, "hidden": False}
                    for metric in sorted(self.ns["POD_MEMORY_METRICS"])
                ],
            }
        ]
        queries = panel_queries(self.view(order))
        for metric in self.ns["POD_MEMORY_METRICS"]:
            self.assertIn(metric.replace("container_", "pod_"), queries[metric]["query_configs"][0]["promql"])

    def test_overview_rebuilds_scope_and_share_where_is_retained(self):
        view = self.view()
        detail = panel_queries(view)[METRIC]["query_configs"][0]
        overview = panel_queries({"panels": view["overview_panels"]})[METRIC]["query_configs"][0]
        self.assertEqual(len(detail["where"]), 3)
        self.assertEqual(overview["where"], [])
        self.assertNotIn("${namespace:regex}", overview["promql"])
        self.assertIn('metrics_path="/metrics/cadvisor"', overview["promql"])
        self.assertIn("pod_memory_working_set_bytes", overview["promql"])

    def test_explicit_container_and_literal_scope_are_applied(self):
        target = {"query_configs": [{"field": METRIC}]}
        where = [
            {"key": "container_name", "method": "eq", "value": ["main"]},
            {"key": "namespace", "method": "eq", "value": ["demo.v2"]},
        ]
        config = self.processor.pod_memory_panel_target(target, where)["data"]["query_configs"][0]
        self.assertNotIn("pod_memory_", config["promql"])
        self.assertIn('container_name=~"^(main)$"', config["promql"])
        self.assertIn('namespace=~"^(demo\\\\.v2)$"', config["promql"])

    def test_non_pod_builtin_views_keep_structured_targets(self):
        for view_id in ("container", "workload"):
            prefix = f"bk_monitor.time_series.k8s.{view_id}"
            config = {
                "id": view_id,
                "panels": [],
                "order": [
                    {
                        "id": f"{prefix}.memory",
                        "title": "memory",
                        "panels": [
                            {
                                "id": f"{prefix}.{METRIC}",
                                "title": METRIC,
                                "hidden": False,
                            }
                        ],
                    }
                ],
            }
            self.processor.patch_group_panels([], [], config)
            qc = panel_queries(config)[METRIC]["query_configs"][0]
            self.assertEqual(qc["data_source_label"], "bk_monitor")
            self.assertEqual(qc["metrics"][0]["field"], METRIC)

    def test_new_gauges_are_discovered_with_byte_units_and_source_dimensions(self):
        namespace = {"os": __import__("os"), "yaml": yaml}
        load("bkmonitor/utils/k8s_metric.py", namespace)
        with unittest.mock.patch("os.getcwd", return_value=str(ROOT)):
            metrics = namespace["get_built_in_k8s_metrics"]()
        for metric in self.ns["POD_MEMORY_METRICS"]:
            parent = next(item for item in metrics if item["field_name"] == metric.replace("container_", "pod_"))
            self.assertEqual(parent["unit"], "bytes")
            self.assertTrue(
                {"bcs_cluster_id", "namespace", "pod_name", "metrics_path", "node", "endpoint"}
                <= {tag["field_name"] for tag in parent["tag_list"]}
            )


if __name__ == "__main__":
    unittest.main()
