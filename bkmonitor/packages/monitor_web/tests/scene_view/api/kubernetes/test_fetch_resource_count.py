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
    FetchK8sNamespaceListResource,
)
from core.drf_resource import api


class TestFetchResourceCount:
    @pytest.mark.django_db
    @pytest.mark.parametrize(
        'params, count',
        [
            [{"bk_biz_id": 2}, 2],
            [{"bk_biz_id": 999}, 0],
            [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": -3}, 2],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}, 1],
        ],
    )
    def test_fetch_cluster_count(
        self,
        params,
        count,
        monkeypatch,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        params["resource_type"] = "cluster"
        assert api.kubernetes.fetch_resource_count(params) == count

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        'params, count',
        [
            [{"bk_biz_id": 2}, 2],
            [{"bk_biz_id": 999, "bcs_cluster_id": "BCS-K8S-00000"}, 0],
            [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}, 2],
            [{"bk_biz_id": 2, "bcs_cluster_id": "unknown"}, 0],
            [{"bk_biz_id": -3}, 2],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}, 2],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}, 0],
        ],
    )
    def test_fetch_namespace_count(
        self,
        params,
        count,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_namespace,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_get_related_bcs_space,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sNamespaceListResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        params["resource_type"] = "namespace"
        assert api.kubernetes.fetch_resource_count(params) == count

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        'params, count',
        [
            [{"bk_biz_id": 2}, 2],
            [{"bk_biz_id": 999}, 0],
            [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": 2, "bcs_cluster_id": "unknown"}, 0],
            [{"bk_biz_id": -3}, 1],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}, 0],
        ],
    )
    def test_fetch_node_count(
        self, params, count, monkeypatch_get_space_detail, monkeypatch_get_clusters_by_space_uid, add_bcs_nodes
    ):
        params["resource_type"] = "node"
        assert api.kubernetes.fetch_resource_count(params) == count

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        'params, count',
        [
            [{"bk_biz_id": 2}, 2],
            [{"bk_biz_id": 999}, 0],
            [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}, 2],
            [{"bk_biz_id": 2, "bcs_cluster_id": "unknown"}, 0],
            [{"bk_biz_id": -3}, 3],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}, 2],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}, 1],
        ],
    )
    def test_fetch_pod_count(
        self, params, count, monkeypatch_get_space_detail, monkeypatch_get_clusters_by_space_uid, add_bcs_pods
    ):
        params["resource_type"] = "pod"
        assert api.kubernetes.fetch_resource_count(params) == count

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        'params, count',
        [
            [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00000"}, 1],
            [{"bk_biz_id": -3, "bcs_cluster_id": "BCS-K8S-00002"}, 0],
        ],
    )
    def test_fetch_master_node_count(
        self, params, count, monkeypatch_get_space_detail, monkeypatch_get_clusters_by_space_uid, add_bcs_nodes
    ):
        params["resource_type"] = "master_node"
        assert api.kubernetes.fetch_resource_count(params) == count
