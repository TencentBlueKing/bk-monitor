"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bkmonitor.models import BCSCluster, BCSPod, BCSWorkload
from bkmonitor.utils.kubernetes import BcsClusterType
from metadata.models import BcsFederalClusterInfo
from monitor_web.k8s.core.federation import get_federated_resource_scope
from monitor_web.k8s.core.meta import K8sPodMeta
from monitor_web.k8s.resources import GetResourceDetail, ListK8SResources, NamespaceWorkloadOverview, WorkloadOverview


class TestFederatedResources(TestCase):
    databases = {"default", "monitor_api"}
    proxy, member_a, member_b, standalone, foreign, removed = (f"BCS-K8S-{number}" for number in range(92001, 92007))

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
            (cls.foreign, ["foreign"]),
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
                **overrides,
            }
        )

    def test_lists_and_counts_use_the_same_cluster_namespace_pairs(self):
        namespaces = self.list_resources("namespace")
        self.assertEqual([item["namespace"] for item in namespaces["items"]], ["alpha", "beta", "shared"])
        self.assertEqual(namespaces["count"], 3)
        workloads = self.list_resources("workload")
        self.assertEqual(
            {item["workload"] for item in workloads["items"]},
            {"Deployment:alpha-app", "Deployment:beta-app", "Deployment:shared-app"},
        )
        counts = dict(WorkloadOverview()({"bk_biz_id": 2, "bcs_cluster_id": self.proxy}))
        self.assertEqual(counts["Deployment"], workloads["count"])
        pods = self.list_resources("pod", filter_dict={"namespace": ["alpha"]})
        self.assertEqual(pods, {"count": 1, "items": [{"pod": "alpha-app", "namespace": "alpha"}]})

    def test_ordinary_cluster_uses_its_own_rows(self):
        self.assertIsNone(get_federated_resource_scope(2, self.standalone))
        pods = self.list_resources("pod", bcs_cluster_id=self.standalone)
        self.assertEqual([item["pod"] for item in pods["items"]], ["ordinary-app"])

    def test_project_scope_limits_lists_counts_and_proxy_history(self):
        space_clusters = {
            self.proxy: {"cluster_type": BcsClusterType.SHARED, "namespace_list": ["alpha", "shared"]},
            self.member_a: {"cluster_type": BcsClusterType.SHARED, "namespace_list": ["alpha", "shared"]},
        }
        with (
            patch("monitor_web.k8s.core.meta.bk_biz_id_to_space_uid", return_value="bkci__example"),
            patch("api.kubernetes.default.GetClusterInfoFromBcsSpaceResource.request", return_value=space_clusters),
            patch("monitor_web.k8s.resources.validate_bk_biz_id", return_value=2),
        ):
            pods = self.list_resources("pod", bk_biz_id=-10, filter_dict={"namespace": ["beta"]})
            self.assertEqual(pods, {"count": 0, "items": []})
            namespace_overview = NamespaceWorkloadOverview()({"bk_biz_id": -10, "bcs_cluster_id": self.proxy})
            self.assertEqual([item["namespace"] for item in namespace_overview["items"]], ["alpha", "shared"])
            self.assertEqual(namespace_overview["workload_count"], 2)

            def query_history(meta, *_args):
                self.assertTrue(meta.filter.filter_string().endswith(',namespace="alpha"'))
                return []

            with patch.object(K8sPodMeta, "get_from_promql", autospec=True, side_effect=query_history):
                pods = self.list_resources("pod", bk_biz_id=-10, with_history=True)
                self.assertEqual({item["pod"] for item in pods["items"]}, {"alpha-app", "shared-app"})

    def test_unauthorized_proxy_skips_history_and_metadata(self):
        with patch.object(K8sPodMeta, "get_from_promql") as query_history:
            self.assertEqual(self.list_resources("pod", bk_biz_id=3, with_history=True), {"count": 0, "items": []})
            query_history.assert_not_called()

    def test_detail_uses_a_unique_permitted_physical_instance(self):
        params = {"bk_biz_id": 2, "bcs_cluster_id": self.proxy, "resource_type": "workload"}
        with patch("monitor_web.scene_view.resources.kubernetes.GetKubernetesWorkload.perform_request") as detail:
            detail.return_value = []
            get_detail = GetResourceDetail()
            get_detail({**params, "namespace": "alpha", "workload_type": "Deployment", "workload_name": "alpha-app"})
            self.assertEqual(detail.call_args.args[0]["bcs_cluster_id"], self.member_a)
            detail.reset_mock()
            for namespace, name in (("shared", "shared-app"), ("beta", "outside-a")):
                result = get_detail(
                    {**params, "namespace": namespace, "workload_type": "Deployment", "workload_name": name}
                )
                self.assertEqual(result, [])
            detail.assert_not_called()
