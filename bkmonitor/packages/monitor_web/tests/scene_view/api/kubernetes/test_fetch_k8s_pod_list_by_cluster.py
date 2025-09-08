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
from api.kubernetes.default import FetchK8sPodListByClusterResource
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


class TestFetchK8sPodListByClusterResource:
    def test_fetch(self, monkeypatch, monkeypatch_bcs_storage_fetch_pod_list_by_cluster):
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_pod_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 2,
                'created_at': '2022-01-01T00:00:00Z',
                'image_id_list': ['host/namespace/apisix:latest', 'host/namespace/gateway-discovery:latest'],
                'label_list': [{'key': 'app.kubernetes.io/name', 'value': 'gateway-discovery'}],
                'labels': {'app.kubernetes.io/name': 'gateway-discovery'},
                'limits_cpu': 10,
                'limits_memory': 9663676416,
                'name': 'api-gateway-0',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod': {
                    'metadata': {
                        'creationTimestamp': '2022-01-01T00:00:00Z',
                        'labels': {'app.kubernetes.io/name': 'gateway-discovery'},
                        'name': 'api-gateway-0',
                        'namespace': 'bcs-system',
                        'ownerReferences': [
                            {
                                'apiVersion': 'host/v1alpha1',
                                'blockOwnerDeletion': True,
                                'controller': True,
                                'kind': 'StatefulSet',
                                'name': 'api-gateway',
                            }
                        ],
                    },
                    'spec': {
                        'containers': [
                            {
                                'command': ['date'],
                                'image': 'host/namespace/apisix:latest',
                                'name': 'apisix',
                                'resources': {
                                    'limits': {'cpu': '8', 'memory': '8Gi'},
                                    'requests': {'cpu': '0', 'memory': '512Mi'},
                                },
                            },
                            {
                                'command': ['date'],
                                'image': 'host/namespace/gateway-discovery:latest',
                                'name': 'gateway-discovery',
                                'resources': {
                                    'limits': {'cpu': '2', 'memory': '1Gi'},
                                    'requests': {'cpu': '0', 'memory': '512Mi'},
                                },
                            },
                        ],
                        'initContainers': [
                            {'image': 'host/namespace/image-name:latest', 'name': 'init-zk', 'resources': {}},
                            {'image': 'host/namespace/image-name:latest', 'name': 'init-etcd', 'resources': {}},
                            {'image': 'host/namespace/image-name:latest', 'name': 'init-etcd-apisix', 'resources': {}},
                        ],
                    },
                    'status': {
                        'conditions': [
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'InPlaceUpdateReady',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'Initialized',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'Ready',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'ContainersReady',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'PodScheduled',
                            },
                        ],
                        'containerStatuses': [
                            {
                                'image': 'host/namespace/apisix:latest',
                                'lastState': {},
                                'name': 'apisix',
                                'ready': True,
                                'restartCount': 1,
                                'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                            },
                            {
                                'image': 'host/namespace/gateway-discovery:latest',
                                'lastState': {},
                                'name': 'gateway-discovery',
                                'ready': True,
                                'restartCount': 1,
                                'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                            },
                        ],
                        'hostIP': '2.2.2.2',
                        'initContainerStatuses': [
                            {
                                'image': 'host/namespace/image-name:latest',
                                'lastState': {},
                                'name': 'init-zk',
                                'ready': True,
                                'restartCount': 0,
                                'state': {
                                    'terminated': {
                                        'exitCode': 0,
                                        'finishedAt': '2022-01-01T00:00:00Z',
                                        'reason': 'Completed',
                                        'startedAt': '2022-01-01T00:00:00Z',
                                    }
                                },
                            },
                            {
                                'image': 'host/namespace/image-name:latest',
                                'lastState': {},
                                'name': 'init-etcd',
                                'ready': True,
                                'restartCount': 0,
                                'state': {
                                    'terminated': {
                                        'exitCode': 0,
                                        'finishedAt': '2022-01-01T00:00:00Z',
                                        'reason': 'Completed',
                                        'startedAt': '2022-01-01T00:00:00Z',
                                    }
                                },
                            },
                            {
                                'image': 'host/namespace/image-name:latest',
                                'lastState': {},
                                'name': 'init-etcd-apisix',
                                'ready': True,
                                'restartCount': 0,
                                'state': {
                                    'terminated': {
                                        'exitCode': 0,
                                        'finishedAt': '2022-01-01T00:00:00Z',
                                        'reason': 'Completed',
                                        'startedAt': '2022-01-01T00:00:00Z',
                                    }
                                },
                            },
                        ],
                        'phase': 'Running',
                        'podIP': '1.1.1.1',
                    },
                },
                'pod_ip': '1.1.1.1',
                'ready': '2/2',
                'ready_container_count': 2,
                'requests_cpu': 0,
                'requests_memory': 1073741824,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 10},
                    {'key': 'requests.memory', 'value': '1GB'},
                    {'key': 'limits.memory', 'value': '9GB'},
                ],
                'restarts': 2,
                'status': 'Running',
                'total_container_count': 2,
                'workload_name': 'api-gateway',
                'workload_type': 'StatefulSet',
                'workloads': [{'key': 'StatefulSet', 'value': 'api-gateway'}],
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'image_id_list': ['host/etcd:latest'],
                'label_list': [
                    {'key': 'app.kubernetes.io/instance', 'value': 'etcd-0'},
                    {'key': 'app.kubernetes.io/name', 'value': 'etcd'},
                ],
                'labels': {'app.kubernetes.io/instance': 'etcd-0', 'app.kubernetes.io/name': 'etcd'},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'api-gateway-etcd-0',
                'namespace': 'bcs-system',
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'pod': {
                    'metadata': {
                        'creationTimestamp': '2022-01-01T00:00:00Z',
                        'labels': {'app.kubernetes.io/instance': 'etcd-0', 'app.kubernetes.io/name': 'etcd'},
                        'name': 'api-gateway-etcd-0',
                        'namespace': 'bcs-system',
                        'ownerReferences': [
                            {
                                'apiVersion': 'apps/v1',
                                'blockOwnerDeletion': True,
                                'controller': True,
                                'kind': 'StatefulSet',
                                'name': 'api-gateway-etcd',
                            }
                        ],
                    },
                    'spec': {
                        'containers': [
                            {
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
                            }
                        ]
                    },
                    'status': {
                        'conditions': [
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'Initialized',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'Ready',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'ContainersReady',
                            },
                            {
                                'lastProbeTime': None,
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'status': 'True',
                                'type': 'PodScheduled',
                            },
                        ],
                        'containerStatuses': [
                            {
                                'image': 'host/etcd:latest',
                                'lastState': {},
                                'name': 'etcd',
                                'ready': True,
                                'restartCount': 0,
                                'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                            }
                        ],
                        'hostIP': '2.2.2.2',
                        'phase': 'Running',
                        'podIP': '1.1.1.1',
                    },
                },
                'pod_ip': '1.1.1.1',
                'ready': '1/1',
                'ready_container_count': 1,
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'restarts': 0,
                'status': 'Running',
                'total_container_count': 1,
                'workload_name': 'api-gateway-etcd',
                'workload_type': 'StatefulSet',
                'workloads': [{'key': 'StatefulSet', 'value': 'api-gateway-etcd'}],
            },
        ]
        assert actual == expect

    def test_filter_namespace(self, monkeypatch, monkeypatch_bcs_storage_fetch_pod_list_by_cluster):
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_pod_list_by_cluster(
            {"bcs_cluster_id": bcs_cluster_id, "namespace_list": ["unknown"]}
        )
        expect = []
        assert actual == expect
