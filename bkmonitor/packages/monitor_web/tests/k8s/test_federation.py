"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bkmonitor.models import BCSCluster, BCSPod, BCSService, BCSWorkload
from bkmonitor.utils.kubernetes import BcsClusterType
from metadata.models import BcsFederalClusterInfo
from monitor_web.k8s.core.federation import get_federated_resource_scope
from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.core.meta import K8sPodMeta, load_resource_meta
from monitor_web.k8s.resources import (
    GetResourceDetail,
    ListK8SResources,
    NamespaceWorkloadOverview,
    ResourceTrendResource,
    WorkloadOverview,
)


class TestFederatedResources(TestCase):
    databases = {"default", "monitor_api"}
    proxy, member_a, member_b, standalone, foreign, removed = (f"BCS-K8S-{number}" for number in range(92001, 92007))

    def setUp(self):
        space_uid = patch("monitor_web.k8s.core.meta.bk_biz_id_to_space_uid", return_value="bkci__example")
        space_uid.start()
        self.addCleanup(space_uid.stop)

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        for cluster_id in (cls.proxy, cls.member_a, cls.member_b, cls.standalone, cls.foreign, cls.removed):
            BCSCluster.objects.create(
                bk_biz_id=3 if cluster_id == cls.foreign else 2,
                bcs_cluster_id=cluster_id,
                created_at=now,
                updated_at=now,
                last_synced_at=now,
                node_count=0,
                cpu_usage_ratio=0,
                memory_usage_ratio=0,
                disk_usage_ratio=0,
            )
        for member, namespaces in (
            (cls.member_a, ["alpha", "shared"]),
            (cls.member_b, ["beta", "shared"]),
            (cls.foreign, ["foreign", "shared"]),
            (cls.removed, ["removed"]),
        ):
            BcsFederalClusterInfo.objects.create(
                fed_cluster_id=cls.proxy,
                host_cluster_id=cls.standalone,
                sub_cluster_id=member,
                fed_namespaces=namespaces,
                is_deleted=member == cls.removed,
            )
        BcsFederalClusterInfo.objects.create(
            bk_tenant_id="other-tenant",
            fed_cluster_id=cls.proxy,
            host_cluster_id=cls.standalone,
            sub_cluster_id=cls.standalone,
            fed_namespaces=["outside-tenant"],
        )
        for cluster, namespace, name in (
            (cls.member_a, "alpha", "alpha-app"),
            (cls.member_a, "beta", "outside-a"),
            (cls.member_b, "beta", "beta-app"),
            (cls.member_b, "alpha", "outside-b"),
            (cls.member_a, "shared", "shared-app"),
            (cls.member_b, "shared", "shared-app"),
            (cls.foreign, "foreign", "foreign-app"),
            (cls.foreign, "shared", "shared-app"),
            (cls.removed, "removed", "removed-app"),
            (cls.standalone, "outside-tenant", "ordinary-app"),
        ):
            common = {
                "bk_biz_id": 3 if cluster == cls.foreign else 2,
                "bcs_cluster_id": cluster,
                "namespace": namespace,
                "name": name,
                "created_at": now,
                "last_synced_at": now,
            }
            BCSWorkload.objects.create(**common, type="Deployment", pod_count=1)
            BCSPod.objects.create(**common, total_container_count=1, ready_container_count=1, restarts=0)

    def list_resources(self, resource_type, **overrides):
        return ListK8SResources()(
            {
                "bk_biz_id": 2,
                "bcs_cluster_id": self.proxy,
                "resource_type": resource_type,
                "scenario": "performance",
                "start_time": 1,
                "end_time": 60,
                "filter_dict": {},
                "page_size": 20,
                "supports_federated_charts": True,
                **overrides,
            }
        )

    def test_lists_and_counts_use_the_same_cluster_namespace_pairs(self):
        namespaces = self.list_resources("namespace")
        self.assertEqual([item["namespace"] for item in namespaces["items"]], ["alpha", "beta", "foreign", "shared"])
        self.assertEqual(namespaces["count"], 4)
        workloads = self.list_resources("workload")
        self.assertEqual(
            {item["workload"] for item in workloads["items"]},
            {"Deployment:alpha-app", "Deployment:beta-app", "Deployment:foreign-app", "Deployment:shared-app"},
        )
        counts = dict(
            WorkloadOverview()({"bk_biz_id": 2, "bcs_cluster_id": self.proxy, "supports_federated_charts": True})
        )
        self.assertEqual(counts["Deployment"], workloads["count"])
        pods = self.list_resources("pod", filter_dict={"namespace": ["alpha"]})
        self.assertEqual(pods, {"count": 1, "items": [{"pod": "alpha-app", "namespace": "alpha"}]})

    def test_ordinary_cluster_uses_its_own_rows(self):
        self.assertIsNone(get_federated_resource_scope(2, self.standalone))
        pods = self.list_resources("pod", bcs_cluster_id=self.standalone)
        self.assertEqual([item["pod"] for item in pods["items"]], ["ordinary-app"])

    def test_proxy_scope_includes_cross_business_members_in_the_same_namespace(self):
        scope = get_federated_resource_scope(2, self.proxy)
        members = set(BCSPod.objects.filter(scope, namespace="shared").values_list("bcs_cluster_id", "bk_biz_id"))
        self.assertEqual(members, {(self.member_a, 2), (self.member_b, 2), (self.foreign, 3)})

    def test_project_member_direct_access_does_not_change_proxy_grant(self):
        for members in ({}, {self.foreign: {"cluster_type": BcsClusterType.SHARED, "namespace_list": []}}):
            clusters = {
                self.proxy: {"cluster_type": BcsClusterType.SHARED, "namespace_list": ["foreign"]},
                **members,
            }
            with patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value=clusters):
                self.assertEqual(
                    self.list_resources("pod", bk_biz_id=-10),
                    {"count": 1, "items": [{"pod": "foreign-app", "namespace": "foreign"}]},
                )

    def test_empty_proxy_namespace_grant_does_not_expand_members(self):
        clusters = {self.proxy: {"cluster_type": BcsClusterType.SHARED, "namespace_list": []}}
        with patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value=clusters):
            self.assertEqual(self.list_resources("pod", bk_biz_id=-10), {"count": 0, "items": []})

    def test_removed_members_keep_historical_metrics_but_not_current_metadata(self):
        series = [{"dimensions": {"namespace": "removed", "pod_name": "removed-app"}, "datapoints": [[7, 60000]]}]
        with patch(
            "monitor_web.grafana.resources.unify_query.GraphUnifyQueryResource.perform_request",
            return_value={"series": series},
        ) as query:
            params = {"filter_dict": {"namespace": ["removed"]}}
            self.assertEqual(self.list_resources("pod", **params), {"count": 0, "items": []})
            result = self.list_resources("pod", with_history=True, **params)
            self.assertEqual(result, {"count": 1, "items": [{"pod": "removed-app", "namespace": "removed"}]})
            config = query.call_args.args[0]["query_configs"][0]
            self.assertIn(f'bcs_cluster_id="{self.proxy}"', config["promql"])
            self.assertIn('namespace="removed"', config["promql"])
            self.assertNotIn("required_promql_match", config)

    def test_legacy_chart_client_does_not_get_expanded_resources(self):
        self.assertEqual(self.list_resources("pod", supports_federated_charts=False), {"count": 0, "items": []})

    def test_pod_options_deduplicate_before_pagination(self):
        pods = self.list_resources("pod", filter_dict={"namespace": ["shared"]}, page_size=1)
        self.assertEqual(pods, {"count": 1, "items": [{"pod": "shared-app", "namespace": "shared"}]})

    def test_history_and_trend_escape_filter_values_and_use_existing_space_routing(self):
        metric = "container_memory_working_set_bytes"
        injected_namespace = (
            'alpha"}) or count by (namespace,pod_name) ('
            + metric
            + '{namespace="foreign"}) or count by (namespace,pod_name) ('
            + metric
            + '{namespace="alpha'
        )
        with (
            patch("monitor_web.grafana.resources.unify_query.GraphUnifyQueryResource.get_metric_info", return_value=[]),
            patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway"),
            patch(
                "api.unify_query.default.QueryDataByPromqlResource.perform_request", return_value={"series": []}
            ) as query,
        ):
            self.list_resources(
                "pod",
                with_history=True,
                method="count",
                column=metric,
                filter_dict={"namespace": [injected_namespace]},
            )
            history_config = query.call_args.args[0]
            ResourceTrendResource()(
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": self.proxy,
                    "resource_type": "pod",
                    "resource_list": ["alpha|app"],
                    "column": metric,
                    "method": "count",
                    "start_time": 1,
                    "end_time": 60,
                    "filter_dict": {"namespace": [injected_namespace]},
                }
            )
            trend_config = query.call_args.args[0]
        for config in (history_config, trend_config):
            self.assertFalse(config.get("match"))
            self.assertEqual(config["bk_biz_ids"], ["2"])
            self.assertIs(config["is_verify_dimensions"], False)
            self.assertIn(f"namespace={json.dumps(injected_namespace)}", config["promql"])

    def test_filter_values_cannot_end_promql_string_literals(self):
        payload = 'value/资源"} or outside{label="\\\n'
        for resource_type in ("namespace", "pod", "container", "node", "service", "ingress", "workload"):
            for fuzzy in (False, True):
                with self.subTest(resource_type=resource_type, fuzzy=fuzzy):
                    text = load_resource_filter(resource_type, payload, fuzzy=fuzzy).filter_string()
                    literal = text.split("=", 1)[1].lstrip("~")
                    self.assertNotIn(r"\/", literal)
                    expected = payload.strip() if resource_type == "workload" else payload
                    if fuzzy and resource_type != "workload":
                        expected = f"({expected})"
                    self.assertEqual(json.loads(literal), expected)
        text = load_resource_filter("namespace", [payload, "valid"]).filter_string()
        self.assertTrue(json.loads(text.split("=~", 1)[1]).startswith("^("))

    def test_node_and_cluster_queries_keep_their_namespace_free_scope(self):
        for resource_type in ("node", "cluster"):
            with (
                self.subTest(resource_type=resource_type),
                patch(
                    "monitor_web.grafana.resources.unify_query.GraphUnifyQueryResource.perform_request",
                    return_value={"series": []},
                ) as query,
            ):
                meta = load_resource_meta(resource_type, 2, self.proxy)
                meta.get_from_promql(1, 60, order_by="node_cpu_seconds_total")
                ResourceTrendResource().get_series_with_promql("node_cpu_seconds_total", 1, 60, 2)
                self.assertEqual(query.call_count, 2)
                for call in query.call_args_list:
                    self.assertNotIn("required_promql_match", call.args[0]["query_configs"][0])

    def test_workload_tree_total_matches_namespace_counts(self):
        now = timezone.now()
        for cluster, namespace, name in (
            (self.member_b, "beta", "alpha-app"),
            (self.member_a, "alpha", "another-app"),
        ):
            BCSWorkload.objects.create(
                bk_biz_id=2,
                bcs_cluster_id=cluster,
                namespace=namespace,
                name=name,
                type="Deployment",
                created_at=now,
                last_synced_at=now,
                pod_count=1,
            )

        overview = NamespaceWorkloadOverview()
        for query, expected in (("", 6), ("alpha", 2), ("beta", 1)):
            with self.subTest(query=query):
                result = overview(
                    {
                        "bk_biz_id": 2,
                        "bcs_cluster_id": self.proxy,
                        "query_string": query,
                        "supports_federated_charts": True,
                    }
                )
                self.assertEqual(result["workload_count"], expected)
                self.assertEqual(sum(item["workload_count"] for item in result["items"]), expected)

    def test_pod_trends_keep_namespaces_separate_and_preserve_unique_legacy_keys(self):
        column = "container_cpu_usage_seconds_total"
        series = [
            {"dimensions": {"namespace": namespace, "pod_name": pod}, "datapoints": [[value, 60]]}
            for namespace, pod, value in (("alpha", "app", 1), ("beta", "app", 2), ("alpha", "legacy", 3))
        ]
        with patch.object(ResourceTrendResource, "get_series_with_promql", return_value=series) as query:
            trends = ResourceTrendResource()(
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": self.proxy,
                    "resource_type": "pod",
                    "resource_list": ["alpha|app", "beta|app", "app", "legacy"],
                    "column": column,
                    "method": "sum",
                    "start_time": 1,
                    "end_time": 60,
                    "filter_dict": {},
                }
            )
        promql = query.call_args.args[0]
        self.assertIn('namespace="alpha",pod_name="app"', promql)
        self.assertIn('namespace="beta",pod_name="app"', promql)
        self.assertEqual(
            {item["resource_name"]: item[column]["datapoints"] for item in trends},
            {"alpha|app": [[1, 60]], "beta|app": [[2, 60]], "legacy": [[3, 60]]},
        )

    def test_project_uses_proxy_namespaces_without_member_access(self):
        space_clusters = {
            self.proxy: {"cluster_type": BcsClusterType.SHARED, "namespace_list": ["alpha", "foreign", "shared"]},
        }
        with (
            patch("monitor_web.k8s.core.meta.bk_biz_id_to_space_uid", return_value="bkci__example"),
            patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value=space_clusters),
            patch("monitor_web.k8s.resources.validate_bk_biz_id", return_value=2),
        ):
            pods = self.list_resources("pod", bk_biz_id=-10, filter_dict={"namespace": ["beta"]})
            self.assertEqual(pods, {"count": 0, "items": []})
            namespace_overview = NamespaceWorkloadOverview()(
                {"bk_biz_id": -10, "bcs_cluster_id": self.proxy, "supports_federated_charts": True}
            )
            self.assertEqual(
                [item["namespace"] for item in namespace_overview["items"]], ["alpha", "foreign", "shared"]
            )
            self.assertEqual(namespace_overview["workload_count"], 3)

            def query_history(meta, *_args):
                self.assertIn('namespace=~"^(alpha|foreign|shared)$"', meta.filter.filter_string())
                return []

            with patch.object(K8sPodMeta, "get_from_promql", autospec=True, side_effect=query_history):
                pods = self.list_resources("pod", bk_biz_id=-10, with_history=True)
                self.assertEqual({item["pod"] for item in pods["items"]}, {"alpha-app", "foreign-app", "shared-app"})

    def test_unauthorized_proxy_has_no_member_metadata(self):
        self.assertEqual(self.list_resources("pod", bk_biz_id=3), {"count": 0, "items": []})
        with patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value={}):
            self.assertEqual(self.list_resources("pod", bk_biz_id=-10), {"count": 0, "items": []})

    def test_detail_uses_a_unique_permitted_physical_instance(self):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": self.proxy,
            "resource_type": "workload",
            "supports_federated_charts": True,
        }
        with patch.object(BCSWorkload, "render", autospec=True, return_value=[]) as detail:
            get_detail = GetResourceDetail()
            get_detail({**params, "namespace": "alpha", "workload_type": "Deployment", "workload_name": "alpha-app"})
            self.assertEqual(detail.call_args.args[0].bcs_cluster_id, self.member_a)
            detail.reset_mock()
            for namespace, name in (("removed", "removed-app"), ("beta", "outside-a")):
                result = get_detail(
                    {**params, "namespace": namespace, "workload_type": "Deployment", "workload_name": name}
                )
                self.assertEqual(result, [])
            detail.assert_not_called()

    def test_replicated_detail_preserves_common_and_member_specific_fields(self):
        def render(item, _biz_id, _mode):
            fields = [
                {
                    "key": "name",
                    "name": "Name",
                    "type": "link",
                    "value": {"value": item.name, "url": item.bcs_cluster_id},
                },
                {"key": "labels", "name": "Labels", "type": "kv", "value": {"app": "shared"}},
                {"key": "status", "name": "Status", "type": "status", "value": item.bcs_cluster_id},
                {"key": "resource_usage_cpu", "name": "CPU", "type": "string", "value": item.bk_biz_id},
            ]
            if item.bcs_cluster_id == self.member_a:
                fields.append({"key": "images", "name": "Images", "type": "list", "value": ["example.test/image"]})
            return fields

        with (
            patch.object(BCSPod, "render", autospec=True, side_effect=render) as render_mock,
            patch.object(GetResourceDetail, "get_pod_resource_relation", return_value=[]) as relation,
        ):
            result = GetResourceDetail()(
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": self.proxy,
                    "resource_type": "pod",
                    "namespace": "shared",
                    "pod_name": "shared-app",
                    "supports_federated_charts": True,
                }
            )
        self.assertEqual(render_mock.call_count, 3)
        relation.assert_called_once()
        by_key = {field["key"]: field for field in result}
        self.assertEqual(by_key["name"]["type"], "string")
        self.assertEqual(by_key["name"]["value"], "shared-app")
        self.assertEqual(by_key["labels"]["value"], {"app": "shared"})
        self.assertFalse(any(key.startswith("resource_usage_cpu") for key in by_key))
        for cluster_id in (self.member_a, self.member_b, self.foreign):
            field = by_key[f"status|{cluster_id}"]
            self.assertEqual(
                (field["name"], field["type"], field["value"]), (f"Status ({cluster_id})", "status", cluster_id)
            )
        self.assertEqual(by_key[f"images|{self.member_a}"]["value"], ["example.test/image"])
        self.assertNotIn("images", by_key)

    def test_federated_service_detail_keeps_monitor_status_refresh(self):
        now = timezone.now()
        BCSService.objects.create(
            bk_biz_id=3,
            bcs_cluster_id=self.foreign,
            namespace="foreign",
            name="service-app",
            created_at=now,
            last_synced_at=now,
        )
        with (
            patch("monitor_web.scene_view.resources.kubernetes.GetKubernetesService.refresh_monitor_status") as refresh,
            patch.object(BCSService, "render", autospec=True, return_value=[]) as render,
        ):
            GetResourceDetail()(
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": self.proxy,
                    "resource_type": "service",
                    "namespace": "foreign",
                    "service_name": "service-app",
                    "supports_federated_charts": True,
                }
            )
            self.assertEqual(refresh.call_args.args[0].bcs_cluster_id, self.foreign)
            self.assertEqual(render.call_args.args[1:], (2, "detail"))

    def test_cross_business_detail_uses_proxy_authorization_and_physical_metadata(self):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": self.proxy,
            "resource_type": "pod",
            "namespace": "foreign",
            "pod_name": "foreign-app",
            "supports_federated_charts": True,
        }
        clusters = {self.proxy: {"cluster_type": BcsClusterType.SHARED, "namespace_list": ["foreign"]}}
        for page_biz in (2, -10):
            with (
                self.subTest(page_biz=page_biz),
                patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value=clusters),
                patch.object(BCSPod, "render", autospec=True, return_value=[]) as render,
                patch.object(GetResourceDetail, "get_pod_resource_relation", return_value=[]) as relation,
            ):
                GetResourceDetail()({**params, "bk_biz_id": page_biz})
                item, request_biz, mode = render.call_args.args
                self.assertEqual(
                    (item.bk_biz_id, item.bcs_cluster_id, request_biz, mode), (3, self.foreign, page_biz, "detail")
                )
                self.assertEqual(
                    relation.call_args.args,
                    (page_biz, {"namespace": "foreign", "bcs_cluster_id": self.proxy, "pod": "foreign-app"}, "service"),
                )

    def test_federated_detail_preserves_scene_validation_with_proxy_identity(self):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": self.proxy,
            "resource_type": "pod",
            "namespace": "foreign",
            "pod_name": "foreign-app",
            "supports_federated_charts": True,
        }
        with (
            patch(
                "monitor_web.scene_view.resources.kubernetes.GetKubernetesPod.validate_request_data",
                side_effect=ValueError("share denied"),
            ) as validate,
            patch.object(BCSPod, "render") as render,
        ):
            with self.assertRaisesMessage(ValueError, "share denied"):
                GetResourceDetail()(params)
            self.assertEqual(validate.call_args.args[0]["bcs_cluster_id"], self.proxy)
            self.assertEqual(validate.call_args.args[0]["bk_biz_id"], 2)
            render.assert_not_called()
