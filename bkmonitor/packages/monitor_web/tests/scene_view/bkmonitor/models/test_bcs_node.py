"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from django.forms.models import model_to_dict
from django.utils import timezone

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sBkmMetricbeatEndpointUpResource,
    FetchK8sCloudIdByClusterResource,
    FetchK8sNodeListByClusterResource,
)
from bkmonitor.models import BCSNode
from core.testing import assert_list_contains


class TestBCSNode:
    @pytest.mark.django_db
    def test_build_promql_param_instance(self, add_bcs_nodes):
        # 输出拼入双引号 PromQL 字符串字面量内的 instance=~""：
        # IPv4 的 . 须转义且反斜杠成对（文本 \\.），否则误匹配任意字符 / 被 PromQL 解析拒绝
        instance = BCSNode.objects.build_promql_param_instance(2, "BCS-K8S-00001")
        assert instance == r"^(2\\.2\\.2\\.2:)"

        # IPv6 维持既有的 \\[x:x::x\\]: 双层转义形态
        BCSNode.objects.create(
            **{
                "bk_biz_id": 2,
                "bcs_cluster_id": "BCS-K8S-00001",
                "created_at": "2022-01-01T00:00:00Z",
                "deleted_at": None,
                "status": "Ready",
                "monitor_status": "success",
                "last_synced_at": timezone.now(),
                "unique_hash": BCSNode.hash_unique_key(2, "BCS-K8S-00001", "node-v6"),
                "name": "node-v6",
                "roles": "",
                "cloud_id": "",
                "ip": "2001:db8::1",
                "endpoint_count": 19,
                "pod_count": 16,
                "taints": "",
            }
        )
        instance = BCSNode.objects.build_promql_param_instance(2, "BCS-K8S-00001")
        assert set(instance[2:-1].split("|")) == {r"2\\.2\\.2\\.2:", r"\\[2001:db8::1\\]:"}

    @pytest.mark.django_db
    def test_load_list_from_api(
        self, monkeypatch, monkeypatch_bcs_storage_fetch_node_and_endpoints, add_bcs_cluster_info
    ):
        monkeypatch.setattr(FetchK8sNodeListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sCloudIdByClusterResource, "cache_type", None)

        models = BCSNode.load_list_from_api(
            {
                "BCS-K8S-00000": 2,
            }
        )
        assert len(models) == 2
        assert models[0].cloud_id == "0"

    @pytest.mark.django_db
    def test_sync_resource_usage(
        self,
        monkeypatch,
        add_bcs_nodes,
        monkeypatch_kubernetes_fetch_node_cpu_usage,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        monkeypatch.setattr(FetchK8sBkmMetricbeatEndpointUpResource, "cache_type", None)

        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"

        BCSNode.sync_resource_usage(bk_biz_id, bcs_cluster_id)

        actual = [model_to_dict(model) for model in BCSNode.objects.all()]
        expect = [
            {
                "bcs_cluster_id": "BCS-K8S-00000",
                "bk_biz_id": 2,
                "cloud_id": "",
                "deleted_at": None,
                "endpoint_count": 19,
                "ip": "1.1.1.1",
                "labels": [],
                "monitor_status": "success",
                "name": "master-1-1-1-1",
                "pod_count": 16,
                "resource_usage_cpu": None,
                "resource_usage_disk": None,
                "resource_usage_memory": None,
                "roles": "control-plane,master",
                "status": "Ready",
                "taints": "",
            },
            {
                "bcs_cluster_id": "BCS-K8S-00001",
                "bk_biz_id": 2,
                "bk_host_id": None,
                "cloud_id": "",
                "deleted_at": None,
                "endpoint_count": 19,
                "ip": "2.2.2.2",
                "labels": [],
                "monitor_status": "success",
                "name": "node-2-2-2-2",
                "pod_count": 16,
                "resource_usage_cpu": None,
                "resource_usage_disk": None,
                "resource_usage_memory": None,
                "roles": "",
                "status": "Ready",
                "taints": "",
            },
            {
                "bcs_cluster_id": "BCS-K8S-00002",
                "bk_biz_id": 100,
                "cloud_id": "",
                "deleted_at": None,
                "endpoint_count": 19,
                "ip": "2.2.2.2",
                "labels": [],
                "monitor_status": "success",
                "name": "node-2-2-2-2",
                "pod_count": 16,
                "resource_usage_cpu": None,
                "resource_usage_disk": None,
                "resource_usage_memory": None,
                "roles": "",
                "status": "Ready",
                "taints": "",
            },
        ]
        assert_list_contains(actual, expect)
