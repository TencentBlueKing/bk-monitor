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


class TestGetKubernetesDiskAnalysis:
    def test_perform_request(
        self,
        add_bcs_nodes,
        monkeypatch_get_kubernetes_disk_analysis_metrics_value,
    ):
        params = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}
        actual = resource.scene_view.get_kubernetes_disk_analysis(params)
        # 去掉master节点
        expect = []
        assert actual == expect

        params = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00001"}
        actual = resource.scene_view.get_kubernetes_disk_analysis(params)
        expect = [
            {'name': '磁盘总量', 'value': '14168.08G'},
            {'name': '磁盘已使用量', 'value': '3427.49G'},
            {'color': '#6bd58f', 'name': '磁盘使用率', 'value': '24.19%'},
        ]
        assert actual == expect

    def test_perform_request__ci_space(
        self,
        add_bcs_nodes,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_get_kubernetes_disk_analysis_metrics_value,
    ):
        params = {"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}
        actual = resource.scene_view.get_kubernetes_disk_analysis(params)
        expect = []
        assert actual == expect
