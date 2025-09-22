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
from django.conf import settings

from api.kubernetes.default import FetchK8sClusterListResource
from core.drf_resource import resource


class TestGetSceneViewListResource:
    @pytest.mark.django_db
    def test_perform_request(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        actual = resource.scene_view.get_scene_view_list({"scene_id": "kubernetes", "type": "overview", "bk_biz_id": 2})
        expect = [
            {'id': 'cluster', 'mode': 'custom', 'name': 'Cluster', 'show_panel_count': False, 'type': ''},
            {'id': 'event', 'mode': 'custom', 'name': 'Event', 'show_panel_count': False, 'type': ''},
            {'id': 'workload', 'mode': 'auto', 'name': 'Workload', 'show_panel_count': False, 'type': ''},
            {'id': 'service', 'mode': 'auto', 'name': 'Service', 'show_panel_count': False, 'type': ''},
            {'id': 'pod', 'mode': 'auto', 'name': 'Pod', 'show_panel_count': False, 'type': ''},
            {'id': 'container', 'mode': 'auto', 'name': 'Container', 'show_panel_count': False, 'type': ''},
            {'id': 'node', 'mode': 'auto', 'name': 'Node', 'show_panel_count': False, 'type': ''},
            {'id': 'service_monitor', 'mode': 'auto', 'name': 'ServiceMonitor', 'show_panel_count': False, 'type': ''},
            {'id': 'pod_monitor', 'mode': 'auto', 'name': 'PodMonitor', 'show_panel_count': False, 'type': ''},
        ]
        assert actual == expect
