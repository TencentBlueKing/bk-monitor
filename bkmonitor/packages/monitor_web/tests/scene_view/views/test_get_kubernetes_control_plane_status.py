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

CONTROL_PLANE_STATUS = [
    {'label': 'etcd', 'status': 'SUCCESS'},
    {'label': 'kube-apiserver', 'status': 'SUCCESS'},
    {'label': 'kube-controller-manager', 'status': 'SUCCESS'},
    {'label': 'kube-scheduler', 'status': 'SUCCESS'},
    {'label': 'kube-proxy', 'status': 'SUCCESS'},
    {'label': 'Kubelet', 'status': 'SUCCESS'},
]


class TestGetKubernetesControlPlaneStatus:
    @pytest.mark.django_db
    def test_perform_request(self, monkeypatch, monkeypatch_get_kubernetes_control_plane_status):
        actual = resource.scene_view.get_kubernetes_control_plane_status({"bk_biz_id": 2})
        expect = CONTROL_PLANE_STATUS
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(self, monkeypatch, monkeypatch_get_kubernetes_control_plane_status):
        actual = resource.scene_view.get_kubernetes_control_plane_status({"bk_biz_id": -3})
        expect = CONTROL_PLANE_STATUS
        assert actual == expect
