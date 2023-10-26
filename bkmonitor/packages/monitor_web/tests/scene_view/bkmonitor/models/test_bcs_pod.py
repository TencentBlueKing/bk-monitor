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
from api.kubernetes.default import FetchK8sPodListByClusterResource
from bkmonitor.models.bcs_pod import BCSPod
from core.testing import assert_list_contains


class TestBCSPod:
    def test_load_list_from_api(self, monkeypatch, monkeypatch_bcs_storage_fetch_pod_list_by_cluster):
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        models = BCSPod.load_list_from_api(
            {
                "BCS-K8S-00000": 2,
            }
        )
        actual = [model_to_dict(model) for model in models]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'created_at': '2022-01-01T00:00:00Z',
                'deleted_at': None,
                'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
                'labels': [],
                'monitor_status': '',
                'name': 'api-gateway-0',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_ip': '1.1.1.1',
                'ready_container_count': 2,
                'resource_limits_cpu': 10.0,
                'resource_limits_memory': 9663676416,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 1073741824,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'restarts': 2,
                'status': 'Running',
                'total_container_count': 2,
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'created_at': '2022-01-01T00:00:00Z',
                'deleted_at': None,
                'images': 'host/etcd:latest',
                'labels': [],
                'monitor_status': '',
                'name': 'api-gateway-etcd-0',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_ip': '1.1.1.1',
                'ready_container_count': 1,
                'resource_limits_cpu': 0.0,
                'resource_limits_memory': 0,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 0,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'restarts': 0,
                'status': 'Running',
                'total_container_count': 1,
                'workload_name': 'api-gateway-etcd',
                'workload_type': 'StatefulSet',
            },
        ]
        assert_list_contains(actual, expect)

    @pytest.mark.django_db
    def test_sync_resource_usage(
        self, monkeypatch_kubernetes_fetch_pod_usage, monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up, add_bcs_pods
    ):
        bcs_cluster_id = "BCS-K8S-00000"
        bk_biz_id = 2

        actual = BCSPod.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        assert actual is None

        actual = [model_to_dict(model) for model in BCSPod.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'deleted_at': None,
                'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
                'monitor_status': 'success',
                'name': 'api-gateway-0',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_ip': '1.1.1.1',
                'ready_container_count': 2,
                'resource_limits_cpu': 10.0,
                'resource_limits_memory': 9663676416,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 1073741824,
                'resource_usage_cpu': 0.021,
                'resource_usage_disk': 330514432,
                'resource_usage_memory': 826540032,
                'restarts': 0,
                'status': 'Running',
                'total_container_count': 2,
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'api-gateway-1',
                'namespace': 'bcs-system',
                'node_ip': '1.1.1.1',
                'node_name': 'node-1.1.1.1',
                'pod_ip': '1.1.1.1',
                'ready_container_count': 2,
                'resource_limits_cpu': 10.0,
                'resource_limits_memory': 9663676416,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 1073741824,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'restarts': 0,
                'status': 'Completed',
                'total_container_count': 2,
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'deleted_at': None,
                'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
                'labels': [],
                'monitor_status': 'failed',
                'name': 'api-gateway-2',
                'namespace': 'namespace_a',
                'node_ip': '1.1.1.1',
                'node_name': 'node-1.1.1.1',
                'pod_ip': '2.2.2.2',
                'ready_container_count': 2,
                'resource_limits_cpu': 10.0,
                'resource_limits_memory': 9663676416,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 1073741824,
                'resource_usage_cpu': 0.03,
                'resource_usage_disk': 330514432,
                'resource_usage_memory': 826540032,
                'restarts': 10,
                'status': 'Completed',
                'total_container_count': 2,
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
        ]
        assert_list_contains(actual, expect)
