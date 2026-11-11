"""Run real Pod query builders and consumers without application/DB bootstrap."""

from __future__ import annotations

import ast
import copy
import json
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
            "pod_memory_quota_filters",
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
            "get_view_config",
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
    load(
        "packages/monitor_web/scene_view/resources/view.py",
        namespace,
        "GetSceneViewDimensionsResource",
        {"get_metrics", "perform_request"},
        bases=[],
    )
    load(
        "packages/monitor_web/grafana/resources/unify_query.py",
        namespace,
        "GraphUnifyQueryResource",
        {"get_unit"},
        bases=[],
    )
    load("packages/monitor_web/grafana/data_migrate.py", namespace, "BasePanel", bases=[])
    load("packages/monitor_web/grafana/data_migrate.py", namespace, "TimeSeriesPanel")
    namespace["json"] = json
    namespace["DataSourceLabel"] = SimpleNamespace(PROMETHEUS="prometheus")
    load(
        "packages/monitor_web/data_explorer/resources.py",
        namespace,
        "SaveToDashboard",
        {"BK_LOG_SEARCH_GRAFANA_DATA_SOURCE_NAME", "add_target", "get_panel"},
        bases=[],
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


def assert_child_selection(test, query, metric):
    test.assertIn(f"{metric}{{", query)
    test.assertNotIn("pod_memory_", query)
    test.assertNotIn('container_name=""', query)


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

    def test_parent_binds_both_names_and_child_uses_its_original_storage_route(self):
        for metric in self.ns["POD_MEMORY_METRICS"]:
            parent = metric.replace("container_memory_", "pod_memory_", 1)
            with self.subTest(metric=metric):
                query = self.ns["pod_memory_usage"](
                    metric,
                    "",
                    dimensions=("bcs_cluster_id", "namespace", "pod_name"),
                    time_shift="offset 1h",
                )
                self.assertEqual(query.count(f'__name__=~"({parent}|{metric})"'), 1)
                self.assertIn(f'"parent", "__name__", "{parent}"', query)
                self.assertIn(f'{metric}{{container_name!="",container_name!="POD"}}', query)
                self.assertIn("sum by (__name__, bcs_cluster_id, namespace, pod_name)", query)
                self.assertEqual(query.count("offset 1h"), 2)
                self.assertNotIn("{,", query)
                self.assertIn('metrics_path="/metrics/cadvisor"', query)

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
            assert_child_selection(self, query, metric)
            self.assertIn('container_name=~"^(main|sidecar)$"', query)
            self.assertIn('namespace="default"', query)

    def test_empty_container_selection_does_not_disable_parent(self):
        self.meta.add_filter(self.ns["load_resource_filter"]("container", []))
        for metric in (
            "container_memory_working_set_bytes",
            "kube_pod_memory_requests_ratio",
            "kube_pod_memory_limits_ratio",
        ):
            query = getattr(self.meta, f"meta_prom_with_{metric}")
            self.assertIn("pod_memory_working_set_bytes", query)
            self.assertNotIn('container_name=~"^()$"', query)

    def test_nonempty_container_selection_is_kept_in_ratio_quota(self):
        self.meta.add_filter(self.ns["load_resource_filter"]("container", ["main"]))
        for kind in ("requests", "limits"):
            query = getattr(self.meta, f"meta_prom_with_kube_pod_memory_{kind}_ratio")
            assert_child_selection(self, query, "container_memory_working_set_bytes")
            self.assertGreaterEqual(query.count('container_name="main"'), 3)

    def test_ratio_identity_anchor_uses_selected_usage_and_keeps_denominator(self):
        for kind in ("requests", "limits"):
            query = getattr(self.meta, f"meta_prom_with_kube_pod_memory_{kind}_ratio")
            self.assertEqual(query.count('"parent", "__name__", "pod_memory_working_set_bytes"'), 2)
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
        self.assertEqual(query.count('"parent", "__name__", "pod_memory_working_set_bytes"'), 2)

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

    def view(self, order=None, supports_pod_memory_promql=True):
        return self.processor.get_pod_view_config(
            SimpleNamespace(id="pod", bk_biz_id=2, order=order or []),
            {"id": "pod"},
            supports_pod_memory_promql=supports_pod_memory_promql,
        )

    def test_old_clients_keep_structured_detail_and_overview_queries(self):
        view = self.view(supports_pod_memory_promql=False)
        self.assertEqual(view["order"], self.view(supports_pod_memory_promql=True)["order"])
        for panels in (view["panels"], view["overview_panels"]):
            queries = panel_queries({"panels": panels})
            for metric in ("container_memory_working_set_bytes", "container_memory_rss"):
                data = queries[metric]
                self.assertEqual(data["expression"], "A")
                self.assertEqual(data["query_configs"][0]["data_source_label"], "bk_monitor")
                self.assertNotIn("promql", data["query_configs"][0])
                self.assertEqual(data["query_configs"][0]["metrics"][0]["field"], metric)
            for kind in ("requests", "limits"):
                data = queries[f"kube_pod_memory_{kind}_ratio"]
                self.assertEqual(data["expression"], "A/B*100")
                self.assertEqual(len(data["query_configs"]), 2)
                self.assertTrue(all(query["data_source_label"] == "bk_monitor" for query in data["query_configs"]))

    def test_scene_processor_uses_only_explicit_client_capability(self):
        self.processor.load_builtin_views = Mock()
        self.processor.get_view_id = Mock(return_value="kubernetes-pod")
        self.processor.builtin_views = {"kubernetes-pod": {"id": "pod"}}
        self.processor.get_pod_view_config = Mock(side_effect=lambda _view, config, **_kwargs: config)
        for params, supported in (
            (None, False),
            ({}, False),
            ({"supports_pod_memory_promql": False}, False),
            ({"supports_pod_memory_promql": True}, True),
        ):
            self.processor.get_view_config(SimpleNamespace(id="pod"), params)
            self.assertEqual(
                self.processor.get_pod_view_config.call_args.kwargs["supports_pod_memory_promql"], supported
            )

    def test_default_fields_ids_and_rss_ratio_meaning_are_preserved(self):
        queries = panel_queries(self.view())
        self.assertIn("container_memory_working_set_bytes", queries)
        self.assertIn("container_memory_rss", queries)
        self.assertNotIn("container_memory_swap", queries)
        for metric in ("container_memory_working_set_bytes", "container_memory_rss"):
            self.assertEqual(queries[metric]["unit"], "bytes")
            config = queries[metric]["query_configs"][0]
            self.assertIn(metric.replace("container_", "pod_"), config["pod_memory_parent_promql"])
            assert_child_selection(self, config["pod_memory_child_promql"], metric)
            self.assertIn('"$pod_memory_marker"', config["pod_memory_parent_promql"])
            self.assertEqual(config["promql"], config["pod_memory_child_promql"])
            self.assertEqual(config["promql"], config["pod_promql"])
            self.assertNotIn("$pod_memory_marker", config["promql"])
            self.assertNotIn("pod_memory_", config["promql"])
            self.assertEqual(config["metrics"][0]["field"], metric)
            self.assertEqual(config["related_metric_ids"], [f"bk_monitor..{metric}"])
            self.assertEqual(config["data_source_label"], "prometheus")
            self.assertEqual(config["interval"], "$interval")
            self.assertIn("$method by ($group_by)", config["promql"])
            self.assertIn("$time_shift", config["promql"])
            self.assertIn("${namespace:regex}", config["promql"])
            self.assertEqual(
                {condition["key"] for condition in config["where"]}, {"bcs_cluster_id", "namespace", "pod_name"}
            )
        for kind in ("requests", "limits"):
            data = queries[f"kube_pod_memory_{kind}_ratio"]
            ratio = data["query_configs"][0]["pod_memory_parent_promql"]
            self.assertIn("pod_memory_rss", ratio)
            self.assertNotIn("pod_memory_working_set_bytes", ratio)
            self.assertIn(f"kube_pod_container_resource_{kind}_memory_bytes", ratio)
            self.assertIn("sum by (bcs_cluster_id, namespace, pod_name, $group_by)", ratio)
            self.assertIn("group_right(workload_kind, workload_name)", ratio)
            self.assertIn("* 0 + 1", ratio)
            self.assertEqual(queries[f"kube_pod_memory_{kind}_ratio"]["expression"], "A")
            self.assertEqual(
                data["query_configs"][0]["related_metric_ids"],
                ["bk_monitor..container_memory_rss", f"bk_monitor..kube_pod_container_resource_{kind}_memory_bytes"],
            )
            unit = self.ns["GraphUnifyQueryResource"]().get_unit([{"unit": "bytes"}], data)
            self.assertEqual(unit, "none")

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
            self.assertIn(
                metric.replace("container_", "pod_"), queries[metric]["query_configs"][0]["pod_memory_parent_promql"]
            )

    def test_overview_rebuilds_scope_and_share_where_is_retained(self):
        view = self.view()
        detail = panel_queries(view)[METRIC]["query_configs"][0]
        overview = panel_queries({"panels": view["overview_panels"]})[METRIC]["query_configs"][0]
        self.assertEqual(len(detail["where"]), 3)
        self.assertEqual(overview["where"], [])
        self.assertNotIn("${namespace:regex}", overview["promql"])
        self.assertNotIn("${namespace:regex}", overview["pod_promql"])
        self.assertIn('metrics_path="/metrics/cadvisor"', overview["pod_memory_parent_promql"])
        self.assertIn("pod_memory_working_set_bytes", overview["pod_memory_parent_promql"])
        assert_child_selection(self, overview["pod_memory_child_promql"], METRIC)
        for source in ("child", "parent"):
            self.assertIn("${namespace:regex}", detail[f"pod_memory_{source}_promql"])
            self.assertNotIn("${namespace:regex}", overview[f"pod_memory_{source}_promql"])
            self.assertNotIn(f"overview_pod_memory_{source}_promql", overview)
        self.assertEqual(overview["promql"], overview["pod_promql"])

    def test_legacy_templates_survive_graph_query_serializer_with_additional_templates(self):
        from django.conf import settings
        from rest_framework import serializers

        if not settings.configured:
            settings.configure(USE_I18N=False)
        self.ns["serializers"] = serializers
        self.ns["settings"] = SimpleNamespace(SQL_MAX_LIMIT=100)
        self.ns["DataSourceLabel"] = SimpleNamespace(BK_LOG_SEARCH="bk_log_search")
        self.ns["ValidationError"] = ValueError
        query_resource = load(
            "packages/monitor_web/grafana/resources/unify_query.py",
            self.ns,
            "UnifyQueryRawResource",
            {"RequestSerializer"},
            bases=[],
        )
        view = self.view()
        for panels in (view["panels"], view["overview_panels"]):
            for metric in (METRIC, "container_memory_rss", "kube_pod_memory_requests_ratio"):
                config = panel_queries({"panels": panels})[metric]["query_configs"][0]
                self.assertEqual(config["promql"], config["pod_promql"])
                self.assertNotIn("$pod_memory_marker", config["promql"])
                serializer = query_resource.RequestSerializer.QueryConfigSerializer(data=config)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data["promql"], config["promql"])
                self.assertFalse(any("pod_memory_" in key for key in serializer.validated_data))

    def test_detail_and_overview_memory_templates_have_no_empty_matchers(self):
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
        invalid_selectors = []
        covered_fields = set()
        for config in (self.view(), self.view(order)):
            for panels in (config["panels"], config["overview_panels"]):
                for field, data in panel_queries({"panels": panels}).items():
                    if field not in self.ns["POD_MEMORY_METRICS"] and field not in (
                        "kube_pod_memory_requests_ratio",
                        "kube_pod_memory_limits_ratio",
                    ):
                        continue
                    covered_fields.add(field)
                    query = data["query_configs"][0]
                    for variant in ("promql", "pod_promql", "pod_memory_child_promql", "pod_memory_parent_promql"):
                        if re.search(r"\{\s*,|,\s*,", query[variant]):
                            invalid_selectors.append((field, variant, query[variant]))
        self.assertEqual(len(covered_fields), 8)
        self.assertEqual(invalid_selectors, [], "Empty matcher in actual detail/overview memory template")

    def test_explicit_container_and_literal_scope_are_applied(self):
        target = {"query_configs": [{"field": METRIC}]}
        where = [
            {"key": "container_name", "method": "eq", "value": ["main"]},
            {"key": "namespace", "method": "eq", "value": ["demo.v2"]},
        ]
        config = self.processor.pod_memory_panel_target(target, where)["data"]["query_configs"][0]
        assert_child_selection(self, config["pod_memory_child_promql"], METRIC)
        self.assertIn('container_name=~"^(main)$"', config["promql"])
        self.assertIn('namespace=~"^(demo\\\\.v2)$"', config["promql"])
        self.assertEqual(config["pod_promql"], config["promql"])
        self.assertEqual(config["pod_memory_parent_promql"], config["pod_memory_child_promql"])

    def test_container_specific_static_groups_and_filters_keep_children_in_both_variants(self):
        for dimension in ("container_name", "container", "image"):
            for group, where in (
                (["namespace", dimension], []),
                ([], [{"key": dimension, "method": "eq", "value": ["main"]}]),
            ):
                with self.subTest(dimension=dimension, group=group):
                    target = {
                        "query_configs": [
                            {"field": "container_memory_rss", "group": group},
                            {"field": "kube_pod_container_resource_requests_memory_bytes", "group": group},
                        ]
                    }
                    config = self.processor.pod_memory_panel_target(target, where)["data"]["query_configs"][0]
                    self.assertEqual(config["pod_promql"], config["promql"])
                    self.assertEqual(config["pod_memory_parent_promql"], config["pod_memory_child_promql"])
                    assert_child_selection(self, config["pod_memory_child_promql"], "container_memory_rss")
                    self.assertIn("container_memory_rss", config["promql"])

    def test_memory_only_saved_view_retains_container_dimension_candidates(self):
        order = self.view()["order"]
        for group in order:
            for panel in group["panels"]:
                panel["hidden"] = panel["title"] not in ("container_memory_rss", "kube_pod_memory_requests_ratio")
        view = self.view(order)
        self.ns["GetSceneViewResource"] = lambda: SimpleNamespace(request=lambda _: view)
        self.ns["bk_biz_id_to_bk_tenant_id"] = lambda _: "default"
        self.ns["get_process_extra_dimensions"] = lambda *_: {}
        self.ns["addon_top_limit_attributes"] = lambda _: None
        metric = SimpleNamespace(
            result_table_id="",
            dimensions=[{"id": key} for key in ("namespace", "container_name", "container", "image")],
        )
        lookup = Mock(return_value=[metric])
        self.ns["MetricListCache"] = SimpleNamespace(objects=SimpleNamespace(filter=lookup))
        dimensions = self.ns["GetSceneViewDimensionsResource"]().perform_request({"id": "pod", "bk_biz_id": 2})
        self.assertEqual(
            {dimension["id"] for dimension in dimensions}, {"namespace", "container_name", "container", "image"}
        )
        lookup.assert_called_once()
        self.assertEqual(
            set(lookup.call_args.kwargs["metric_field__in"]),
            {"container_memory_rss", "kube_pod_container_resource_requests_memory_bytes"},
        )

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


