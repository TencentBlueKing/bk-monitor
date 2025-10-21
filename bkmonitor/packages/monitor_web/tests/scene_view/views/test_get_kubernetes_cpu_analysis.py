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

from core.drf_resource import resource

pytestmark = pytest.mark.django_db


class TestGetKubernetesCpuAnalysis:
    def test_perform_request(self, monkeypatch_get_kubernetes_cpu_analysis_metrics_value, add_bcs_nodes_only_worker):
        params = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = [
            {'name': 'CPU总核数', 'value': 112},
            {'name': 'CPU request 核数', 'value': 38.18},
            {'name': 'CPU limit 核数', 'value': 282.4},
            {'color': '#6bd58f', 'name': 'CPU预分配率', 'value': '34.09%'},
        ]
        assert actual == expect

    def test_perform_request__ci_space(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_get_kubernetes_cpu_analysis_metrics_value,
        add_bcs_nodes_only_worker,
    ):
        params = {"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = [{'name': 'CPU request 核数', 'value': 38.18}, {'name': 'CPU limit 核数', 'value': 282.4}]
        assert actual == expect

        params = {"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = [
            {'name': 'CPU总核数', 'value': 112},
            {'name': 'CPU request 核数', 'value': 38.18},
            {'name': 'CPU limit 核数', 'value': 282.4},
            {'color': '#6bd58f', 'name': 'CPU预分配率', 'value': '34.09%'},
        ]
        assert actual == expect

    def test_perform_request__requests_cpu_bytes(
        self, monkeypatch_get_kubernetes_cpu_analysis_metrics_value, add_bcs_nodes_only_worker
    ):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "group_by": "namespace",
            "data_type": "percentage-bar",
            "usage_type": "requests_cpu_cores",
            "top_n": 1000,
        }
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = {
            'data': [
                {'name': 'blueking', 'total': 36.85999999999999, 'unit': '核', 'value': 26.88},
                {'name': 'bcs-system', 'total': 36.85999999999999, 'unit': '核', 'value': 4.46},
                {'name': 'bkmonitor-operator', 'total': 36.85999999999999, 'unit': '核', 'value': 2.35},
                {'name': 'kube-system', 'total': 36.85999999999999, 'unit': '核', 'value': 1.55},
                {'name': 'default', 'total': 36.85999999999999, 'unit': '核', 'value': 1.0},
                {'name': 'istio-system', 'total': 36.85999999999999, 'unit': '核', 'value': 0.62},
            ]
        }
        assert actual == expect

    def test_perform_request__limits_cpu_cores(
        self, monkeypatch_get_kubernetes_cpu_analysis_metrics_value, add_bcs_nodes_only_worker
    ):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "group_by": "namespace",
            "data_type": "percentage-bar",
            "usage_type": "limits_cpu_cores",
            "top_n": 1000,
        }
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = {
            'data': [
                {'name': 'blueking', 'total': 281.59999999999997, 'unit': '核', 'value': 196.7},
                {'name': 'bcs-system', 'total': 281.59999999999997, 'unit': '核', 'value': 44},
                {'name': 'bkmonitor-operator', 'total': 281.59999999999997, 'unit': '核', 'value': 21.6},
                {'name': 'default', 'total': 281.59999999999997, 'unit': '核', 'value': 16.6},
                {'name': 'istio-system', 'total': 281.59999999999997, 'unit': '核', 'value': 2},
                {'name': 'kube-system', 'total': 281.59999999999997, 'unit': '核', 'value': 0.7},
            ]
        }
        assert actual == expect

    def test_perform_request_without_bcs_cluster_id(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_get_kubernetes_cpu_analysis_metrics_value,
        add_bcs_nodes_only_worker,
    ):
        params = {"bk_biz_id": 2}
        actual = resource.scene_view.get_kubernetes_cpu_analysis(params)
        expect = [
            {'name': 'CPU总核数', 'value': 205.05},
            {'name': 'CPU request 核数', 'value': 0},
            {'name': 'CPU limit 核数', 'value': 276.56},
            {'color': '#6bd58f', 'name': 'CPU预分配率', 'value': '29.14%'},
        ]
        assert actual == expect
