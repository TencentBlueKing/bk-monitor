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


class TestGetKubernetesMemoryAnalysis:
    def test_perform_request(self, monkeypatch_get_kubernetes_memory_analysis_metrics_value, add_bcs_nodes_only_worker):
        params = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = [
            {'name': '内存总量', 'value': '217.04G'},
            {'name': '内存 request 量', 'value': '53.4G'},
            {'name': '内存 limit 量', 'value': '400.74G'},
            {'color': '#6bd58f', 'name': '内存预分配率', 'value': '24.61%'},
        ]
        assert actual == expect

    def test_perform_request__ci_space(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_get_kubernetes_memory_analysis_metrics_value,
        add_bcs_nodes_only_worker,
    ):
        params = {"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = [{'name': '内存 request 量', 'value': '53.4G'}, {'name': '内存 limit 量', 'value': '400.74G'}]
        assert actual == expect

        params = {"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = [
            {'name': '内存总量', 'value': '217.04G'},
            {'name': '内存 request 量', 'value': '53.4G'},
            {'name': '内存 limit 量', 'value': '400.74G'},
            {'color': '#6bd58f', 'name': '内存预分配率', 'value': '24.61%'},
        ]
        assert actual == expect

    def test_perform_request__requests_memory_bytes(
        self, monkeypatch_get_kubernetes_memory_analysis_metrics_value, add_bcs_nodes_only_worker
    ):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "group_by": "namespace",
            "data_type": "percentage-bar",
            "usage_type": "requests_memory_bytes",
            "top_n": 1000,
        }
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = {
            'data': [
                {'name': 'blueking', 'total': 52.255859375, 'unit': 'G', 'value': 37.47},
                {'name': 'bcs-system', 'total': 52.255859375, 'unit': 'G', 'value': 7.83},
                {'name': 'bkmonitor-operator', 'total': 52.255859375, 'unit': 'G', 'value': 2.69},
                {'name': 'istio-system', 'total': 52.255859375, 'unit': 'G', 'value': 2.19},
                {'name': 'default', 'total': 52.255859375, 'unit': 'G', 'value': 1.5},
                {'name': 'kube-system', 'total': 52.255859375, 'unit': 'G', 'value': 0.58},
            ]
        }
        assert actual == expect

    def test_perform_request__limits_memory_bytes(
        self, monkeypatch_get_kubernetes_memory_analysis_metrics_value, add_bcs_nodes_only_worker
    ):
        params = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "group_by": "namespace",
            "data_type": "percentage-bar",
            "usage_type": "limits_memory_bytes",
            "top_n": 1000,
        }
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = {
            'data': [
                {'name': 'blueking', 'total': 400.498046875, 'unit': 'G', 'value': 322.61},
                {'name': 'bcs-system', 'total': 400.498046875, 'unit': 'G', 'value': 53.0},
                {'name': 'bkmonitor-operator', 'total': 400.498046875, 'unit': 'G', 'value': 13.71},
                {'name': 'default', 'total': 400.498046875, 'unit': 'G', 'value': 8.5},
                {'name': 'istio-system', 'total': 400.498046875, 'unit': 'G', 'value': 2.0},
                {'name': 'kube-system', 'total': 400.498046875, 'unit': 'G', 'value': 0.67},
            ]
        }
        assert actual == expect

    def test_perform_request_without_bcs_cluster_id(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_get_kubernetes_memory_analysis_metrics_value,
        add_bcs_nodes_only_worker,
    ):
        params = {"bk_biz_id": 2}
        actual = resource.scene_view.get_kubernetes_memory_analysis(params)
        expect = [
            {'name': '内存总量', 'value': '404.55G'},
            {'name': '内存 request 量', 'value': '71.52G'},
            {'name': '内存 limit 量', 'value': '267.29G'},
            {'color': '#6bd58f', 'name': '内存预分配率', 'value': '17.68%'},
        ]
        assert actual == expect