class TestPodMemoryDashboard(unittest.TestCase):
    def setUp(self):
        self.ns = builders()

    @staticmethod
    def query(unit=None):
        query = {
            "expression": "A",
            "alias": "",
            "function": {},
            "query_configs": [
                {"data_source_label": "prometheus", "data_type_label": "time_series", "promql": METRIC, "interval": 60}
            ],
        }
        if unit is not None:
            query["unit"] = unit
        return query

    def panel(self, queries):
        return (
            self.ns["SaveToDashboard"]
            .get_panel({"name": "Pod memory", "fill": False, "min_y_zero": False, "queries": queries})
            .to_dict()
        )

    def test_native_units_are_preserved_per_query_without_cross_contamination(self):
        queries = [self.query("bytes"), self.query("none"), self.query()]
        original = copy.deepcopy(queries)
        panel = self.panel(queries)
        self.assertEqual([target["refId"] for target in panel["targets"]], ["A", "B", "C"])
        self.assertEqual(
            panel["fieldConfig"]["overrides"],
            [
                {"matcher": {"id": "byFrameRefID", "options": ref}, "properties": [{"id": "unit", "value": unit}]}
                for ref, unit in (("A", "bytes"), ("B", "none"))
            ],
        )
        self.assertNotIn("unit", panel["fieldConfig"]["defaults"])
        self.assertEqual(queries, original)

    def test_legacy_native_requests_without_unit_keep_their_panel_shape(self):
        for unit in (None, ""):
            panel = self.panel([self.query(unit)])
            self.assertEqual(panel["fieldConfig"]["overrides"], [])
            self.assertEqual(panel["targets"][0]["refId"], "A")

    def test_structured_query_retains_metric_metadata_and_native_override_is_isolated(self):
        query = self.query("bytes")
        query["query_configs"] = [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "metrics": [{"field": "container_memory_rss", "method": "SUM", "alias": "A"}],
                "filter_dict": {},
                "functions": [],
                "group_by": ["container_name"],
                "interval": 60,
                "interval_unit": "s",
                "table": "",
                "where": [],
            }
        ]
        panel = self.panel([query, self.query("none")])
        self.assertEqual(panel["targets"][0]["query_configs"][0]["metric_field"], "container_memory_rss")
        self.assertEqual(panel["fieldConfig"]["overrides"][0]["matcher"]["options"], "B")
        self.assertEqual(len(panel["fieldConfig"]["overrides"]), 1)

    def test_panel_override_lists_are_not_shared(self):
        self.panel([self.query("bytes")])
        self.assertEqual(self.panel([self.query()])["fieldConfig"]["overrides"], [])

    def test_save_serializer_retains_explicit_unit_and_accepts_old_payloads(self):
        from django.conf import settings
        from rest_framework import serializers

        if not settings.configured:
            settings.configure(USE_I18N=False)
        self.ns["serializers"] = serializers
        save = load(
            "packages/monitor_web/data_explorer/resources.py",
            self.ns,
            "SaveToDashboard",
            {"BK_LOG_SEARCH_GRAFANA_DATA_SOURCE_NAME", "RequestSerializer", "add_target", "get_panel"},
            bases=[],
        )
        for unit in (None, "bytes", "none"):
            serializer = save.RequestSerializer(
                data={
                    "bk_biz_id": 2,
                    "dashboard_uids": [],
                    "panels": [{"name": "Pod memory", "queries": [self.query(unit)]}],
                }
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            panel_config = serializer.validated_data["panels"][0]
            self.assertEqual(panel_config["queries"][0].get("unit"), unit)
            panel = save.get_panel(panel_config).to_dict()
            self.assertEqual(len(panel["fieldConfig"]["overrides"]), int(unit is not None))


if __name__ == "__main__":
    unittest.main()
