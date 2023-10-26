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

from bkmonitor.models import BCSContainer
from core.testing import assert_list_contains


class TestBCSContainer:
    @pytest.mark.django_db
    def test_sync_resource_usage(
        self,
        add_bcs_containers,
        monkeypatch_kubernetes_fetch_container_usage,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        bcs_cluster_id = "BCS-K8S-00000"
        bk_biz_id = 2

        BCSContainer.sync_resource_usage(bk_biz_id, bcs_cluster_id)

        actual = [model_to_dict(model) for model in BCSContainer.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'image': 'host/namespace/apisix:latest',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'apisix',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-0',
                'resource_limits_cpu': 8.0,
                'resource_limits_memory': 8589934592,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 536870912,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'status': 'running',
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'image': 'host/namespace/gateway-discovery:latest',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'gateway-discovery',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-0',
                'resource_limits_cpu': 2.0,
                'resource_limits_memory': 1073741824,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 536870912,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'status': 'running',
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'image': 'docker.io/host/etcd:latest',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'etcd',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-etcd-0',
                'resource_limits_cpu': 0.0,
                'resource_limits_memory': 0,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 0,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'status': 'running',
                'workload_name': 'api-gateway-etcd',
                'workload_type': 'StatefulSet',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'deleted_at': None,
                'image': 'docker.io/host/etcd:latest',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'etcd',
                'namespace': 'namespace_a',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-etcd-0',
                'resource_limits_cpu': 0.0,
                'resource_limits_memory': 0,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 0,
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'status': 'running',
                'workload_name': 'api-gateway-etcd',
                'workload_type': 'StatefulSet',
            },
        ]
        assert_list_contains(actual, expect)
