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

from api.kubernetes.default import FetchK8sPodMonitorListByClusterResource
from core.drf_resource import api


@pytest.mark.django_db(databases="__all__")
class TestFetchK8sPodMonitorListByClusterResource:
    def test_fetch(
        self,
        monkeypatch,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_kubernetes_fetch_k8s_monitor_list_by_cluster,
    ):
        monkeypatch.setattr(FetchK8sPodMonitorListByClusterResource, "cache_type", None)
        bcs_cluster_id = "BCS-K8S-00000"

        actual = api.kubernetes.fetch_k8s_pod_monitor_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                "age": None,
                "bcs_cluster_id": "BCS-K8S-00000",
                "created_at": None,
                "endpoint_count": 1,
                "label_list": [{"key": "app.kubernetes.io/name", "value": "pod-monitor"}],
                "labels": {"app.kubernetes.io/name": "pod-monitor"},
                "metric_interval": ["300s"],
                "metric_path": ["/metrics"],
                "metric_port": ["http"],
                "name": "pod-monitor-test",
                "namespace": "default",
            }
        ]
        assert actual == expect
