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
from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sContainerListByClusterResource,
    FetchK8sPodListByClusterResource,
)
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


class TestFetchK8sContainerListByClusterResource:
    def test_fetch(self, monkeypatch, monkeypatch_bcs_storage_fetch_pod_list_by_cluster):
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sContainerListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"

        actual = api.kubernetes.fetch_k8s_container_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container': {
                    'command': ['date'],
                    'image': 'host/namespace/apisix:latest',
                    'name': 'apisix',
                    'resources': {'limits': {'cpu': '8', 'memory': '8Gi'}, 'requests': {'cpu': '0', 'memory': '512Mi'}},
                },
                'container_name': 'apisix',
                'container_status': {
                    'image': 'host/namespace/apisix:latest',
                    'lastState': {},
                    'name': 'apisix',
                    'ready': True,
                    'restartCount': 1,
                    'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                },
                'container_status_ready': True,
                'created_at': '2022-01-01T00:00:00Z',
                'image': 'host/namespace/apisix:latest',
                'labels': {'app.kubernetes.io/name': 'gateway-discovery'},
                'limits_cpu': 8.0,
                'limits_memory': 8589934592,
                'name': 'apisix',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-0',
                'requests_cpu': 0.0,
                'requests_memory': 536870912,
                'status': 'running',
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
                'workloads': [{'key': 'StatefulSet', 'value': 'api-gateway'}],
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container': {
                    'command': ['date'],
                    'image': 'host/namespace/gateway-discovery:latest',
                    'name': 'gateway-discovery',
                    'resources': {'limits': {'cpu': '2', 'memory': '1Gi'}, 'requests': {'cpu': '0', 'memory': '512Mi'}},
                },
                'container_name': 'gateway-discovery',
                'container_status': {
                    'image': 'host/namespace/gateway-discovery:latest',
                    'lastState': {},
                    'name': 'gateway-discovery',
                    'ready': True,
                    'restartCount': 1,
                    'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                },
                'container_status_ready': True,
                'created_at': '2022-01-01T00:00:00Z',
                'image': 'host/namespace/gateway-discovery:latest',
                'labels': {'app.kubernetes.io/name': 'gateway-discovery'},
                'limits_cpu': 2.0,
                'limits_memory': 1073741824,
                'name': 'gateway-discovery',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-0',
                'requests_cpu': 0.0,
                'requests_memory': 536870912,
                'status': 'running',
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
                'workloads': [{'key': 'StatefulSet', 'value': 'api-gateway'}],
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container': {
                    'image': 'docker.io/host/etcd:latest',
                    'livenessProbe': {
                        'exec': {'command': ['date']},
                        'failureThreshold': 5,
                        'initialDelaySeconds': 60,
                        'periodSeconds': 30,
                        'successThreshold': 1,
                        'timeoutSeconds': 5,
                    },
                    'name': 'etcd',
                    'ports': [
                        {'containerPort': 9012, 'name': 'client', 'protocol': 'TCP'},
                        {'containerPort': 9011, 'name': 'peer', 'protocol': 'TCP'},
                    ],
                    'readinessProbe': {
                        'exec': {'command': ['date']},
                        'failureThreshold': 5,
                        'initialDelaySeconds': 60,
                        'periodSeconds': 10,
                        'successThreshold': 1,
                        'timeoutSeconds': 5,
                    },
                    'resources': {},
                },
                'container_name': 'etcd',
                'container_status': {
                    'image': 'host/etcd:latest',
                    'lastState': {},
                    'name': 'etcd',
                    'ready': True,
                    'restartCount': 0,
                    'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                },
                'container_status_ready': True,
                'created_at': '2022-01-01T00:00:00Z',
                'image': 'docker.io/host/etcd:latest',
                'labels': {'app.kubernetes.io/instance': 'etcd-0', 'app.kubernetes.io/name': 'etcd'},
                'limits_cpu': 0.0,
                'limits_memory': 0,
                'name': 'etcd',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod_name': 'api-gateway-etcd-0',
                'requests_cpu': 0.0,
                'requests_memory': 0,
                'status': 'running',
                'workload_name': 'api-gateway-etcd',
                'workload_type': 'StatefulSet',
                'workloads': [{'key': 'StatefulSet', 'value': 'api-gateway-etcd'}],
            },
        ]
        assert actual == expect
