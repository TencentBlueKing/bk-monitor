# -*- coding: utf-8 -*-
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

from api.kubernetes.default import FetchK8sMonitorEndpointList
from core.drf_resource import resource


class TestGetKubernetesServiceMonitorEndpoints:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        monkeypatch,
        monkeypatch_kubernetes_monitor_endpoint_list,
    ):
        monkeypatch.setattr(FetchK8sMonitorEndpointList, "cache_type", None)

        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "bk_biz_id": 2,
            "namespace": 'namespace-operator',
            "name": 'namespace-operator-stack-kubelet',
            "metric_path": "/metrics",
        }
        actual = resource.scene_view.get_kubernetes_service_monitor_endpoints(params)
        expect = [
            {'id': 'http://1.1.1.1:10250/metrics', 'name': 'http://1.1.1.1:10250/metrics'},
            {'id': 'http://2.2.2.2:10250/metrics', 'name': 'http://2.2.2.2:10250/metrics'},
        ]
        assert actual == expect
