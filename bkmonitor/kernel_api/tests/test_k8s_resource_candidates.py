"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

容器资源候选值级联检索（ListK8sResourceCandidatesResource）单测。

覆盖：粒度路由（replica=0 负载必现 / pod 级条件抬档）、namespace 并集兜裸 Pod、
多集群去重与分页、eq/include/query_string 匹配语义、目标维度自身条件忽略、
node_ip 空值排除、共享集群命名空间隔离、serializer 校验。

仅 import kernel_api.resource（避开 kernel_api.views.v4 的 alarm_backends import 链，
见 test_issue_v4.py 的说明）。运行：scripts/local-unittest.sh kernel_api/tests/test_k8s_resource_candidates.py
"""

import pytest
from django.utils import timezone

from bkmonitor.models import BCSContainer, BCSPod, BCSWorkload
from kernel_api.resource.k8s_resource import ListK8sResourceCandidatesResource

pytestmark = pytest.mark.django_db

BIZ = 2
C1 = "BCS-K8S-90001"
C2 = "BCS-K8S-90002"


def make_workload(cluster, namespace, workload_type, name, bk_biz_id=BIZ, pod_count=1):
    now = timezone.now()
    return BCSWorkload.objects.create(
        bk_biz_id=bk_biz_id,
        bcs_cluster_id=cluster,
        type=workload_type,
        name=name,
        namespace=namespace,
        pod_name_list="",
        images="",
        pod_count=pod_count,
        created_at=now,
        last_synced_at=now,
    )


def make_pod(cluster, namespace, name, workload_type="", workload_name="", node_ip=None, bk_biz_id=BIZ):
    now = timezone.now()
    return BCSPod.objects.create(
        bk_biz_id=bk_biz_id,
        bcs_cluster_id=cluster,
        name=name,
        namespace=namespace,
        node_name="node-1",
        node_ip=node_ip,
        workload_type=workload_type,
        workload_name=workload_name,
        total_container_count=1,
        ready_container_count=1,
        images="",
        restarts=0,
        created_at=now,
        last_synced_at=now,
    )


def make_container(cluster, namespace, pod_name, name, workload_type="", workload_name="", node_ip=None, bk_biz_id=BIZ):
    now = timezone.now()
    return BCSContainer.objects.create(
        bk_biz_id=bk_biz_id,
        bcs_cluster_id=cluster,
        name=name,
        namespace=namespace,
        pod_name=pod_name,
        workload_type=workload_type,
        workload_name=workload_name,
        node_ip=node_ip,
        node_name="node-1",
        image="",
        created_at=now,
        last_synced_at=now,
    )


@pytest.fixture
def bcs_resources():
    """两个集群的容器资源快照。

    C1/ns1: Deployment:gamesvr-lobby（1 pod 1 容器）+ Deployment:scaled-zero（replica=0，无 pod/容器行）
    C1/ns2: StatefulSet:db（1 pod 1 容器）
    C1/ns-bare: 裸 Pod（无 ownerReferences，workload 字段为空串，BCSWorkload 无行，node_ip 为 NULL）
    C2/ns1: Deployment:gamesvr-match（1 pod 1 容器）——与 C1 同名命名空间，验证跨集群去重
    """
    make_workload(C1, "ns1", "Deployment", "gamesvr-lobby")
    make_pod(C1, "ns1", "gamesvr-lobby-1", "Deployment", "gamesvr-lobby", node_ip="127.0.1.10")
    make_container(C1, "ns1", "gamesvr-lobby-1", "lobby-main", "Deployment", "gamesvr-lobby", node_ip="127.0.1.10")

    make_workload(C1, "ns1", "Deployment", "scaled-zero", pod_count=0)

    make_workload(C1, "ns2", "StatefulSet", "db")
    make_pod(C1, "ns2", "db-0", "StatefulSet", "db", node_ip="127.0.1.11")
    make_container(C1, "ns2", "db-0", "db-main", "StatefulSet", "db", node_ip="127.0.1.11")

    make_pod(C1, "ns-bare", "bare-pod-1")

    make_workload(C2, "ns1", "Deployment", "gamesvr-match")
    make_pod(C2, "ns1", "gamesvr-match-1", "Deployment", "gamesvr-match", node_ip="127.0.1.12")
    make_container(C2, "ns1", "gamesvr-match-1", "match-main", "Deployment", "gamesvr-match", node_ip="127.0.1.12")


def list_candidates(**kwargs):
    params = {"bk_biz_id": BIZ, "bcs_cluster_ids": [C1], "page": 1, "page_size": 500}
    params.update(kwargs)
    return ListK8sResourceCandidatesResource().request(params)


class TestGrainRouting:
    def test_workload_name_includes_zero_replica(self, bcs_resources):
        """workload 级约束下查 BCSWorkload，replica=0 的负载必须出现在候选中"""
        result = list_candidates(
            resource_type="workload_name",
            conditions=[{"key": "namespace", "method": "eq", "value": ["ns1"]}],
        )
        assert result == {"count": 2, "items": ["gamesvr-lobby", "scaled-zero"]}

    def test_pod_condition_lifts_grain(self, bcs_resources):
        """条件含 pod 级维度时路由到 BCSPod 反查，replica=0 负载（无 pod）正确消失"""
        result = list_candidates(
            resource_type="workload_name",
            conditions=[{"key": "pod_name", "method": "eq", "value": ["gamesvr-lobby-1"]}],
        )
        assert result == {"count": 1, "items": ["gamesvr-lobby"]}

    def test_zero_replica_workload_has_no_pod_candidates(self, bcs_resources):
        result = list_candidates(
            resource_type="pod_name",
            conditions=[{"key": "workload_name", "method": "eq", "value": ["scaled-zero"]}],
        )
        assert result == {"count": 0, "items": []}

    def test_container_grain(self, bcs_resources):
        result = list_candidates(
            resource_type="container_name",
            conditions=[{"key": "workload_type", "method": "eq", "value": ["Deployment"]}],
            bcs_cluster_ids=[C1, C2],
        )
        assert result == {"count": 2, "items": ["lobby-main", "match-main"]}


class TestNamespaceUnion:
    def test_union_covers_bare_pod_namespace(self, bcs_resources):
        """无更细条件时 namespace 候选取 workload ∪ pod 并集，兜住只有裸 Pod 的命名空间"""
        result = list_candidates(resource_type="namespace")
        assert result == {"count": 3, "items": ["ns-bare", "ns1", "ns2"]}

    def test_workload_condition_drops_bare_pod_namespace(self, bcs_resources):
        """带 workload 条件时裸 Pod 命名空间消失（其 workload 字段为空串，被空值排除钉死）"""
        result = list_candidates(
            resource_type="namespace",
            conditions=[{"key": "workload_type", "method": "eq", "value": ["Deployment", "StatefulSet"]}],
        )
        assert result == {"count": 2, "items": ["ns1", "ns2"]}


class TestMultiClusterAndPaging:
    def test_multi_cluster_dedup(self, bcs_resources):
        """同名 namespace 跨集群去重只出现一次"""
        result = list_candidates(resource_type="namespace", bcs_cluster_ids=[C1, C2])
        assert result == {"count": 3, "items": ["ns-bare", "ns1", "ns2"]}

    def test_paging(self, bcs_resources):
        result = list_candidates(
            resource_type="workload_name",
            conditions=[{"key": "namespace", "method": "eq", "value": ["ns1"]}],
            page=2,
            page_size=1,
        )
        assert result == {"count": 2, "items": ["scaled-zero"]}

    def test_unknown_cluster_returns_empty(self, bcs_resources):
        """集群不属于该业务时静默返回空，不报错"""
        result = list_candidates(resource_type="workload_name", bcs_cluster_ids=["BCS-K8S-99999"])
        assert result == {"count": 0, "items": []}


class TestMatching:
    def test_include_condition_or_semantics(self, bcs_resources):
        result = list_candidates(
            resource_type="pod_name",
            conditions=[{"key": "workload_name", "method": "include", "value": ["gamesvr", "db"]}],
            bcs_cluster_ids=[C1, C2],
        )
        assert result == {"count": 3, "items": ["db-0", "gamesvr-lobby-1", "gamesvr-match-1"]}

    def test_query_string_narrows_target(self, bcs_resources):
        result = list_candidates(
            resource_type="pod_name",
            conditions=[{"key": "workload_name", "method": "include", "value": ["gamesvr"]}],
            query_string="match",
            bcs_cluster_ids=[C1, C2],
        )
        assert result == {"count": 1, "items": ["gamesvr-match-1"]}

    def test_self_dimension_condition_ignored(self, bcs_resources):
        """目标维度自身的已选条件不参与过滤，否则多选时候选只剩已选值"""
        result = list_candidates(
            resource_type="workload_name",
            conditions=[
                {"key": "namespace", "method": "eq", "value": ["ns1"]},
                {"key": "workload_name", "method": "eq", "value": ["gamesvr-lobby"]},
            ],
        )
        assert result == {"count": 2, "items": ["gamesvr-lobby", "scaled-zero"]}

    def test_node_ip_excludes_null(self, bcs_resources):
        """裸 Pod 的 node_ip 为 NULL，不出现在候选中"""
        result = list_candidates(resource_type="node_ip")
        assert result == {"count": 2, "items": ["127.0.1.10", "127.0.1.11"]}


class TestSharedClusterIsolation:
    C3 = "BCS-K8S-90003"
    HOST_BIZ = 100

    def test_shared_cluster_only_authorized_namespaces(self, bcs_resources, monkeypatch):
        """BCS 空间（负数 biz）下共享集群只放行授权命名空间的数据。

        共享集群的资源行落在宿主业务 bk_biz_id 下，隔离完全依赖
        filter_by_biz_id 按 (bcs_cluster_id, namespace) 的授权过滤。
        """
        make_workload(self.C3, "ns-auth", "Deployment", "auth-app", bk_biz_id=self.HOST_BIZ)
        make_workload(self.C3, "ns-other", "Deployment", "other-app", bk_biz_id=self.HOST_BIZ)

        from api.kubernetes.default import GetClusterInfoFromBcsSpaceResource

        authorized = {self.C3: {"cluster_type": "shared", "namespace_list": ["ns-auth"]}}
        monkeypatch.setattr(GetClusterInfoFromBcsSpaceResource, "perform_request", lambda _self, params: authorized)

        result = list_candidates(resource_type="workload_name", bk_biz_id=-3, bcs_cluster_ids=[self.C3])
        assert result == {"count": 1, "items": ["auth-app"]}

        result = list_candidates(resource_type="namespace", bk_biz_id=-3, bcs_cluster_ids=[self.C3])
        assert result == {"count": 1, "items": ["ns-auth"]}

    def test_space_without_clusters_returns_empty(self, monkeypatch):
        """名下无集群的 BCS 空间：filter_by_biz_id 抛 EmptyResultSet，接口收敛为空结果"""
        from api.kubernetes.default import GetClusterInfoFromBcsSpaceResource

        monkeypatch.setattr(GetClusterInfoFromBcsSpaceResource, "perform_request", lambda self, params: {})

        result = list_candidates(resource_type="namespace", bk_biz_id=-4, bcs_cluster_ids=["BCS-K8S-90004"])
        assert result == {"count": 0, "items": []}


class TestSerializer:
    def test_invalid_resource_type(self):
        serializer = ListK8sResourceCandidatesResource.RequestSerializer(
            data={"bk_biz_id": BIZ, "bcs_cluster_ids": [C1], "resource_type": "service"}
        )
        assert not serializer.is_valid()
        assert "resource_type" in serializer.errors

    def test_defaults(self):
        serializer = ListK8sResourceCandidatesResource.RequestSerializer(
            data={"bk_biz_id": BIZ, "bcs_cluster_ids": [C1], "resource_type": "namespace"}
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["conditions"] == []
        assert serializer.validated_data["query_string"] == ""
        assert serializer.validated_data["page"] == 1
        assert serializer.validated_data["page_size"] == 500

    def test_empty_condition_value_rejected(self):
        serializer = ListK8sResourceCandidatesResource.RequestSerializer(
            data={
                "bk_biz_id": BIZ,
                "bcs_cluster_ids": [C1],
                "resource_type": "namespace",
                "conditions": [{"key": "workload_name", "method": "eq", "value": []}],
            }
        )
        assert not serializer.is_valid()
