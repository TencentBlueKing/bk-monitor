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

from api.kubernetes.default import FetchK8sServiceMonitorListByClusterResource
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


@pytest.mark.django_db(databases="__all__")
class TestFetchK8sServiceMonitorListByClusterResource:
    def test_fetch(
        self,
        monkeypatch,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_kubernetes_fetch_k8s_service_monitor_list_by_cluster,
    ):
        monkeypatch.setattr(FetchK8sServiceMonitorListByClusterResource, "cache_type", None)
        bcs_cluster_id = "BCS-K8S-00000"

        actual = api.kubernetes.fetch_k8s_service_monitor_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                "age": translate_timestamp_since("2022-01-01T00:00:00Z"),
                "bcs_cluster_id": "BCS-K8S-00000",
                "created_at": "2022-01-01T00:00:00Z",
                "endpoint_count": 1,
                "label_list": [],
                "labels": {},
                "metric_interval": ["30s"],
                "metric_path": ["/metrics"],
                "metric_port": ["https"],
                "name": "namespace-operator-stack-api-server",
                "namespace": "namespace-operator",
            },
            {
                "age": translate_timestamp_since("2022-01-01T00:00:00Z"),
                "bcs_cluster_id": "BCS-K8S-00000",
                "created_at": "2022-01-01T00:00:00Z",
                "endpoint_count": 1,
                "label_list": [],
                "labels": {},
                "metric_interval": ["30s"],
                "metric_path": ["/metrics"],
                "metric_port": ["http"],
                "name": "namespace-operator-stack-kube-state-metrics",
                "namespace": "namespace-operator",
            },
        ]
        assert actual == expect
