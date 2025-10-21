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

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sClusterListResource,
    FetchK8sNodeListByClusterResource,
)
from core.drf_resource import api


class TestFetchK8sClusterListResource:
    def test_data_type_is_simple(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        actual = api.kubernetes.fetch_k8s_cluster_list(
            {
                "data_type": "simple",
            }
        )
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': '2',
                'cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00000',
                'name': '蓝鲸社区版7.0',
                'project_id': '0000000000',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': '100',
                'cluster_id': 'BCS-K8S-00002',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00002',
                'name': '共享集群',
                'project_id': '2222222222',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_data_type_is_full(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_node_and_endpoints,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sNodeListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        actual = api.kubernetes.fetch_k8s_cluster_list(
            {
                "data_type": "full",
            }
        )
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': '2',
                'cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00000',
                'master_count': 1,
                'name': '蓝鲸社区版7.0',
                'node_count': 1,
                'project_id': '0000000000',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': '100',
                'cluster_id': 'BCS-K8S-00002',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00002',
                'master_count': 1,
                'name': '共享集群',
                'node_count': 1,
                'project_id': '2222222222',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            },
        ]
        assert actual == expect

    def test_filter_biz_id(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        actual = api.kubernetes.fetch_k8s_cluster_list({"bk_biz_id": 2})
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': '2',
                'cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00000',
                'name': '蓝鲸社区版7.0',
                'project_id': '0000000000',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            }
        ]
        assert actual == expect

    def test_filter_biz_id_by_space(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_get_related_bcs_space,
        monkeypatch_get_space_detail,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        actual = api.kubernetes.fetch_k8s_cluster_list({"bk_biz_id": -3})
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': '2',
                'cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00+08:00',
                'environment': 'prod',
                'id': 'BCS-K8S-00000',
                'name': '蓝鲸社区版7.0',
                'project_id': '0000000000',
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
            }
        ]
        assert actual == expect
