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
from api.kubernetes.default import FetchK8sCloudIdByClusterResource
from core.drf_resource import api

pytestmark = pytest.mark.django_db


class TestFetchK8sCloudIdByClusterResource:
    def test_perform_request(self, monkeypatch):
        monkeypatch.setattr(FetchK8sCloudIdByClusterResource, "cache_type", None)
        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_cloud_id_by_cluster({"bcs_cluster_ids": [bcs_cluster_id]})
        expect = []
        assert actual == expect

    def test_perform_request__cluster_exited(self, monkeypatch, add_bcs_cluster_info):
        monkeypatch.setattr(FetchK8sCloudIdByClusterResource, "cache_type", None)

        actual = api.kubernetes.fetch_k8s_cloud_id_by_cluster()
        expect = [
            {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_cloud_id': 0},
            {'bcs_cluster_id': 'BCS-K8S-00001', 'bk_cloud_id': 0},
        ]
        assert actual == expect

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_cloud_id_by_cluster({"bcs_cluster_ids": [bcs_cluster_id]})
        expect = [
            {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_cloud_id': 0},
        ]
        assert actual == expect
