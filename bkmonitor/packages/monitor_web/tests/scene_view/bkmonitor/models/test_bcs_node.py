# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import pytest
from django.forms.models import model_to_dict

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sBkmMetricbeatEndpointUpResource,
    FetchK8sCloudIdByClusterResource,
    FetchK8sNodeListByClusterResource,
)
from bkmonitor.models import BCSNode
from core.testing import assert_list_contains


class TestBCSNode:
    @pytest.mark.django_db
    def test_load_list_from_api(
        self, monkeypatch, monkeypatch_bcs_storage_fetch_node_and_endpoints, add_bcs_cluster_info
    ):
        monkeypatch.setattr(FetchK8sNodeListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sCloudIdByClusterResource, "cache_type", None)

        models = BCSNode.load_list_from_api(
            {
                "BCS-K8S-00000": 2,
            }
        )
        assert len(models) == 2
        assert models[0].cloud_id == '0'

    @pytest.mark.django_db
    def test_sync_resource_usage(
        self,
        monkeypatch,
        add_bcs_nodes,
        monkeypatch_kubernetes_fetch_node_cpu_usage,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        monkeypatch.setattr(FetchK8sBkmMetricbeatEndpointUpResource, "cache_type", None)

        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"

        BCSNode.sync_resource_usage(bk_biz_id, bcs_cluster_id)

        actual = [model_to_dict(model) for model in BCSNode.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'cloud_id': '',
                'deleted_at': None,
                'endpoint_count': 19,
                'ip': '1.1.1.1',
                'labels': [],
                'monitor_status': 'success',
                'name': 'master-1-1-1-1',
                'pod_count': 16,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'roles': 'control-plane,master',
                'status': 'Ready',
                'taints': '',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00001',
                'bk_biz_id': 2,
                'bk_host_id': None,
                'cloud_id': '',
                'deleted_at': None,
                'endpoint_count': 19,
                'ip': '2.2.2.2',
                'labels': [],
                'monitor_status': 'success',
                'name': 'node-2-2-2-2',
                'pod_count': 16,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'roles': '',
                'status': 'Ready',
                'taints': '',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'cloud_id': '',
                'deleted_at': None,
                'endpoint_count': 19,
                'ip': '2.2.2.2',
                'labels': [],
                'monitor_status': 'success',
                'name': 'node-2-2-2-2',
                'pod_count': 16,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'roles': '',
                'status': 'Ready',
                'taints': '',
            },
        ]
        assert_list_contains(actual, expect)
