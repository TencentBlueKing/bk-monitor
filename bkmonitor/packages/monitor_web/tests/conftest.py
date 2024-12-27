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
from django.utils import timezone
from kubernetes.client.api.custom_objects_api import CustomObjectsApi

from api.bcs_cluster_manager.default import FetchClustersResource
from api.bcs_storage.default import BcsStorageBaseResource, FetchResource
from api.cmdb.default import (
    GetBluekingBiz,
    GetBusiness,
    GetHostByIP,
    GetHostByTopoNode,
    Host,
)
from api.kubernetes.default import (
    FetchContainerUsage,
    FetchK8sBkmMetricbeatEndpointUpResource,
    FetchK8sEventListResource,
    FetchK8sEventLogResource,
    FetchK8sMonitorEndpointListResource,
    FetchK8sNodePerformanceResource,
    FetchK8sPodListByClusterResource,
    FetchK8sWorkloadListByClusterResource,
    FetchNodeCpuUsage,
    FetchUsageRatio,
    HasBkmMetricbeatEndpointUpResource,
)
from api.metadata.default import GetClustersBySpaceUidResource
from api.unify_query.default import QueryDataResource as UnifyQueryQueryDataResource
from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.models import (
    BCSCluster,
    BCSContainer,
    BCSLabel,
    BCSNode,
    BCSPod,
    BCSPodLabels,
    BCSPodMonitor,
    BCSService,
    BCSServiceMonitor,
    BCSWorkload,
)
from metadata.models.bcs import BCSClusterInfo
from monitor_web.scene_view.resources.kubernetes import (
    GetKubernetesCpuAnalysis,
    GetKubernetesDiskAnalysis,
    GetKubernetesMemoryAnalysis,
    GetKubernetesOverCommitAnalysis,
)


@pytest.fixture
def monkeypatch_api_cmdb_get_business(monkeypatch):
    class MockBusiness:
        bk_biz_maintainer = "admin"

    monkeypatch.setattr(GetBusiness, "perform_request", lambda _self, params: [MockBusiness()])


@pytest.fixture
def monkeypatch_api_cmdb_get_blueking_biz(monkeypatch):
    monkeypatch.setattr(GetBluekingBiz, "perform_request", lambda _self, params: 2)


@pytest.fixture
def monkeypatch_had_bkm_metricbeat_endpoint_up(monkeypatch):
    monkeypatch.setattr(HasBkmMetricbeatEndpointUpResource, "perform_request", lambda _self, params: True)


MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS = [
    {
        "clusterID": "BCS-K8S-00000",
        "clusterName": "蓝鲸社区版7.0",
        "projectID": "0000000000",
        "businessID": "2",
        "environment": "prod",
        "engineType": "k8s",
        "clusterType": "single",
        "labels": {},
        "creator": "admin",
        "createTime": '2022-01-01T00:00:00+08:00',
        "updateTime": '2022-01-01T00:00:00+08:00',
        "master": {
            "1.1.1.1": {
                "nodeID": "",
                "innerIP": "1.1.1.1",
                "instanceType": "",
                "CPU": 0,
                "mem": 0,
                "GPU": 0,
                "status": "",
                "zoneID": "",
                "nodeGroupID": "",
                "clusterID": "",
                "VPC": "",
                "region": "default",
                "passwd": "",
                "zone": 0,
                "deviceID": "",
            }
        },
        "status": "RUNNING",
        "networkType": "overlay",
        "description": "蓝鲸社区版7.0集群",
        "is_shared": False,
    },
    {
        "clusterID": "BCS-K8S-00002",
        "clusterName": "共享集群",
        "projectID": "2222222222",
        "businessID": "100",
        "environment": "prod",
        "engineType": "k8s",
        "clusterType": "single",
        "labels": {},
        "creator": "admin",
        "createTime": '2022-01-01T00:00:00+08:00',
        'updateTime': '2022-01-01T00:00:00+08:00',
        "master": {
            "1.1.1.1": {
                "nodeID": "",
                "innerIP": "1.1.1.1",
                "instanceType": "",
                "CPU": 0,
                "mem": 0,
                "GPU": 0,
                "status": "",
                "zoneID": "",
                "nodeGroupID": "",
                "clusterID": "",
                "VPC": "",
                "region": "default",
                "passwd": "",
                "zone": 0,
                "deviceID": "",
            }
        },
        "status": "RUNNING",
        "networkType": "overlay",
        "description": "共享集群",
        "is_shared": True,
    },
]

MOCK_FETCH_K8S_NODE_LIST_BY_CLUSTER = [
    {
        "bcs_cluster_id": "BCS-K8S-00000",
        "node": {
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "master-1-1-1-1",
            },
            "status": {
                "addresses": [
                    {"address": "1.1.1.1", "type": "InternalIP"},
                    {"address": "master-1-1-1-1", "type": "Hostname"},
                ],
                "conditions": [
                    {
                        "reason": "FlannelIsUp",
                        "status": "False",
                        "type": "NetworkUnavailable",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "reason": "KubeletHasSufficientMemory",
                        "status": "False",
                        "type": "MemoryPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "reason": "KubeletHasNoDiskPressure",
                        "status": "False",
                        "type": "DiskPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletHasSufficientPID",
                        "status": "False",
                        "type": "PIDPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletReady",
                        "status": "True",
                        "type": "Ready",
                    },
                ],
            },
        },
        "node_link": {
            "value": "master-1-1-1-1",
            "target": "event",
            "key": "switch_scenes_type",
        },
        "name": "master-1-1-1-1",
        "cloud_id": 0,
        "host_link": {"value": "1.1.1.1", "url": "/performance/detail/1.1.1.1-0", "target": "self"},
        "node_roles": ["control-plane", "master"],
        "node_ip": "1.1.1.1",
        "status": "success",
        "node_name": "master-1-1-1-1",
        "label_list": [],
        "labels": {},
        "endpoint_count": 23,
        "pod_count": 20,
        "created_at": '2022-01-01T00:00:00Z',
        "age": "3 months",
    }
]

# 返回集群的[endpoints, nodes]
MOCK_BCS_STORAGE_FETCH_NODE_AND_ENDPOINT_BY_CLUSTER_ID_FULL = [
    [
        {
            "subsets": [
                {
                    "addresses": [
                        {
                            "nodeName": "node-1-1-1-1",
                            "targetRef": {
                                "kind": "Pod",
                                "name": "api-gateway-0",
                                "namespace": "bcs-system",
                            },
                            "hostname": "api-gateway-0",
                            "ip": "1.1.1.1",
                        }
                    ],
                    "ports": [
                        {"name": "metric", "port": 9001, "protocol": "TCP"},
                        {"name": "gateway", "port": 9002, "protocol": "TCP"},
                        {"name": "apisixmetric", "port": 9003, "protocol": "TCP"},
                        {"protocol": "TCP", "name": "insecure", "port": 9004},
                    ],
                }
            ],
            "metadata": {
                "name": "api-gateway",
                "namespace": "bcs-system",
                "creationTimestamp": "2022-01-01T00:00:00Z",
            },
        },
        {
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "api-gateway-etcd",
                "namespace": "bcs-system",
            },
            "subsets": [
                {
                    "ports": [
                        {"protocol": "TCP", "name": "peer", "port": 9005},
                        {"protocol": "TCP", "name": "client", "port": 9006},
                    ],
                    "addresses": [
                        {
                            "ip": "2.2.2.2",
                            "nodeName": "node-2-2-2-2",
                            "targetRef": {
                                "kind": "Pod",
                                "name": "api-gateway-etcd-0",
                                "namespace": "bcs-system",
                            },
                        }
                    ],
                }
            ],
        },
    ],
    [
        {
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "master-1-1-1-1",
            },
            "spec": {},
            "status": {
                "conditions": [
                    {
                        "reason": "FlannelIsUp",
                        "status": "False",
                        "type": "NetworkUnavailable",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "status": "False",
                        "type": "MemoryPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletHasSufficientMemory",
                    },
                    {
                        "reason": "KubeletHasNoDiskPressure",
                        "status": "False",
                        "type": "DiskPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletHasSufficientPID",
                        "status": "False",
                        "type": "PIDPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletReady",
                        "status": "True",
                        "type": "Ready",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    },
                ],
                "addresses": [
                    {"address": "1.1.1.1", "type": "InternalIP"},
                    {"address": "master-1-1-1-1", "type": "Hostname"},
                ],
            },
        },
        {
            "spec": {},
            "status": {
                "conditions": [
                    {
                        "reason": "FlannelIsUp",
                        "status": "False",
                        "type": "NetworkUnavailable",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "type": "MemoryPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletHasSufficientMemory",
                        "status": "False",
                    },
                    {
                        "type": "DiskPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "reason": "KubeletHasNoDiskPressure",
                        "status": "False",
                    },
                    {
                        "reason": "KubeletHasSufficientPID",
                        "status": "False",
                        "type": "PIDPressure",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                    {
                        "reason": "KubeletReady",
                        "status": "True",
                        "type": "Ready",
                        "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                    },
                ],
                "addresses": [
                    {"address": "2.2.2.2", "type": "InternalIP"},
                    {"type": "Hostname", "address": "node-2-2-2-2"},
                ],
            },
            "metadata": {
                "name": "node-2-2-2-2",
                "creationTimestamp": "2022-01-01T00:00:00Z",
            },
        },
    ],
]

MOCK_BCS_STORAGE_FETCH_NODE_AND_ENDPOINT_BY_CLUSTER_ID = [
    [
        {
            'subsets': [
                {
                    'ports': [
                        {'protocol': 'TCP', 'name': 'metric', 'port': 9007},
                        {'port': 9008, 'protocol': 'TCP', 'name': 'gateway'},
                        {'name': 'apisixmetric', 'port': 9009, 'protocol': 'TCP'},
                        {'protocol': 'TCP', 'name': 'insecure', 'port': 9010},
                    ],
                    'addresses': [
                        {
                            'ip': '2.2.2.2',
                            'nodeName': 'node-2-2-2-2',
                            'targetRef': {'kind': 'Pod', 'name': 'api-gateway-0', 'namespace': 'bcs-system'},
                            'hostname': 'api-gateway-0',
                        }
                    ],
                }
            ],
            'metadata': {'name': 'api-gateway'},
        },
        {
            'subsets': [
                {
                    'addresses': [
                        {
                            'ip': '2.2.2.2',
                            'nodeName': 'node-2-2-2-2',
                            'targetRef': {
                                'kind': 'Pod',
                                'name': 'api-gateway-etcd-0',
                                'namespace': 'bcs-system',
                            },
                        }
                    ],
                    'ports': [
                        {'name': 'peer', 'port': 9011, 'protocol': 'TCP'},
                        {'name': 'client', 'port': 9012, 'protocol': 'TCP'},
                    ],
                }
            ],
            'metadata': {'name': 'api-gateway-etcd'},
        },
    ],
    [
        {
            'metadata': {
                'creationTimestamp': '2022-01-01T00:00:00Z',
                'name': 'master-1-1-1-1',
                'labels': {'node-role.kubernetes.io/master': ''},
            },
            'spec': {},
            'status': {
                'addresses': [
                    {'address': '1.1.1.1', 'type': 'InternalIP'},
                    {'address': 'master-1-1-1-1', 'type': 'Hostname'},
                ],
                'conditions': [
                    {
                        'reason': 'FlannelIsUp',
                        'status': 'False',
                        'type': 'NetworkUnavailable',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                    },
                    {
                        'reason': 'KubeletHasSufficientMemory',
                        'status': 'False',
                        'type': 'MemoryPressure',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                    },
                    {
                        'reason': 'KubeletHasNoDiskPressure',
                        'status': 'False',
                        'type': 'DiskPressure',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                    },
                    {
                        'type': 'PIDPressure',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                        'reason': 'KubeletHasSufficientPID',
                        'status': 'False',
                    },
                    {
                        'reason': 'KubeletReady',
                        'status': 'True',
                        'type': 'Ready',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                    },
                ],
            },
        },
        {
            'metadata': {
                'creationTimestamp': "2022-01-01T00:00:00Z",
                'name': 'node-2-2-2-2',
            },
            'spec': {},
            'status': {
                'addresses': [
                    {'type': 'InternalIP', 'address': '2.2.2.2'},
                    {'type': 'Hostname', 'address': 'node-2-2-2-2'},
                ],
                'conditions': [
                    {
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                        'reason': 'FlannelIsUp',
                        'status': 'False',
                        'type': 'NetworkUnavailable',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                    },
                    {
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                        'reason': 'KubeletHasSufficientMemory',
                        'status': 'False',
                        'type': 'MemoryPressure',
                    },
                    {
                        'type': 'DiskPressure',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                        'reason': 'KubeletHasNoDiskPressure',
                        'status': 'False',
                    },
                    {
                        'reason': 'KubeletHasSufficientPID',
                        'status': 'False',
                        'type': 'PIDPressure',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                    },
                    {
                        'type': 'Ready',
                        'lastHeartbeatTime': "2022-01-01T00:00:00Z",
                        'lastTransitionTime': "2022-01-01T00:00:00Z",
                        'reason': 'KubeletReady',
                        'status': 'True',
                    },
                ],
            },
        },
    ],
]
# 集群的namespace信息
MOCK_BCS_STORAGE_FETCH_NAMESPACE_BY_CLUSTER_ID = [
    {
        "spec": {"finalizers": ["kubernetes"]},
        "status": {"phase": "Active"},
        "metadata": {
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "bcs-system",
        },
    },
    {
        "spec": {"finalizers": ["kubernetes"]},
        "status": {"phase": "Active"},
        "metadata": {
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "bcs-system-2",
        },
    },
]

MOCK_UNIFY_QUERY_QUERY_DATA = {
    "series": [
        {
            "name": "_result0",
            "columns": ["_time", "_value"],
            "types": ["float", "float"],
            "group_keys": [],
            "group_values": [],
            "values": [[1652873880000, 35.982743483580045]],
        }
    ]
}

# POD相关信息
MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER_NODE_LIST = [
    {
        "metadata": {
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "master-1-1-1-1",
        },
        "spec": {},
        "status": {
            "addresses": [
                {"address": "1.1.1.1", "type": "InternalIP"},
                {"address": "master-1-1-1-1", "type": "Hostname"},
            ],
            "conditions": [
                {
                    "reason": "FlannelIsUp",
                    "status": "False",
                    "type": "NetworkUnavailable",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                },
                {
                    "reason": "KubeletHasSufficientMemory",
                    "status": "False",
                    "type": "MemoryPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                },
                {
                    "status": "False",
                    "type": "DiskPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletHasNoDiskPressure",
                },
                {
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletHasSufficientPID",
                    "status": "False",
                    "type": "PIDPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                },
                {
                    "type": "Ready",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletReady",
                    "status": "True",
                },
            ],
        },
    },
    {
        "spec": {},
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": "2.2.2.2"},
                {"address": "node-2-2-2-2", "type": "Hostname"},
            ],
            "conditions": [
                {
                    "reason": "FlannelIsUp",
                    "status": "False",
                    "type": "NetworkUnavailable",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                },
                {
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletHasSufficientMemory",
                    "status": "False",
                    "type": "MemoryPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                },
                {
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletHasNoDiskPressure",
                    "status": "False",
                    "type": "DiskPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                },
                {
                    "type": "PIDPressure",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletHasSufficientPID",
                    "status": "False",
                },
                {
                    "status": "True",
                    "type": "Ready",
                    "lastHeartbeatTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                    "reason": "KubeletReady",
                },
            ],
        },
        "metadata": {
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "node-2-2-2-2",
        },
    },
]
MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER_REPLICA_SET_LIST = [
    {
        "spec": {
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "containers": [
                        {
                            "resources": {
                                "limits": {"cpu": "2", "memory": "2Gi"},
                                "requests": {"cpu": "25m", "memory": "2Gi"},
                            },
                            "image": "host/namespace/image-name:latest",
                            "name": "bcs-cluster-manager",
                        }
                    ],
                    "initContainers": [
                        {
                            "name": "init-etcd",
                            "image": "host/namespace/image-name:latest",
                        }
                    ],
                },
            },
            "replicas": 1,
        },
        "status": {
            "fullyLabeledReplicas": 1,
            "readyReplicas": 1,
            "replicas": 1,
            "availableReplicas": 1,
        },
        "metadata": {
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "Deployment",
                    "name": "bcs-cluster-manager",
                }
            ],
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "replicaSet",
            "namespace": "bcs-system",
        },
    },
    {
        "metadata": {
            "ownerReferences": [
                {
                    "name": "deployment-operator",
                    "apiVersion": "apps/v1",
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "Deployment",
                }
            ],
            "name": "deployment-operator-658d88f7df",
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "namespace": "bcs-system",
        },
        "spec": {
            "replicas": 1,
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "containers": [
                        {
                            "name": "deployment-operator",
                            "resources": {
                                "requests": {"cpu": "25m", "memory": "100Mi"},
                                "limits": {"cpu": "2", "memory": "1Gi"},
                            },
                            "image": "host/namespace/deployment-operator:latest",
                        }
                    ],
                },
            },
        },
        "status": {
            "readyReplicas": 1,
            "replicas": 1,
            "availableReplicas": 1,
            "fullyLabeledReplicas": 1,
        },
    },
]
MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER_POD_DATA = [
    {
        "metadata": {
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "api-gateway-0",
            "namespace": "bcs-system",
            "ownerReferences": [
                {
                    "apiVersion": "host/v1alpha1",
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "StatefulSet",
                    "name": "api-gateway",
                }
            ],
        },
        "spec": {
            "tolerations": [
                {
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                    "effect": "NoExecute",
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
            "nodeName": "node-2-2-2-2",
            "hostname": "api-gateway-0",
            "serviceAccountName": "default",
            "restartPolicy": "Always",
            "containers": [
                {
                    "resources": {"limits": {"cpu": "8", "memory": "8Gi"}, "requests": {"cpu": "0", "memory": "512Mi"}},
                    "name": "apisix",
                    "image": "host/namespace/apisix:latest",
                },
                {
                    "image": "host/namespace/gateway-discovery:latest",
                    "name": "gateway-discovery",
                    "resources": {"limits": {"cpu": "2", "memory": "1Gi"}, "requests": {"cpu": "0", "memory": "512Mi"}},
                },
            ],
            "initContainers": [
                {
                    "name": "init-zk",
                    "image": "host/namespace/image-name:latest",
                },
            ],
        },
        "status": {
            "startTime": '2022-01-01T00:00:00Z',
            "conditions": [
                {
                    "type": "InPlaceUpdateReady",
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                },
                {
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "Initialized",
                },
                {
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "Ready",
                },
                {
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "ContainersReady",
                    "lastProbeTime": None,
                },
                {
                    "status": "True",
                    "type": "PodScheduled",
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                },
            ],
            "containerStatuses": [
                {
                    "lastState": {},
                    "name": "apisix",
                    "ready": True,
                    "restartCount": 0,
                    "state": {
                        "running": {
                            "startedAt": '2022-01-01T00:00:00Z',
                        }
                    },
                    "image": "host/namespace/apisix:latest",
                },
                {
                    "restartCount": 0,
                    "state": {
                        "running": {
                            "startedAt": '2022-01-01T00:00:00Z',
                        }
                    },
                    "image": "host/namespace/gateway-discovery:latest",
                    "lastState": {},
                    "name": "gateway-discovery",
                    "ready": True,
                },
            ],
            "hostIP": "2.2.2.2",
            "initContainerStatuses": [
                {
                    "lastState": {},
                    "name": "init-zk",
                    "ready": True,
                    "restartCount": 0,
                    "state": {
                        "terminated": {
                            "reason": "Completed",
                            "startedAt": '2022-01-01T00:00:00Z',
                            "exitCode": 0,
                            "finishedAt": '2022-01-01T00:00:00Z',
                        }
                    },
                    "image": "host/namespace/image-name:latest",
                },
                {
                    "lastState": {},
                    "name": "init-etcd",
                    "ready": True,
                    "restartCount": 0,
                    "state": {
                        "terminated": {
                            "exitCode": 0,
                            "finishedAt": '2022-01-01T00:00:00Z',
                            "reason": "Completed",
                            "startedAt": '2022-01-01T00:00:00Z',
                        }
                    },
                    "image": "host/namespace/image-name:latest",
                },
                {
                    "lastState": {},
                    "name": "init-etcd-apisix",
                    "ready": True,
                    "restartCount": 0,
                    "state": {
                        "terminated": {
                            "startedAt": '2022-01-01T00:00:00Z',
                            "exitCode": 0,
                            "finishedAt": '2022-01-01T00:00:00Z',
                            "reason": "Completed",
                        }
                    },
                    "image": "host/namespace/image-name:latest",
                },
            ],
            "phase": "Running",
            "podIP": "1.1.1.1",
        },
    },
    {
        "spec": {
            "nodeName": "node-2-2-2-2",
            "tolerations": [
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                    "effect": "NoExecute",
                },
            ],
            "hostname": "api-gateway-etcd-0",
            "containers": [
                {
                    "name": "etcd",
                    "resources": {},
                    "terminationMessagePolicy": "File",
                    "ports": [
                        {"protocol": "TCP", "containerPort": 9012, "name": "client"},
                        {"containerPort": 9011, "name": "peer", "protocol": "TCP"},
                    ],
                    "image": "docker.io/host/etcd:latest",
                    "readinessProbe": {
                        "timeoutSeconds": 5,
                        "exec": {"command": ["date"]},
                        "failureThreshold": 5,
                        "initialDelaySeconds": 60,
                        "periodSeconds": 10,
                        "successThreshold": 1,
                    },
                    "livenessProbe": {
                        "initialDelaySeconds": 60,
                        "periodSeconds": 30,
                        "successThreshold": 1,
                        "timeoutSeconds": 5,
                        "exec": {"command": ["date"]},
                        "failureThreshold": 5,
                    },
                }
            ],
        },
        "status": {
            "phase": "Running",
            "podIP": "1.1.1.1",
            "startTime": "2022-01-01T00:00:00Z",
            "conditions": [
                {
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "Initialized",
                },
                {
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "Ready",
                },
                {
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "ContainersReady",
                    "lastProbeTime": None,
                },
                {
                    "lastProbeTime": None,
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                    "type": "PodScheduled",
                },
            ],
            "containerStatuses": [
                {
                    "name": "etcd",
                    "ready": True,
                    "restartCount": 0,
                    "state": {
                        "running": {
                            "startedAt": '2022-01-01T00:00:00Z',
                        }
                    },
                    "image": "host/etcd:latest",
                    "lastState": {},
                }
            ],
            "hostIP": "2.2.2.2",
        },
        "metadata": {
            "name": "api-gateway-etcd-0",
            "namespace": "bcs-system",
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "StatefulSet",
                    "name": "api-gateway-etcd",
                }
            ],
            "creationTimestamp": '2022-01-01T00:00:00Z',
        },
    },
]
MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER_JOB_LIST = [
    {
        "spec": {
            "parallelism": 1,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "log",
                            "resources": {
                                "limits": {"cpu": "200m", "memory": "1Gi"},
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                            },
                            "image": "host/namespace/k8s-wait-for:latest",
                        }
                    ],
                },
                "metadata": {
                    "creationTimestamp": None,
                },
            },
        },
        "status": {
            "succeeded": 1,
            "completionTime": '2022-01-01T00:00:00Z',
            "conditions": [
                {
                    "status": "True",
                    "type": "Complete",
                    "lastProbeTime": "2022-01-01T00:00:00Z",
                    "lastTransitionTime": "2022-01-01T00:00:00Z",
                }
            ],
            "startTime": "2022-01-01T00:00:00Z",
        },
        "metadata": {
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "api-gateway-storages-1",
            "namespace": "namespace",
        },
    },
    {
        "spec": {
            "template": {
                "spec": {
                    "initContainers": [
                        {
                            "image": "host/namespace/k8s-wait-for:latest",
                            "name": "wait-migrations",
                            "resources": {
                                "limits": {"cpu": "200m", "memory": "1Gi"},
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                            },
                        },
                    ],
                    "containers": [
                        {
                            "image": "host/namespace/k8s-wait-for:latest",
                            "name": "log",
                            "resources": {
                                "limits": {"cpu": "200m", "memory": "1Gi"},
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                            },
                        }
                    ],
                },
                "metadata": {
                    "creationTimestamp": None,
                },
            },
            "parallelism": 1,
        },
        "status": {
            "completionTime": '2022-01-01T00:00:00Z',
            "conditions": [
                {
                    "type": "Complete",
                    "lastProbeTime": '2022-01-01T00:00:00Z',
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "status": "True",
                }
            ],
            "startTime": '2022-01-01T00:00:00Z',
            "succeeded": 1,
        },
        "metadata": {
            "namespace": "namespace",
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "api-gateway-dashboard-1",
        },
    },
]
MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER = [
    [
        {
            'metadata': {'name': 'master-1-1-1-1'},
            'status': {
                'addresses': [
                    {'address': '1.1.1.1', 'type': 'InternalIP'},
                    {'address': 'master-1-1-1-1', 'type': 'Hostname'},
                ]
            },
        },
        {
            'metadata': {'name': 'node-2-2-2-2'},
            'status': {
                'addresses': [
                    {'type': 'InternalIP', 'address': '2.2.2.2'},
                    {'address': 'node-2-2-2-2', 'type': 'Hostname'},
                ]
            },
        },
    ],
    [
        {
            'metadata': {
                'ownerReferences': [
                    {
                        'apiVersion': 'apps/v1',
                        'blockOwnerDeletion': True,
                        'controller': True,
                        'kind': 'Deployment',
                        'name': 'bcs-cluster-manager',
                    }
                ],
                'name': 'replicaSet',
            }
        },
        {
            'metadata': {
                'name': 'deployment-operator-658d88f7df',
                'ownerReferences': [
                    {
                        'name': 'deployment-operator',
                        'apiVersion': 'apps/v1',
                        'blockOwnerDeletion': True,
                        'controller': True,
                        'kind': 'Deployment',
                    }
                ],
            }
        },
    ],
    [
        {
            'status': {
                'conditions': [
                    {
                        'status': 'True',
                        'type': 'InPlaceUpdateReady',
                        'lastProbeTime': None,
                        'lastTransitionTime': '2022-01-01T00:00:00Z',
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
                        'lastTransitionTime': '2022-01-01T00:00:00Z',
                        'status': 'True',
                        'type': 'ContainersReady',
                        'lastProbeTime': None,
                    },
                    {
                        'type': 'PodScheduled',
                        'lastProbeTime': None,
                        'lastTransitionTime': '2022-01-01T00:00:00Z',
                        'status': 'True',
                    },
                ],
                'containerStatuses': [
                    {
                        'restartCount': 1,
                        'state': {
                            'running': {
                                'startedAt': '2022-01-01T00:00:00Z',
                            }
                        },
                        'image': 'host/namespace/apisix:latest',
                        'lastState': {},
                        'name': 'apisix',
                        'ready': True,
                    },
                    {
                        'state': {
                            'running': {
                                'startedAt': '2022-01-01T00:00:00Z',
                            }
                        },
                        'image': 'host/namespace/gateway-discovery:latest',
                        'lastState': {},
                        'name': 'gateway-discovery',
                        'ready': True,
                        'restartCount': 1,
                    },
                ],
                'hostIP': '2.2.2.2',
                'initContainerStatuses': [
                    {
                        'state': {
                            'terminated': {
                                'exitCode': 0,
                                'finishedAt': '2022-01-01T00:00:00Z',
                                'reason': 'Completed',
                                'startedAt': '2022-01-01T00:00:00Z',
                            }
                        },
                        'image': 'host/namespace/image-name:latest',
                        'lastState': {},
                        'name': 'init-zk',
                        'ready': True,
                        'restartCount': 0,
                    },
                    {
                        'state': {
                            'terminated': {
                                'reason': 'Completed',
                                'startedAt': '2022-01-01T00:00:00Z',
                                'exitCode': 0,
                                'finishedAt': '2022-01-01T00:00:00Z',
                            }
                        },
                        'image': 'host/namespace/image-name:latest',
                        'lastState': {},
                        'name': 'init-etcd',
                        'ready': True,
                        'restartCount': 0,
                    },
                    {
                        'restartCount': 0,
                        'state': {
                            'terminated': {
                                'finishedAt': '2022-01-01T00:00:00Z',
                                'reason': 'Completed',
                                'startedAt': '2022-01-01T00:00:00Z',
                                'exitCode': 0,
                            }
                        },
                        'image': 'host/namespace/image-name:latest',
                        'lastState': {},
                        'name': 'init-etcd-apisix',
                        'ready': True,
                    },
                ],
                'phase': 'Running',
                'podIP': '1.1.1.1',
            },
            'metadata': {
                'namespace': 'bcs-system',
                'ownerReferences': [
                    {
                        'name': 'api-gateway',
                        'apiVersion': 'host/v1alpha1',
                        'blockOwnerDeletion': True,
                        'controller': True,
                        'kind': 'StatefulSet',
                    }
                ],
                'creationTimestamp': '2022-01-01T00:00:00Z',
                'name': 'api-gateway-0',
                'labels': {'app.kubernetes.io/name': 'gateway-discovery'},
            },
            'spec': {
                'containers': [
                    {
                        'image': 'host/namespace/apisix:latest',
                        'resources': {
                            'limits': {'cpu': '8', 'memory': '8Gi'},
                            'requests': {'cpu': '0', 'memory': '512Mi'},
                        },
                        'command': ['date'],
                        'name': 'apisix',
                    },
                    {
                        'name': 'gateway-discovery',
                        'image': 'host/namespace/gateway-discovery:latest',
                        'command': ['date'],
                        'resources': {
                            'limits': {'cpu': '2', 'memory': '1Gi'},
                            'requests': {'cpu': '0', 'memory': '512Mi'},
                        },
                    },
                ],
                'initContainers': [
                    {
                        'resources': {},
                        'image': 'host/namespace/image-name:latest',
                        'name': 'init-zk',
                    },
                    {
                        'name': 'init-etcd',
                        'resources': {},
                        'image': 'host/namespace/image-name:latest',
                    },
                    {
                        'resources': {},
                        'image': 'host/namespace/image-name:latest',
                        'name': 'init-etcd-apisix',
                    },
                ],
            },
        },
        {
            'spec': {
                'containers': [
                    {
                        'livenessProbe': {
                            'failureThreshold': 5,
                            'initialDelaySeconds': 60,
                            'periodSeconds': 30,
                            'successThreshold': 1,
                            'timeoutSeconds': 5,
                            'exec': {'command': ['date']},
                        },
                        'readinessProbe': {
                            'exec': {'command': ['date']},
                            'failureThreshold': 5,
                            'initialDelaySeconds': 60,
                            'periodSeconds': 10,
                            'successThreshold': 1,
                            'timeoutSeconds': 5,
                        },
                        'image': 'docker.io/host/etcd:latest',
                        'name': 'etcd',
                        'resources': {},
                        'ports': [
                            {'containerPort': 9012, 'name': 'client', 'protocol': 'TCP'},
                            {'protocol': 'TCP', 'containerPort': 9011, 'name': 'peer'},
                        ],
                    }
                ]
            },
            'status': {
                'hostIP': '2.2.2.2',
                'phase': 'Running',
                'podIP': '1.1.1.1',
                'conditions': [
                    {
                        'lastProbeTime': None,
                        'lastTransitionTime': '2022-01-01T00:00:00Z',
                        'status': 'True',
                        'type': 'Initialized',
                    },
                    {
                        'status': 'True',
                        'type': 'Ready',
                        'lastProbeTime': None,
                        'lastTransitionTime': '2022-01-01T00:00:00Z',
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
                        'name': 'etcd',
                        'ready': True,
                        'restartCount': 0,
                        'state': {'running': {'startedAt': '2022-01-01T00:00:00Z'}},
                        'image': 'host/etcd:latest',
                        'lastState': {},
                    }
                ],
            },
            'metadata': {
                'ownerReferences': [
                    {
                        'controller': True,
                        'kind': 'StatefulSet',
                        'name': 'api-gateway-etcd',
                        'apiVersion': 'apps/v1',
                        'blockOwnerDeletion': True,
                    }
                ],
                'creationTimestamp': '2022-01-01T00:00:00Z',
                'name': 'api-gateway-etcd-0',
                'namespace': 'bcs-system',
                'labels': {'app.kubernetes.io/name': 'etcd', 'app.kubernetes.io/instance': 'etcd-0'},
            },
        },
    ],
    [{'metadata': {'name': 'api-gateway-storages-1'}}, {'metadata': {'name': 'api-gateway-dashboard-1'}}],
]

MOCK_BCS_KUBERNETES_FETCH_K8S_POD_LIST_BY_CLUSTER = [
    {
        "age": "4 days",
        "bcs_cluster_id": "BCS-K8S-00000",
        "container_number": 2,
        "created_at": '2022-01-01T00:00:00Z',
        "image_id_list": [],
        "label_list": [],
        "labels": {},
        "limits_cpu": 10,
        "limits_memory": 9663676416,
        "name": "api-gateway-0",
        "namespace": "bcs-system",
        "node_ip": "2.2.2.2",
        "node_name": "",
        "pod": {
            "metadata": {
                "creationTimestamp": '2022-01-01T00:00:00Z',
                "name": "api-gateway-0",
                "namespace": "bcs-system",
                "ownerReferences": [
                    {
                        "apiVersion": "host/v1alpha1",
                        "blockOwnerDeletion": True,
                        "controller": True,
                        "kind": "StatefulSet",
                        "name": "api-gateway",
                    }
                ],
            },
            "spec": {
                "containers": [
                    {
                        "image": "host/namespace/apisix:latest",
                        "name": "apisix",
                        "resources": {
                            "limits": {"cpu": "8", "memory": "8Gi"},
                            "requests": {"cpu": "0", "memory": "512Mi"},
                        },
                    },
                    {
                        "image": "host/namespace/gateway-discovery:latest",
                        "name": "gateway-discovery",
                        "resources": {
                            "limits": {"cpu": "2", "memory": "1Gi"},
                            "requests": {"cpu": "0", "memory": "512Mi"},
                        },
                    },
                ],
                "dnsPolicy": "ClusterFirst",
                "hostname": "api-gateway-0",
                "initContainers": [
                    {
                        "image": "host/namespace/image-name:latest",
                        "name": "init-zk",
                        "resources": {},
                    }
                ],
                "nodeName": "node-2-2-2-2",
                "tolerations": [
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/not-ready",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/unreachable",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                ],
            },
            "status": {
                "conditions": [
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "InPlaceUpdateReady",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "Initialized",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "Ready",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "ContainersReady",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "PodScheduled",
                    },
                ],
                "containerStatuses": [
                    {
                        "image": "host/namespace/apisix:latest",
                        "lastState": {},
                        "name": "apisix",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "running": {
                                "startedAt": '2022-01-01T00:00:00Z',
                            }
                        },
                    },
                    {
                        "image": "host/namespace/gateway-discovery:latest",
                        "lastState": {},
                        "name": "gateway-discovery",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "running": {
                                "startedAt": "2022-01-01T00:00:00Z",
                            }
                        },
                    },
                ],
                "hostIP": "2.2.2.2",
                "initContainerStatuses": [
                    {
                        "image": "host/namespace/image-name:latest",
                        "lastState": {},
                        "name": "init-zk",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "terminated": {
                                "exitCode": 0,
                                "finishedAt": '2022-01-01T00:00:00Z',
                                "reason": "Completed",
                                "startedAt": '2022-01-01T00:00:00Z',
                            }
                        },
                    },
                    {
                        "image": "host/namespace/image-name:latest",
                        "lastState": {},
                        "name": "init-etcd",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "terminated": {
                                "exitCode": 0,
                                "finishedAt": '2022-01-01T00:00:00Z',
                                "reason": "Completed",
                                "startedAt": '2022-01-01T00:00:00Z',
                            }
                        },
                    },
                    {
                        "image": "host/namespace/image-name:latest",
                        "lastState": {},
                        "name": "init-etcd-apisix",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "terminated": {
                                "exitCode": 0,
                                "finishedAt": '2022-01-01T00:00:00Z',
                                "reason": "Completed",
                                "startedAt": '2022-01-01T00:00:00Z',
                            }
                        },
                    },
                ],
                "phase": "Running",
                "podIP": "1.1.1.1",
                "startTime": '2022-01-01T00:00:00Z',
            },
        },
        "pod_ip": "1.1.1.1",
        "ready": "2/2",
        "ready_container_count": 2,
        "requests_cpu": 0,
        "requests_memory": 1073741824,
        "resources": [
            {"key": "requests.cpu", "value": 0},
            {"key": "limits.cpu", "value": 10},
            {"key": "requests.memory", "value": "1GB"},
            {"key": "limits.memory", "value": "9GB"},
        ],
        "restarts": 0,
        "status": "success",
        "total_container_count": 2,
        "workload_name": "api-gateway",
        "workload_type": "StatefulSet",
        "workloads": [{"key": "StatefulSet", "value": "api-gateway"}],
    },
    {
        "age": "4 days",
        "bcs_cluster_id": "BCS-K8S-00000",
        "container_number": 1,
        "created_at": '2022-01-01T00:00:00Z',
        "image_id_list": ["host/etcd:latest"],
        "label_list": [],
        "labels": {},
        "limits_cpu": 0,
        "limits_memory": 0,
        "name": "api-gateway-etcd-0",
        "namespace": "bcs-system",
        "node_ip": "2.2.2.2",
        "node_name": "",
        "pod": {
            "metadata": {
                "creationTimestamp": '2022-01-01T00:00:00Z',
                "labels": {},
                "name": "api-gateway-etcd-0",
                "namespace": "bcs-system",
                "ownerReferences": [
                    {
                        "apiVersion": "apps/v1",
                        "blockOwnerDeletion": True,
                        "controller": True,
                        "kind": "StatefulSet",
                        "name": "api-gateway-etcd",
                    }
                ],
            },
            "spec": {
                "containers": [
                    {
                        "image": "docker.io/host/etcd:latest",
                        "livenessProbe": {
                            "exec": {"command": ["date"]},
                            "failureThreshold": 5,
                            "initialDelaySeconds": 60,
                            "periodSeconds": 30,
                            "successThreshold": 1,
                            "timeoutSeconds": 5,
                        },
                        "name": "etcd",
                        "ports": [
                            {"containerPort": 9012, "name": "client", "protocol": "TCP"},
                            {"containerPort": 9011, "name": "peer", "protocol": "TCP"},
                        ],
                        "readinessProbe": {
                            "exec": {"command": ["date"]},
                            "failureThreshold": 5,
                            "initialDelaySeconds": 60,
                            "periodSeconds": 10,
                            "successThreshold": 1,
                            "timeoutSeconds": 5,
                        },
                        "resources": {},
                    }
                ],
                "dnsPolicy": "ClusterFirst",
                "hostname": "api-gateway-etcd-0",
                "nodeName": "node-2-2-2-2",
                "tolerations": [
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/not-ready",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/unreachable",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                ],
            },
            "status": {
                "conditions": [
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "Initialized",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "Ready",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "ContainersReady",
                    },
                    {
                        "lastProbeTime": None,
                        "lastTransitionTime": '2022-01-01T00:00:00Z',
                        "status": "True",
                        "type": "PodScheduled",
                    },
                ],
                "containerStatuses": [
                    {
                        "image": "host/etcd:latest",
                        "lastState": {},
                        "name": "etcd",
                        "ready": True,
                        "restartCount": 0,
                        "state": {
                            "running": {
                                "startedAt": '2022-01-01T00:00:00Z',
                            }
                        },
                    }
                ],
                "hostIP": "2.2.2.2",
                "phase": "Running",
                "podIP": "1.1.1.1",
                "startTime": '2022-01-01T00:00:00Z',
            },
        },
        "pod_ip": "1.1.1.1",
        "ready": "1/1",
        "ready_container_count": 1,
        "requests_cpu": 0,
        "requests_memory": 0,
        "resources": [
            {"key": "requests.cpu", "value": 0},
            {"key": "limits.cpu", "value": 0},
            {"key": "requests.memory", "value": "0B"},
            {"key": "limits.memory", "value": "0B"},
        ],
        "restarts": 0,
        "status": "success",
        "total_container_count": 1,
        "workload_name": "api-gateway-etcd",
        "workload_type": "StatefulSet",
        "workloads": [{"key": "StatefulSet", "value": "api-gateway-etcd"}],
    },
]
MOCK_BCS_STORAGE_FETCH_K8S_SERVICE_LIST_BY_CLUSTER_ENDPOINTS = [
    {
        "metadata": {
            "namespace": "bcs-system",
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "api-gateway",
        },
        "subsets": [
            {
                "ports": [
                    {"port": 9001, "protocol": "TCP", "name": "metric"},
                    {"port": 9002, "protocol": "TCP", "name": "gateway"},
                    {"port": 9003, "protocol": "TCP", "name": "apisixmetric"},
                    {"protocol": "TCP", "name": "insecure", "port": 9004},
                ],
                "addresses": [
                    {
                        "ip": "1.1.1.1",
                        "nodeName": "node-1-1-1-1",
                        "targetRef": {
                            "namespace": "bcs-system",
                            "kind": "Pod",
                            "name": "api-gateway-0",
                        },
                        "hostname": "api-gateway-0",
                    }
                ],
            }
        ],
    },
    {
        "subsets": [
            {
                "addresses": [
                    {
                        "targetRef": {
                            "kind": "Pod",
                            "name": "api-gateway-etcd-0",
                            "namespace": "bcs-system",
                        },
                        "ip": "2.2.2.2",
                        "nodeName": "node-2-2-2-2",
                    }
                ],
                "ports": [
                    {"port": 9005, "protocol": "TCP", "name": "peer"},
                    {"port": 9006, "protocol": "TCP", "name": "client"},
                ],
            }
        ],
        "metadata": {
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "api-gateway-etcd",
            "namespace": "bcs-system",
        },
    },
]

MOCK_BCS_STORAGE_FETCH_K8S_SERVICE_LIST_BY_CLUSTER_SERVICES = [
    {
        "status": {"loadBalancer": {}},
        "metadata": {
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "api-gateway",
            "namespace": "bcs-system",
        },
        "spec": {
            "sessionAffinity": "None",
            "type": "NodePort",
            "clusterIP": "1.1.1.1",
            "externalTrafficPolicy": "Cluster",
            "ports": [
                {"port": 9002, "protocol": "TCP", "targetPort": 9013, "name": "gateway", "nodePort": 31001},
                {"port": 9004, "protocol": "TCP", "targetPort": 9010, "name": "insecure", "nodePort": 31000},
                {"nodePort": 31003, "port": 9001, "protocol": "TCP", "targetPort": 9014, "name": "metric"},
                {"name": "apisixmetric", "nodePort": 31002, "port": 9003, "protocol": "TCP", "targetPort": 9009},
            ],
        },
    },
    {
        "status": {"loadBalancer": {}},
        "metadata": {
            "namespace": "bcs-system",
            "creationTimestamp": "2022-01-01T00:00:00Z",
            "name": "api-gateway-etcd",
        },
        "spec": {
            "ports": [
                {"protocol": "TCP", "targetPort": "client", "name": "client", "port": 9006},
                {"port": 9005, "protocol": "TCP", "targetPort": "peer", "name": "peer"},
            ],
            "type": "ClusterIP",
            "clusterIP": "2.2.2.2",
        },
    },
]

MOCK_BCS_STORAGE_FETCH_K8S_SERVICE_LIST_BY_CLUSTER = [
    [
        {
            'metadata': {'name': 'api-gateway'},
            'subsets': [
                {
                    'ports': [
                        {'name': 'metric', 'port': 9007, 'protocol': 'TCP'},
                        {'port': 9008, 'protocol': 'TCP', 'name': 'gateway'},
                        {'name': 'apisixmetric', 'port': 9009, 'protocol': 'TCP'},
                        {'name': 'insecure', 'port': 9010, 'protocol': 'TCP'},
                    ],
                    'addresses': [
                        {
                            'ip': '1.1.1.1',
                            'nodeName': 'node-1-1-1--1',
                            'targetRef': {
                                'name': 'api-gateway-0',
                                'namespace': 'bcs-system',
                                'kind': 'Pod',
                            },
                            'hostname': 'api-gateway-0',
                        }
                    ],
                }
            ],
        },
        {
            'subsets': [
                {
                    'addresses': [
                        {
                            'nodeName': 'node-2-2-2-2',
                            'targetRef': {
                                'namespace': 'bcs-system',
                                'kind': 'Pod',
                                'name': 'api-gateway-etcd-0',
                            },
                            'ip': '2.2.2.2',
                        }
                    ],
                    'ports': [
                        {'name': 'peer', 'port': 9011, 'protocol': 'TCP'},
                        {'port': 9012, 'protocol': 'TCP', 'name': 'client'},
                    ],
                }
            ],
            'metadata': {'name': 'api-gateway-etcd'},
        },
    ],
    [
        {
            'status': {'loadBalancer': {}},
            'metadata': {
                'creationTimestamp': '2022-01-01T00:00:00Z',
                'name': 'api-gateway',
                'namespace': 'bcs-system',
            },
            'spec': {
                'ports': [
                    {'name': 'gateway', 'nodePort': 31001, 'port': 9008, 'protocol': 'TCP', 'targetPort': 9013},
                    {'targetPort': 9010, 'name': 'insecure', 'nodePort': 31000, 'port': 9010, 'protocol': 'TCP'},
                    {'targetPort': 9014, 'name': 'metric', 'nodePort': 31003, 'port': 9007, 'protocol': 'TCP'},
                    {'name': 'apisixmetric', 'nodePort': 31002, 'port': 9009, 'protocol': 'TCP', 'targetPort': 9009},
                ],
                'type': 'NodePort',
                'clusterIP': '1.1.1.1',
            },
        },
        {
            'metadata': {
                'name': 'api-gateway-etcd',
                'namespace': 'bcs-system',
                'creationTimestamp': '2022-01-01T00:00:00Z',
            },
            'spec': {
                'clusterIP': '2.2.2.2',
                'ports': [
                    {'name': 'client', 'port': 9012, 'protocol': 'TCP', 'targetPort': 'client'},
                    {'name': 'peer', 'port': 9011, 'protocol': 'TCP', 'targetPort': 'peer'},
                ],
                'type': 'ClusterIP',
            },
            'status': {'loadBalancer': {}},
        },
    ],
]

MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER_FULL = [
    {
        "metadata": {
            "name": "bcs-cluster-manager",
            "namespace": "bcs-system",
            "creationTimestamp": '2022-01-01T00:00:00Z',
        },
        "spec": {
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "containers": [
                        {
                            "resources": {
                                "limits": {"cpu": "2", "memory": "2Gi"},
                                "requests": {"memory": "2Gi", "cpu": "25m"},
                            },
                            "image": "host/namespace/image-name:latest",
                            "name": "bcs-cluster-manager",
                        }
                    ],
                    "initContainers": [
                        {
                            "image": "host/namespace/image-name:latest",
                            "name": "init-etcd",
                        }
                    ],
                },
            },
            "progressDeadlineSeconds": 600,
            "replicas": 1,
        },
        "status": {
            "readyReplicas": 1,
            "replicas": 1,
            "updatedReplicas": 1,
            "availableReplicas": 1,
            "conditions": [
                {
                    "type": "Available",
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "lastUpdateTime": '2022-01-01T00:00:00Z',
                    "reason": "MinimumReplicasAvailable",
                    "status": "True",
                },
                {
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "lastUpdateTime": '2022-01-01T00:00:00Z',
                    "reason": "NewReplicaSetAvailable",
                    "status": "True",
                    "type": "Progressing",
                },
            ],
        },
    },
    {
        "status": {
            "conditions": [
                {
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "lastUpdateTime": '2022-01-01T00:00:00Z',
                    "reason": "MinimumReplicasAvailable",
                    "status": "True",
                    "type": "Available",
                },
                {
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                    "lastUpdateTime": '2022-01-01T00:00:00Z',
                    "reason": "NewReplicaSetAvailable",
                    "status": "True",
                    "type": "Progressing",
                },
            ],
            "readyReplicas": 1,
            "replicas": 1,
            "updatedReplicas": 1,
            "availableReplicas": 1,
        },
        "metadata": {
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "deployment-operator",
            "namespace": "bcs-system",
        },
        "spec": {
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "containers": [
                        {
                            "image": "host/namespace/deployment-operator:latest",
                            "name": "deployment-operator",
                            "resources": {
                                "limits": {"cpu": "2", "memory": "1Gi"},
                                "requests": {"cpu": "25m", "memory": "100Mi"},
                            },
                        }
                    ],
                },
            },
            "replicas": 1,
        },
    },
]

MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER = [
    {
        'metadata': {
            'name': 'bcs-cluster-manager',
            'namespace': 'bcs-system',
            'creationTimestamp': '2022-01-01T00:00:00Z',
        },
        'spec': {
            'template': {
                'spec': {
                    'containers': [
                        {
                            'name': 'bcs-cluster-manager',
                            'image': 'host/namespace/image-name:latest',
                            'resources': {
                                'requests': {'cpu': '25m', 'memory': '2Gi'},
                                'limits': {'cpu': '2', 'memory': '2Gi'},
                            },
                        }
                    ]
                }
            }
        },
        'status': {
            'readyReplicas': 1,
            'replicas': 1,
            'updatedReplicas': 1,
            'availableReplicas': 1,
            'conditions': [
                {
                    'reason': 'NewReplicaSetAvailable',
                    'status': 'True',
                    'type': 'Progressing',
                    'lastTransitionTime': '2022-01-01T00:00:00Z',
                    'lastUpdateTime': '2022-01-01T00:00:00Z',
                },
                {
                    'lastTransitionTime': '2022-01-01T00:00:00Z',
                    'lastUpdateTime': '2022-01-01T00:00:00Z',
                    'reason': 'MinimumReplicasAvailable',
                    'status': 'True',
                    'type': 'Available',
                },
            ],
        },
    },
    {
        'status': {
            'updatedReplicas': 1,
            'availableReplicas': 1,
            'conditions': [
                {
                    'lastUpdateTime': '2022-01-01T00:00:00Z',
                    'reason': 'NewReplicaSetAvailable',
                    'status': 'True',
                    'type': 'Progressing',
                    'lastTransitionTime': '2022-01-01T00:00:00Z',
                },
                {
                    'reason': 'MinimumReplicasAvailable',
                    'status': 'True',
                    'type': 'Available',
                    'lastTransitionTime': '2022-01-01T00:00:00Z',
                    'lastUpdateTime': '2022-01-01T00:00:00Z',
                },
            ],
            'readyReplicas': 1,
            'replicas': 1,
        },
        'metadata': {
            'namespace': 'bcs-system',
            'creationTimestamp': '2022-01-01T00:00:00Z',
            'name': 'deployment-operator',
        },
        'spec': {
            'template': {
                'spec': {
                    'containers': [
                        {
                            'image': 'host/namespace/deployment-operator:latest',
                            'name': 'deployment-operator',
                            'resources': {
                                'limits': {'cpu': '2', 'memory': '1Gi'},
                                'requests': {'cpu': '25m', 'memory': '100Mi'},
                            },
                        }
                    ]
                }
            }
        },
    },
]

MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER_WITH_REPLICASET = [
    {
        "spec": {
            "replicas": 1,
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "containers": [
                        {
                            "livenessProbe": {
                                "initialDelaySeconds": 100,
                                "periodSeconds": 10,
                                "successThreshold": 1,
                                "tcpSocket": {"port": 9015},
                                "timeoutSeconds": 1,
                                "failureThreshold": 3,
                            },
                            "ports": [{"name": "http", "protocol": "TCP", "containerPort": 9015}],
                            "terminationMessagePolicy": "File",
                            "image": "host/amg/workload-admin-service:latest",
                            "readinessProbe": {
                                "failureThreshold": 3,
                                "httpGet": {"scheme": "HTTP", "path": "/health", "port": 9015},
                                "initialDelaySeconds": 30,
                                "periodSeconds": 5,
                                "successThreshold": 1,
                                "timeoutSeconds": 1,
                            },
                            "name": "workload-admin-service",
                        }
                    ],
                },
            },
        },
        "status": {
            "availableReplicas": 1,
            "fullyLabeledReplicas": 1,
            "readyReplicas": 1,
            "replicas": 1,
        },
        "metadata": {
            "ownerReferences": [
                {
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "Deployment",
                    "name": "workload-docker-workload-admin-service",
                    "apiVersion": "apps/v1",
                }
            ],
            "name": "workload-docker-workload-admin-service-111111111",
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "namespace": "workload-docker",
        },
    }
]

MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER_WITH_JOB = [
    {
        "spec": {
            "parallelism": 1,
            "template": {
                "metadata": {
                    "creationTimestamp": None,
                },
                "spec": {
                    "initContainers": [
                        {
                            "image": "host/image:latest",
                            "name": "image-name-1",
                        }
                    ],
                    "containers": [
                        {
                            "name": "image-name-2",
                            "image": "host/image:latest",
                        }
                    ],
                },
            },
            "completions": 1,
        },
        "status": {
            "conditions": [
                {
                    "reason": "BackoffLimitExceeded",
                    "status": "true",
                    "type": "Failed",
                    "lastProbeTime": '2022-01-01T00:00:00Z',
                    "lastTransitionTime": '2022-01-01T00:00:00Z',
                }
            ],
            "startTime": '2022-01-01T00:00:00Z',
        },
        "metadata": {
            "ownerReferences": [
                {
                    "controller": True,
                    "kind": "CronJob",
                    "name": "crontab-job-name-1",
                    "apiVersion": "batch/v1beta1",
                    "blockOwnerDeletion": True,
                }
            ],
            "creationTimestamp": '2022-01-01T00:00:00Z',
            "name": "crontab-job-name-1-1111111111",
            "namespace": "crontab-job",
        },
    }
]

MOCK_BCS_KUBERNETES_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER = [
    {
        "age": "4 days",
        "available": 1,
        "bcs_cluster_id": "BCS-K8S-00000",
        "container_number": 1,
        "created_at": '2022-01-01T00:00:00Z',
        "images": "host/namespace/image-name:latest",
        "label_list": [],
        "labels": {},
        "limits_cpu": 0,
        "limits_memory": 0,
        "name": "bcs-cluster-manager",
        "namespace": "bcs-system",
        "pod_name": [],
        "pod_count": 0,
        "ready": 1,
        "ready_status": "available",
        "requests_cpu": 0,
        "requests_memory": 0,
        "resources": [
            {"key": "requests.cpu", "value": 0},
            {"key": "limits.cpu", "value": 0},
            {"key": "requests.memory", "value": "0B"},
            {"key": "limits.memory", "value": "0B"},
        ],
        "status": "success",
        "up_to_date": 1,
        "workload": {
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "bcs-cluster-manager",
                "namespace": "bcs-system",
            },
            "spec": {
                "progressDeadlineSeconds": 600,
                "replicas": 1,
                "template": {
                    "metadata": {
                        "creationTimestamp": None,
                    },
                    "spec": {
                        "containers": [
                            {
                                "image": "host/namespace/image-name:latest",
                                "name": "bcs-cluster-manager",
                                "resources": {
                                    "limits": {"cpu": "2", "memory": "2Gi"},
                                    "requests": {"cpu": "25m", "memory": "2Gi"},
                                },
                            }
                        ],
                        "initContainers": [
                            {
                                "image": "host/namespace/image-name:latest",
                                "name": "init-etcd",
                                "resources": {},
                            }
                        ],
                    },
                },
            },
            "status": {
                "availableReplicas": 1,
                "conditions": [
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "lastUpdateTime": "2022-01-01T00:00:00Z",
                        "reason": "MinimumReplicasAvailable",
                        "status": "True",
                        "type": "Available",
                    },
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "lastUpdateTime": "2022-01-01T00:00:00Z",
                        "reason": "NewReplicaSetAvailable",
                        "status": "True",
                        "type": "Progressing",
                    },
                ],
                "readyReplicas": 1,
                "replicas": 1,
                "updatedReplicas": 1,
            },
        },
        "workload_labels": {},
        "workload_name": "bcs-cluster-manager",
        "workload_type": "Deployment",
    },
    {
        "age": "4 days",
        "available": 1,
        "bcs_cluster_id": "BCS-K8S-00000",
        "container_number": 1,
        "created_at": '2022-01-01T00:00:00Z',
        "images": "host/namespace/deployment-operator:latest",
        "label_list": [],
        "labels": {},
        "limits_cpu": 0,
        "limits_memory": 0,
        "name": "deployment-operator",
        "namespace": "bcs-system",
        "pod_name": [],
        "pod_count": 0,
        "ready": 1,
        "ready_status": "available",
        "requests_cpu": 0,
        "requests_memory": 0,
        "resources": [
            {"key": "requests.cpu", "value": 0},
            {"key": "limits.cpu", "value": 0},
            {"key": "requests.memory", "value": "0B"},
            {"key": "limits.memory", "value": "0B"},
        ],
        "status": "success",
        "up_to_date": 1,
        "workload": {
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "deployment-operator",
                "namespace": "bcs-system",
            },
            "spec": {
                "progressDeadlineSeconds": 600,
                "replicas": 1,
                "revisionHistoryLimit": 10,
                "template": {
                    "metadata": {
                        "creationTimestamp": None,
                    },
                    "spec": {
                        "containers": [
                            {
                                "image": "host/namespace/deployment-operator:latest",
                                "name": "deployment-operator",
                                "resources": {
                                    "limits": {"cpu": "2", "memory": "1Gi"},
                                    "requests": {"cpu": "25m", "memory": "100Mi"},
                                },
                            }
                        ],
                    },
                },
            },
            "status": {
                "availableReplicas": 1,
                "conditions": [
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "lastUpdateTime": "2022-01-01T00:00:00Z",
                        "reason": "MinimumReplicasAvailable",
                        "status": "True",
                        "type": "Available",
                    },
                    {
                        "lastTransitionTime": "2022-01-01T00:00:00Z",
                        "lastUpdateTime": "2022-01-01T00:00:00Z",
                        "reason": "NewReplicaSetAvailable",
                        "status": "True",
                        "type": "Progressing",
                    },
                ],
                "readyReplicas": 1,
                "replicas": 1,
                "updatedReplicas": 1,
            },
        },
        "workload_labels": {},
        "workload_name": "deployment-operator",
        "workload_type": "Deployment",
    },
]

MOCK_KUBERNETES_FETCH_K8S_SERVICE_MONITOR_LIST_BY_CLUSTER = {
    "apiVersion": "monitoring.coreos.com/v1",
    "items": [
        {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "namespace-operator-stack-api-server",
                "namespace": "namespace-operator",
            },
            "spec": {
                "endpoints": [
                    {
                        "port": "https",
                        "scheme": "https",
                        "tlsConfig": {
                            "insecureSkipVerify": False,
                            "serverName": "kubernetes",
                        },
                    }
                ],
            },
        },
        {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "creationTimestamp": "2022-01-01T00:00:00Z",
                "name": "namespace-operator-stack-kube-state-metrics",
                "namespace": "namespace-operator",
            },
            "spec": {
                "endpoints": [
                    {
                        "port": "http",
                    }
                ],
            },
        },
    ],
    "kind": "ServiceMonitorList",
    "metadata": {"continue": ""},
}

MOCK_KUBERNETES_FETCH_K8S_POD_MONITOR_LIST_BY_CLUSTER = {
    "apiVersion": "monitoring.coreos.com/v1",
    "items": [
        {
            'apiVersion': 'monitoring.coreos.com/v1',
            'kind': 'PodMonitor',
            'metadata': {
                'labels': {'app.kubernetes.io/name': 'pod-monitor'},
                'name': 'pod-monitor-test',
                'namespace': 'default',
            },
            'spec': {
                'namespaceSelector': {'matchNames': ['default']},
                'podMetricsEndpoints': [{'interval': '300s', 'path': '/metrics', 'port': 'http'}],
                'selector': {
                    'matchLabels': {
                        'app.kubernetes.io/name': 'monitor',
                        'process': 'web',
                        'processType': 'metrics',
                    }
                },
            },
        }
    ],
    "kind": "PodMonitorList",
    "metadata": {"continue": ""},
}

MOCK_KUBERNETES_FETCH_K8S_EVENT_LIST = {
    "list": [
        {
            "_index": "v2_2_namespace_event_1_2_0",
            "_type": "_doc",
            "_id": "1",
            "_score": None,
            "_source": {
                "dimensions": {
                    "bcs_cluster_id": "BCS-K8S-40764",
                    "bk_biz_id": "551",
                    "kind": "HorizontalPodAutoscaler",
                    "name": "event-name-php",
                    "namespace": "business-helm",
                },
                "event": {
                    "content": "failed to get memory utilization",
                    "count": 20,
                },
                "event_name": "FailedGetResourceMetric",
                "target": "horizontal-pod-autoscaler",
                "time": "1654581965000",
            },
            "sort": [1654581965000000000],
        }
    ],
    "total": 1,
}

MOCK_KUBERNETES_FETCH_K8S_EVENT_LIST_TYPE_IS_CHART = [
    {
        "alias": "_result_",
        "metric_field": "_result_",
        "dimensions": {"kind": "HorizontalPodAutoscaler"},
        "target": "SUM(event){kind=HorizontalPodAutoscaler}",
        "datapoints": [
            [0, 1654578480000],
            [0, 1654578540000],
            [40, 1654578600000],
            [0, 1654578660000],
            [0, 1654578720000],
            [0, 1654578780000],
            [0, 1654578840000],
            [0, 1654578900000],
            [40, 1654578960000],
            [0, 1654579020000],
            [0, 1654579080000],
            [0, 1654579140000],
            [0, 1654579200000],
            [40, 1654579260000],
            [0, 1654579320000],
            [0, 1654579380000],
            [0, 1654579440000],
            [0, 1654579500000],
            [40, 1654579560000],
            [0, 1654579620000],
            [0, 1654579680000],
            [0, 1654579740000],
            [0, 1654579800000],
            [40, 1654579860000],
            [0, 1654579920000],
            [0, 1654579980000],
            [0, 1654580040000],
            [0, 1654580100000],
            [40, 1654580160000],
            [0, 1654580220000],
            [0, 1654580280000],
            [0, 1654580340000],
            [0, 1654580400000],
            [40, 1654580460000],
            [0, 1654580520000],
            [0, 1654580580000],
            [0, 1654580640000],
            [0, 1654580700000],
            [40, 1654580760000],
            [0, 1654580820000],
            [0, 1654580880000],
            [0, 1654580940000],
            [0, 1654581000000],
            [40, 1654581060000],
            [0, 1654581120000],
            [0, 1654581180000],
            [0, 1654581240000],
            [0, 1654581300000],
            [40, 1654581360000],
            [0, 1654581420000],
            [0, 1654581480000],
            [0, 1654581540000],
            [0, 1654581600000],
            [40, 1654581660000],
            [0, 1654581720000],
            [0, 1654581780000],
            [0, 1654581840000],
            [0, 1654581900000],
            [40, 1654581960000],
            [0, 1654582020000],
            [0, 1654582080000],
        ],
        "stack": "all",
        "type": "bar",
    }
]

MOCK_KUBERNETES_FETCH_K8S_FETCH_CONTAINER_USAGE = [
    {
        "usage_type": "cpu",
        "data": [
            {
                "container_name": "api",
                "namespace": "namespace",
                "pod_name": "api-beat-77c5869696-dc4lj",
                "_time_": 1653128820000,
                "_result_": 0.0008446444444444978,
            },
            {
                "container_name": "api",
                "namespace": "namespace",
                "pod_name": "api-web-5fc88fff94-d6sk2",
                "_time_": 1653128820000,
                "_result_": 0.019931466666669926,
            },
            {
                "container_name": "api",
                "namespace": "namespace",
                "pod_name": "api-worker-79df54ffdb-7t66d",
                "_time_": 1653128820000,
                "_result_": 0.0027477777777777292,
            },
            {
                "container_name": "api-server",
                "namespace": "namespace",
                "pod_name": "api-server-79dccc877b-6nmbw",
                "_time_": 1653128820000,
                "_result_": 0.017046800000005326,
            },
        ],
    },
    {
        "usage_type": "memory",
        "data": [
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "api-gateway-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "api-gateway-etcd-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "replicaSet-cl9mc",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "bcs-etcd-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
        ],
    },
    {
        "usage_type": "disk",
        "data": [
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "api-gateway-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "api-gateway-etcd-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "replicaSet-cl9mc",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
            {
                "container_name": "POD",
                "namespace": "bcs-system",
                "pod_name": "bcs-etcd-0",
                "_time_": 1653128820000,
                "_result_": 131072,
            },
        ],
    },
]

MOCK_KUBERNETES_FETCH_K8S_FETCH_POD_USAGE = [
    {
        "usage_type": "cpu",
        "data": [
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-0",
                "_time_": 1653136140000,
                "_result_": 0.020947444444443082,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-etcd-0",
                "_time_": 1653136140000,
                "_result_": 0.13782395555556123,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "replicaSet-cl9mc",
                "_time_": 1653136140000,
                "_result_": 0.001589044444444375,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "bcs-etcd-0",
                "_time_": 1653136140000,
                "_result_": 0.018255544444441003,
            },
        ],
    },
    {
        "usage_type": "memory",
        "data": [
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-0",
                "_time_": 1653136140000,
                "_result_": 826540032,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-etcd-0",
                "_time_": 1653136140000,
                "_result_": 195993600,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "replicaSet-cl9mc",
                "_time_": 1653136140000,
                "_result_": 62799872,
            },
            {"namespace": "bcs-system", "pod_name": "bcs-etcd-0", "_time_": 1653136140000, "_result_": 112492544},
        ],
    },
    {
        "usage_type": "disk",
        "data": [
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-0",
                "_time_": 1653136140000,
                "_result_": 330514432,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "api-gateway-etcd-0",
                "_time_": 1653136140000,
                "_result_": 5210112,
            },
            {
                "namespace": "bcs-system",
                "pod_name": "replicaSet-cl9mc",
                "_time_": 1653136140000,
                "_result_": 185204736,
            },
            {"namespace": "bcs-system", "pod_name": "bcs-etcd-0", "_time_": 1653136140000, "_result_": 5275648},
        ],
    },
]

MOCK_KUBERNETES_FETCH_K8S_FETCH_NODE_CPU_USAGE = {
    "1.1.1.1": 0.10566185611882578,
    "2.2.2.2": 0.06742554365994677,
}

MOCK_KUBERNETES_MONITOR_ENDPOINT_LIST = [
    {
        "kind": "ServiceMonitor",
        "namespace": "namespace",
        "name": "bk-monitor",
        "count": 1,
        "location": [{"address": "1.1.1.1:80", "node": "node-1-1-1-1", "target": "http://1.1.1.1:80/metrics"}],
    },
    {
        "kind": "ServiceMonitor",
        "namespace": "namespace-operator",
        "name": "namespace-operator-stack-kubelet",
        "count": 2,
        "location": [
            {"address": "1.1.1.1:10250", "node": "node-1-1-1-1", "target": "http://1.1.1.1:10250/metrics"},
            {"address": "2.2.2.2:10250", "node": "node-2-2-2-2", "target": "http://2.2.2.2:10250/metrics"},
        ],
    },
    {
        "kind": "PodMonitor",
        "namespace": "namespace-operator",
        "name": "namespace-operator-stack-kubelet",
        "count": 2,
        "location": [
            {"address": "1.1.1.1:10251", "node": "node-1-1-1-1", "target": "http://1.1.1.1:10251/metrics"},
            {"address": "2.2.2.2:10251", "node": "node-2-2-2-2", "target": "http://2.2.2.2:10251/metrics"},
        ],
    },
]

MOCK_KUBERNETES_FETCH_K8S_EVENT_LOG = {
    "took": 27,
    "timed_out": False,
    "_shards": {"total": 2, "successful": 2, "skipped": 0, "failed": 0},
    "hits": {
        "total": {"value": 649, "relation": "eq"},
        "max_score": None,
        "hits": [
            {
                '_index': 'v2_namespace_event_1_2_0',
                '_type': '_doc',
                '_id': '1',
                '_score': None,
                '_source': {
                    'dimensions': {
                        'apiVersion': 'autoscaling/v2beta2',
                        'bcs_cluster_id': 'BCS-K8S-00000',
                        'bk_biz_id': '2',
                        'host': '',
                        'kind': 'HorizontalPodAutoscaler',
                        'name': 'hpa-soc-backend-scan-producer',
                        'namespace': 'namespace-1',
                        'type': 'Warning',
                    },
                    'event': {'content': 'missing request for memory', 'count': 20},
                    'event_name': 'FailedGetResourceMetric',
                    'target': 'horizontal-pod-autoscaler',
                    'time': '1663749405000',
                },
                'sort': [1663749405000000000],
            },
            {
                '_index': 'v2_namespace_event_1_2_0',
                '_type': '_doc',
                '_id': '2',
                '_score': None,
                '_source': {
                    'dimensions': {
                        'apiVersion': 'autoscaling/v2beta2',
                        'bcs_cluster_id': 'BCS-K8S-00000',
                        'bk_biz_id': '2',
                        'host': '',
                        'kind': 'HorizontalPodAutoscaler',
                        'name': 'hpa-batch-scheduler-worker',
                        'namespace': 'namespace-1',
                        'type': 'Warning',
                    },
                    'event': {'content': 'missing request for cpu', 'count': 20},
                    'event_name': 'FailedGetResourceMetric',
                    'target': 'horizontal-pod-autoscaler',
                    'time': '1663749405000',
                },
                'sort': [1663749405000000000],
            },
        ],
    },
    "aggregations": {
        "dimensions.type": {
            "doc_count_error_upper_bound": 0,
            "sum_other_doc_count": 0,
            "buckets": [
                {
                    "key": "Warning",
                    "doc_count": 638,
                    "time": {
                        "buckets": [
                            {
                                "key_as_string": "1663746060000",
                                "key": 1663746060000,
                                "doc_count": 53,
                                "event_type": {"value": 0},
                            },
                            {
                                "key_as_string": "1663749360000",
                                "key": 1663749360000,
                                "doc_count": 54,
                                "event_type": {"value": 54},
                            },
                        ]
                    },
                },
                {
                    "key": "Normal",
                    "doc_count": 11,
                    "time": {
                        "buckets": [
                            {
                                "key_as_string": "1663747320000",
                                "key": 1663747320000,
                                "doc_count": 8,
                                "event_type": {"value": 8},
                            },
                            {
                                "key_as_string": "1663747920000",
                                "key": 1663747920000,
                                "doc_count": 3,
                                "event_type": {"value": 3},
                            },
                        ]
                    },
                },
            ],
        }
    },
}


@pytest.fixture
def monkeypatch_bcs_storage_base(monkeypatch):
    def return_value(self, params):
        if params.get("offset") == 0:
            return [
                {
                    "id": 1,
                    "username": "username_a",
                },
                {
                    "id": 2,
                    "username": "username_b",
                },
            ]
        elif params.get("offset") == 1:
            return [
                {
                    "id": 3,
                    "username": "username_c",
                },
                {
                    "id": 4,
                    "username": "username_d",
                },
                {
                    "id": 5,
                    "username": "username_e",
                },
            ]
        elif params.get("offset") == 2:
            return [
                {
                    "id": 6,
                    "username": "username_f",
                },
            ]
        else:
            return []

    monkeypatch.setattr(BcsStorageBaseResource, "perform_request", return_value)


@pytest.fixture
def monkeypatch_cluster_management_fetch_clusters(monkeypatch):
    """返回集群列表 ."""
    monkeypatch.setattr(
        FetchClustersResource, "perform_request", lambda self, params: MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_node_and_endpoints(monkeypatch):
    """返回一个集群的node和endpoints信息 ."""
    monkeypatch.setattr(
        FetchResource, "bulk_request", lambda self, params: MOCK_BCS_STORAGE_FETCH_NODE_AND_ENDPOINT_BY_CLUSTER_ID
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_namespace(monkeypatch):
    """返回一个集群的namespaces信息 ."""
    monkeypatch.setattr(
        FetchResource, "perform_request", lambda self, params: MOCK_BCS_STORAGE_FETCH_NAMESPACE_BY_CLUSTER_ID
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_pod_list_by_cluster(monkeypatch):
    """返回一个集群的pods信息 ."""
    monkeypatch.setattr(
        FetchResource, "bulk_request", lambda self, params: MOCK_BCS_STORAGE_FETCH_K8S_POD_LIST_BY_CLUSTER
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_k8s_service_list_by_cluster(monkeypatch):
    """返回一个集群的services信息 ."""
    monkeypatch.setattr(
        FetchResource, "bulk_request", lambda self, params: MOCK_BCS_STORAGE_FETCH_K8S_SERVICE_LIST_BY_CLUSTER
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_k8s_workload_list_by_cluster(monkeypatch):
    """返回一个集群的workload信息 ."""
    monkeypatch.setattr(
        FetchResource, "perform_request", lambda self, params: MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_k8s_workload_list_with_replica_set(monkeypatch):
    """返回一个集群的replicaSet信息 ."""
    monkeypatch.setattr(
        FetchResource,
        "perform_request",
        lambda self, params: MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER_WITH_REPLICASET,
    )


@pytest.fixture
def monkeypatch_bcs_storage_fetch_k8s_workload_list_with_job(monkeypatch):
    """返回一个集群的Job信息 ."""
    monkeypatch.setattr(
        FetchResource,
        "perform_request",
        lambda self, params: MOCK_BCS_STORAGE_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER_WITH_JOB,
    )


@pytest.fixture
def monkeypatch_unify_query_query_data(monkeypatch):
    """调用unify_query获取指标信息 ."""
    monkeypatch.setattr(
        UnifyQueryQueryDataResource, "perform_request", lambda self, params: MOCK_UNIFY_QUERY_QUERY_DATA
    )


@pytest.fixture
def monkeypatch_bcs_kubernetes_fetch_k8s_pod_list_by_cluster(monkeypatch):
    """返回一个集群的pods信息 ."""
    monkeypatch.setattr(
        FetchK8sPodListByClusterResource,
        "perform_request",
        lambda self, params: MOCK_BCS_KUBERNETES_FETCH_K8S_POD_LIST_BY_CLUSTER,
    )


@pytest.fixture
def monkeypatch_bcs_kubernetes_fetch_usage_radio(monkeypatch):
    """返回一个集群的pods信息 ."""
    monkeypatch.setattr(
        FetchUsageRatio,
        "perform_request",
        lambda self, params: {'cpu': 2.460417, 'memory': 27.739831, 'disk': 7.817225},
    )


@pytest.fixture
def monkeypatch_bcs_kubernetes_fetch_k8s_workload_list_by_cluster(monkeypatch):
    """返回一个集群的pods信息 ."""
    monkeypatch.setattr(
        FetchK8sWorkloadListByClusterResource,
        "perform_request",
        lambda self, params: MOCK_BCS_KUBERNETES_FETCH_K8S_WORKLOAD_LIST_BY_CLUSTER,
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_k8s_service_monitor_list_by_cluster(monkeypatch):
    """返回一个集群的service monitor信息 ."""
    monkeypatch.setattr(
        CustomObjectsApi,
        "list_cluster_custom_object",
        lambda self, group, version, plural: MOCK_KUBERNETES_FETCH_K8S_SERVICE_MONITOR_LIST_BY_CLUSTER,
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_k8s_monitor_list_by_cluster(monkeypatch):
    """返回一个集群的pod monitor信息 ."""

    def mock_return(self, group, version, plural):
        if plural == "servicemonitors":
            return MOCK_KUBERNETES_FETCH_K8S_SERVICE_MONITOR_LIST_BY_CLUSTER
        elif plural == "podmonitors":
            return MOCK_KUBERNETES_FETCH_K8S_POD_MONITOR_LIST_BY_CLUSTER
        return {}

    monkeypatch.setattr(CustomObjectsApi, "list_cluster_custom_object", mock_return)


@pytest.fixture
def monkeypatch_kubernetes_fetch_k8s_event_list(monkeypatch):
    """返回event信息 ."""

    def mock_return(self, params):
        data_type = params.get("data_type")
        if data_type == "chart":
            return MOCK_KUBERNETES_FETCH_K8S_EVENT_LIST_TYPE_IS_CHART
        return MOCK_KUBERNETES_FETCH_K8S_EVENT_LIST

    monkeypatch.setattr(
        FetchK8sEventListResource,
        "perform_request",
        mock_return,
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_container_usage(monkeypatch):
    """返回一个集群的容器container usage信息 ."""
    monkeypatch.setattr(
        FetchContainerUsage, "bulk_request", lambda self, params: MOCK_KUBERNETES_FETCH_K8S_FETCH_CONTAINER_USAGE
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_pod_usage(monkeypatch):
    """返回一个集群的容器pod usage信息 ."""
    monkeypatch.setattr(
        FetchContainerUsage, "bulk_request", lambda self, params: MOCK_KUBERNETES_FETCH_K8S_FETCH_POD_USAGE
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_node_cpu_usage(monkeypatch):
    """返回一个集群的Node usage信息 ."""
    monkeypatch.setattr(
        FetchNodeCpuUsage, "perform_request", lambda self, params: MOCK_KUBERNETES_FETCH_K8S_FETCH_NODE_CPU_USAGE
    )


@pytest.fixture
def monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up(monkeypatch):
    """返回一个集群的采集器up指标值 ."""

    def mock_return(self, params):
        bk_biz_id = params["bk_biz_id"]
        group_by = params.get("group_by")
        result = {}
        if group_by == ["node", "code"]:
            result = {
                ("1.1.1.1", "1"): 1,
                ("2.2.2.2", "1"): 2,
                ("3.3.3.3", "1"): 3,
            }
        elif group_by == ["bcs_cluster_id", "code"]:
            result = {('BCS-K8S-00000', '1'): 4}
        elif group_by == ["bk_endpoint_url", "code"]:
            result = {
                ('1.1.1.1:9153/metrics', '1'): 5,
                ('2.2.2.2:9153/metrics', '1'): 6,
            }
        elif group_by == ["namespace", "service", "bk_endpoint_url", "code"]:
            result = {
                ('bcs-system', 'api-gateway', '1.1.1.1:9153/metrics', '1'): 5,
                ('bcs-system', 'api-gateway-etcd', '2.2.2.2:9153/metrics', '1'): 6,
            }
        elif group_by == ["namespace", "bk_monitor_name", "bk_endpoint_url", "endpoint", "code"]:
            if bk_biz_id == 2:
                result = {
                    (
                        'namespace-operator',
                        'namespace-operator-stack-api-server',
                        'https://1.1.1.1:10250/metrics',
                        'https',
                        '2',
                    ): 7,
                }

        return result

    monkeypatch.setattr(FetchK8sBkmMetricbeatEndpointUpResource, "perform_request", mock_return)


@pytest.fixture
def monkeypatch_kubernetes_monitor_endpoint_list(monkeypatch):
    """返回一个集群的Node usage信息 ."""
    monkeypatch.setattr(
        FetchK8sMonitorEndpointList, "perform_request", lambda self, params: MOCK_KUBERNETES_MONITOR_ENDPOINT_LIST
    )


@pytest.fixture
def monkeypatch_list_spaces(monkeypatch):
    """获得所有的空间列表 ."""
    monkeypatch.setattr(
        SpaceApi,
        "list_spaces",
        lambda *args, **kwargs: [
            Space(
                id=101,
                space_type_id='bkcc',
                space_id='3',
                space_name='test_cc_project',
                status='normal',
                space_code=None,
                space_uid='bkcc__3',
                type_name='业务',
                bk_biz_id=3,
            ),
            Space(
                id=102,
                space_type_id='bkci',
                space_id='test_bcs_project',
                space_name='test_bcs_project',
                status='normal',
                space_code='0000000000',
                space_uid='bkci__test_bcs_project',
                type_name='研发项目',
                bk_biz_id=-102,
            ),
            Space(
                id=103,
                space_type_id='bkci',
                space_id='test_shared_bcs_project',
                space_name='test_shared_bcs_project',
                status='normal',
                space_code='2222222222',
                space_uid='bkci__test_shared_bcs_project',
                type_name='研发项目',
                bk_biz_id=-103,
            ),
        ],
    )


@pytest.fixture
def monkeypatch_get_related_bcs_space(monkeypatch):
    """获得空间关联的容器空间 ."""
    monkeypatch.setattr(
        SpaceApi,
        "get_related_space",
        lambda *args, **kwargs: Space(
            id=102,
            space_type_id='bcs',
            space_id='0000000000',
            space_name='test_bcs_project',
            status='normal',
            space_code='0000000000',
            space_uid='bkci__test_bcs_project',
            type_name='研发项目',
            bk_biz_id=-102,
        ),
    )


@pytest.fixture
def monkeypatch_get_related_cc_space(monkeypatch):
    """获得空间关联的主机空间 ."""
    monkeypatch.setattr(
        SpaceApi,
        "get_related_space",
        lambda *args, **kwargs: Space(
            id=101,
            space_type_id='bcs',
            space_id='3',
            space_name='test_cc_project',
            status='normal',
            space_code=None,
            space_uid='bkcc__3',
            type_name='业务',
            bk_biz_id=3,
        ),
    )


@pytest.fixture
def monkeypatch_get_space_detail(monkeypatch):
    """获得空间详情 ."""
    monkeypatch.setattr(
        SpaceApi,
        "get_space_detail",
        lambda *args, **kwargs: Space(
            id=102,
            space_type_id='bcs',
            space_id='0000000000',
            space_name='test_bcs_project',
            status='normal',
            space_code='test_bcs_project',
            space_uid='bkci__test_bcs_project',
            type_name='研发项目',
            bk_biz_id=-102,
        ),
    )


@pytest.fixture
def monkeypatch_get_shared_space_detail(monkeypatch):
    """获得空间详情 ."""
    monkeypatch.setattr(
        SpaceApi,
        "get_space_detail",
        lambda *args, **kwargs: Space(
            id=103,
            space_type_id='bkci',
            space_id='test_shared_bcs_project',
            space_name='test_shared_bcs_project',
            status='normal',
            space_code='2222222222',
            space_uid='bkci__test_shared_bcs_project',
            type_name='研发项目',
            bk_biz_id=-103,
        ),
    )


@pytest.fixture
def monkeypatch_get_clusters_by_space_uid(monkeypatch):
    """根据空间uid获得BCS集群 ."""
    monkeypatch.setattr(
        GetClustersBySpaceUidResource,
        "perform_request",
        lambda self, params: [
            {'cluster_id': 'BCS-K8S-00000', 'namespace_list': [], "cluster_type": "single"},
            {'cluster_id': 'BCS-K8S-00002', 'namespace_list': ['namespace_a', 'namespace_b'], "cluster_type": "shared"},
            {'cluster_id': 'BCS-K8S-00003', 'namespace_list': [], "cluster_type": "shared"},  # 共享集群没有使用
        ],
    )


@pytest.fixture
def add_bcs_cluster_item_for_insert_and_delete():
    """添加数据库记录用于新增和删除场景 ."""
    now = timezone.now()
    BCSCluster.objects.all().delete()
    BCSCluster.objects.create(
        **{
            "area_name": "",
            "bcs_cluster_id": "BCS-K8S-00001",
            "bcs_monitor_data_source": "prometheus",
            "bk_biz_id": 2,
            "cpu_usage_ratio": 35.982743483580045,
            "data_source": "api",
            "deleted_at": None,
            "disk_usage_ratio": 35.982743483580045,
            "environment": "prod",
            "gray_status": False,
            "id": None,
            "last_synced_at": now,
            "memory_usage_ratio": 35.982743483580045,
            "name": "蓝鲸社区版7.0",
            "node_count": 2,
            "project_name": "",
            "status": "RUNNING",
            "monitor_status": "success",
            "unique_hash": BCSCluster.md5str("2,BCS-K8S-00001"),
            "created_at": '2022-01-01T00:00:00Z',
            "updated_at": '2022-01-01T00:00:00Z',
            "space_uid": "bcs__1111111111",
        }
    )


@pytest.fixture
def add_bcs_cluster_item_for_update_and_delete():
    """添加数据库记录用于更新和删除cluster的场景 ."""
    now = timezone.now()
    BCSCluster.objects.all().delete()
    BCSCluster.objects.create(
        **{
            "area_name": "",
            "bcs_cluster_id": "BCS-K8S-00000",
            "bcs_monitor_data_source": "prometheus",
            "bk_biz_id": 2,
            "cpu_usage_ratio": 35.982743483580045,
            "data_source": "api",
            "deleted_at": None,
            "disk_usage_ratio": 35.982743483580045,
            "environment": "prod",
            "gray_status": False,
            "id": None,
            "last_synced_at": now,
            "memory_usage_ratio": 35.982743483580045,
            "name": "蓝鲸社区版7.0",
            "node_count": 1,  # 需要变更的值
            "project_name": "",
            "status": "RUNNING",
            "monitor_status": "success",
            "unique_hash": BCSCluster.md5str("2,BCS-K8S-00000"),
            "created_at": '2022-01-01T00:00:00Z',
            "updated_at": '2022-01-01T00:00:00Z',
            "space_uid": "bkci__test_bcs_project",
        }
    )
    BCSCluster.objects.create(
        **{
            "area_name": "",
            "bcs_cluster_id": "BCS-K8S-00001",
            "bcs_monitor_data_source": "prometheus",
            "bk_biz_id": "2",
            "cpu_usage_ratio": 36.982743483580045,
            "data_source": "api",
            "deleted_at": None,
            "disk_usage_ratio": 36.982743483580045,
            "environment": "prod",
            "gray_status": False,
            "id": None,
            "last_synced_at": now,
            "memory_usage_ratio": 36.982743483580045,
            "name": "蓝鲸社区版7.0",
            "node_count": 2,
            "project_name": "",
            "status": "RUNNING",
            "monitor_status": "success",
            "unique_hash": BCSCluster.md5str("2,BCS-K8S-00001"),
            "created_at": '2022-01-01T00:00:00Z',
            "updated_at": '2022-01-01T00:00:00Z',
            "space_uid": "",
        }
    )
    # 添加共享集群
    BCSCluster.objects.create(
        **{
            "area_name": "",
            "bcs_cluster_id": "BCS-K8S-00002",
            "bcs_monitor_data_source": "prometheus",
            "bk_biz_id": 100,
            "cpu_usage_ratio": 37.982743483580045,
            "data_source": "api",
            "deleted_at": None,
            "disk_usage_ratio": 37.982743483580045,
            "environment": "prod",
            "gray_status": False,
            "id": None,
            "last_synced_at": now,
            "memory_usage_ratio": 37.982743483580045,
            "name": "蓝鲸社区版7.0",
            "node_count": 3,
            "project_name": "",
            "status": "RUNNING",
            "monitor_status": "success",
            "unique_hash": BCSCluster.md5str("100,BCS-K8S-00002"),
            "created_at": '2022-01-01T00:00:00Z',
            "updated_at": '2022-01-01T00:00:00Z',
            "space_uid": "bkci__test_shared_bcs_project",
        }
    )


@pytest.fixture
def add_bcs_pods():
    """添加BCSPod数据表记录 ."""
    now = timezone.now()
    BCSPod.objects.all().delete()
    BCSLabel.objects.all().delete()

    # 获得需要新增的标签
    lable_model_1 = BCSLabel.objects.create(
        hash_id=BCSPod.md5str("key_1" + ":" + "value_1"), key="key_1", value="value_1"
    )
    lable_model_2 = BCSLabel.objects.create(
        hash_id=BCSPod.md5str("key_2" + ":" + "value_2"), key="key_2", value="value_2"
    )

    pod_model = BCSPod.objects.create(
        **{
            "bcs_cluster_id": "BCS-K8S-00000",
            "bk_biz_id": 2,
            "deleted_at": None,
            "id": None,
            "images": "host/namespace/apisix:latest,host/namespace/gateway-discovery:latest",
            "name": "api-gateway-0",
            "namespace": "bcs-system",
            "node_ip": "2.2.2.2",
            "node_name": "node-2-2-2-2",
            "pod_ip": "1.1.1.1",
            "ready_container_count": 2,
            "resource_limits_cpu": 10,
            "resource_limits_memory": 9663676416,
            "resource_requests_cpu": 0,
            "resource_requests_memory": 1073741824,
            "resource_usage_cpu": 0.02,
            "resource_usage_disk": 330514432,
            "resource_usage_memory": 826540032,
            "request_cpu_usage_ratio": 1,
            "limit_cpu_usage_ratio": 2,
            "request_memory_usage_ratio": 3,
            "limit_memory_usage_ratio": 4,
            "restarts": 0,
            "status": "Running",
            "monitor_status": "success",
            "total_container_count": 2,
            "unique_hash": BCSPod.hash_unique_key(2, "BCS-K8S-00000", "bcs-system", "api-gateway-0"),
            "workload_name": "api-gateway",
            "workload_type": "StatefulSet",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
        }
    )
    BCSPodLabels.objects.create(
        bcs_cluster_id="BCS-K8S-00000",
        label_id=lable_model_1.hash_id,
        resource_id=pod_model.id,
    )
    BCSPodLabels.objects.create(
        bcs_cluster_id="BCS-K8S-00000",
        label_id=lable_model_2.hash_id,
        resource_id=pod_model.id,
    )

    BCSPod.objects.create(
        **{
            "bcs_cluster_id": "BCS-K8S-00000",
            "bk_biz_id": 2,
            "deleted_at": None,
            "id": None,
            "images": "host/namespace/apisix:latest,host/namespace/gateway-discovery:latest",
            "name": "api-gateway-1",
            "namespace": "bcs-system",
            "node_ip": "1.1.1.1",
            "node_name": "node-1.1.1.1",
            "pod_ip": "1.1.1.1",
            "ready_container_count": 2,
            "resource_limits_cpu": 10,
            "resource_limits_memory": 9663676416,
            "resource_requests_cpu": 0,
            "resource_requests_memory": 1073741824,
            "resource_usage_cpu": 0.03,
            "resource_usage_disk": 330514432,
            "resource_usage_memory": 826540032,
            "request_cpu_usage_ratio": 1,
            "limit_cpu_usage_ratio": 2,
            "request_memory_usage_ratio": 3,
            "limit_memory_usage_ratio": 4,
            "restarts": 0,
            "status": "Completed",
            "monitor_status": "failed",
            "total_container_count": 2,
            "unique_hash": BCSPod.hash_unique_key(2, "BCS-K8S-00000", "bcs-system", "api-gateway-1"),
            "workload_name": "api-gateway",
            "workload_type": "StatefulSet",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
        }
    )

    BCSPod.objects.create(
        **{
            "bcs_cluster_id": "BCS-K8S-00002",
            "bk_biz_id": 100,
            "deleted_at": None,
            "id": None,
            "images": "host/namespace/apisix:latest,host/namespace/gateway-discovery:latest",
            "name": "api-gateway-2",
            "namespace": "namespace_a",
            "node_ip": "1.1.1.1",
            "node_name": "node-1.1.1.1",
            "pod_ip": "2.2.2.2",
            "ready_container_count": 2,
            "resource_limits_cpu": 10,
            "resource_limits_memory": 9663676416,
            "resource_requests_cpu": 0,
            "resource_requests_memory": 1073741824,
            "resource_usage_cpu": 0.03,
            "resource_usage_disk": 330514432,
            "resource_usage_memory": 826540032,
            "request_cpu_usage_ratio": 1,
            "limit_cpu_usage_ratio": 2,
            "request_memory_usage_ratio": 3,
            "limit_memory_usage_ratio": 4,
            "restarts": 10,
            "status": "Completed",
            "monitor_status": "failed",
            "total_container_count": 2,
            "unique_hash": BCSPod.hash_unique_key(100, "BCS-K8S-00002", "namespace_a", "api-gateway-2"),
            "workload_name": "api-gateway",
            "workload_type": "StatefulSet",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
        }
    )


@pytest.fixture
def add_service_monitors():
    """添加BCSServiceMonitor数据表记录 ."""
    now = timezone.now()
    BCSServiceMonitor.objects.all().delete()

    BCSServiceMonitor.objects.create(
        **{
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "metric_interval": "30s",
            "metric_path": "/metrics",
            "metric_port": "https",
            'monitor_status': 'success',
            "name": "namespace-operator-stack-api-server",
            "namespace": "namespace-operator",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
            "unique_hash": BCSServiceMonitor.hash_unique_key(
                2,
                "BCS-K8S-00000",
                "namespace-operator",
                "namespace-operator-stack-api-server",
                "/metrics",
                "https",
                "30s",
            ),
        }
    )
    BCSServiceMonitor.objects.create(
        **{
            "bk_biz_id": 100,
            "bcs_cluster_id": "BCS-K8S-00002",
            "metric_interval": "60s",
            "metric_path": "/metrics",
            "metric_port": "http",
            'monitor_status': 'success',
            "name": "namespace-operator-stack-api-server",
            "namespace": "namespace_a",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
            "unique_hash": BCSServiceMonitor.hash_unique_key(
                100,
                "BCS-K8S-00002",
                "namespace_a",
                "namespace-operator-stack-api-server",
                "/metrics",
                "http",
                "60s",
            ),
        }
    )


@pytest.fixture
def add_pod_monitors():
    """添加BCSPodMonitor数据表记录 ."""
    now = timezone.now()
    BCSPodMonitor.objects.all().delete()

    BCSPodMonitor.objects.create(
        **{
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "metric_interval": "30s",
            "metric_path": "/metrics",
            "metric_port": "https",
            'monitor_status': 'success',
            "name": "pod-monitor-test",
            "namespace": "namespace-operator",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
            "unique_hash": BCSServiceMonitor.hash_unique_key(
                2,
                "BCS-K8S-00000",
                "namespace-operator",
                "pod-monitor-test",
                "/metrics",
                "https",
                "30s",
            ),
        }
    )
    BCSPodMonitor.objects.create(
        **{
            "bk_biz_id": 100,
            "bcs_cluster_id": "BCS-K8S-00002",
            "metric_interval": "60s",
            "metric_path": "/metrics",
            "metric_port": "http",
            'monitor_status': 'success',
            "name": "pod-monitor-test",
            "namespace": "namespace_a",
            "created_at": '2022-01-01T00:00:00Z',
            "last_synced_at": now,
            "unique_hash": BCSServiceMonitor.hash_unique_key(
                100,
                "BCS-K8S-00002",
                "namespace_a",
                "pod-monitor-test",
                "/metrics",
                "http",
                "60s",
            ),
        }
    )


@pytest.fixture
def add_workloads():
    """添加BCSWorkload数据表记录 ."""
    now = timezone.now()
    BCSWorkload.objects.all().delete()

    BCSWorkload.objects.create(
        **{
            'bk_biz_id': 2,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'success',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSWorkload.hash_unique_key(
                2, 'BCS-K8S-00000', 'bcs-system', 'Deployment', 'bcs-cluster-manager'
            ),
            'resource_usage_cpu': 0.0,
            'resource_usage_memory': 0,
            'resource_usage_disk': 0,
            'type': 'Deployment',
            'name': 'bcs-cluster-manager',
            'namespace': 'bcs-system',
            'pod_name_list': 'api-gateway-0',
            'images': 'images',
            'pod_count': 1,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 2147483648,
            'resource_limits_cpu': 2,
            'resource_limits_memory': 2147483648,
        }
    )
    BCSWorkload.objects.create(
        **{
            'bk_biz_id': 100,
            'bcs_cluster_id': 'BCS-K8S-00002',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'success',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSWorkload.hash_unique_key(
                100, 'BCS-K8S-00002', 'namespace_a', 'Deployment', 'bcs-cluster-manager'
            ),
            'resource_usage_cpu': 0.0,
            'resource_usage_memory': 0,
            'resource_usage_disk': 0,
            'type': 'Deployment',
            'name': 'bcs-cluster-manager',
            'namespace': 'namespace_a',
            'pod_name_list': 'api-gateway-0',
            'images': 'images',
            'pod_count': 1,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 2147483648,
            'resource_limits_cpu': 2,
            'resource_limits_memory': 2147483648,
        }
    )


@pytest.fixture
def add_bcs_nodes():
    """添加BCSNode数据表记录 ."""
    now = timezone.now()
    BCSNode.objects.all().delete()

    BCSNode.objects.create(
        **{
            'bk_biz_id': 2,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'Ready',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSNode.hash_unique_key(2, 'BCS-K8S-00000', 'master-1-1-1-1'),
            'name': 'master-1-1-1-1',
            'roles': 'control-plane,master',
            'cloud_id': '',
            'ip': '1.1.1.1',
            'endpoint_count': 19,
            'pod_count': 16,
            'taints': '',
        }
    )
    BCSNode.objects.create(
        **{
            'bk_biz_id': 2,
            'bcs_cluster_id': 'BCS-K8S-00001',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'Ready',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSNode.hash_unique_key(2, 'BCS-K8S-00000', 'master-1-1-1-1'),
            'name': 'node-2-2-2-2',
            'roles': '',
            'cloud_id': '',
            'ip': '2.2.2.2',
            'endpoint_count': 19,
            'pod_count': 16,
            'taints': '',
        }
    )
    BCSNode.objects.create(
        **{
            'bk_biz_id': 100,
            'bcs_cluster_id': 'BCS-K8S-00002',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'Ready',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSNode.hash_unique_key(100, 'BCS-K8S-00002', 'node-2-2-2-2'),
            'name': 'node-2-2-2-2',
            'roles': '',
            'cloud_id': '',
            'ip': '2.2.2.2',
            'endpoint_count': 19,
            'pod_count': 16,
            'taints': '',
        }
    )


@pytest.fixture
def add_bcs_nodes_only_worker():
    """添加BCSNode数据表记录 ."""
    now = timezone.now()
    BCSNode.objects.all().delete()

    BCSNode.objects.create(
        **{
            'bk_biz_id': 2,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'status': 'Ready',
            'monitor_status': 'success',
            'last_synced_at': now,
            'unique_hash': BCSNode.hash_unique_key(2, 'BCS-K8S-00000', 'master-1-1-1-1'),
            'name': 'node-1-1-1-1',
            'roles': '',
            'cloud_id': '',
            'ip': '1.1.1.1',
            'endpoint_count': 19,
            'pod_count': 16,
            'taints': '',
        }
    )


@pytest.fixture
def add_bcs_deployments():
    """添加BCSWorkload数据表记录 ."""
    now = timezone.now()
    BCSNode.objects.all().delete()

    BCSWorkload.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'images': 'host/namespace/image-name:latest',
            'monitor_status': '',
            'name': 'bcs-cluster-manager',
            'namespace': 'bcs-system',
            'pod_count': 0,
            'pod_name_list': '',
            'resource_limits_cpu': 0,
            'resource_limits_memory': 0,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'success',
            'type': 'Deployment',
        }
    )

    BCSWorkload.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'images': 'host/namespace/deployment-operator:latest',
            'monitor_status': '',
            'name': 'deployment-operator',
            'namespace': 'bcs-system',
            'pod_count': 0,
            'pod_name_list': '',
            'resource_limits_cpu': 0,
            'resource_limits_memory': 0,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'failed',
            'type': 'Deployment',
        }
    )


@pytest.fixture
def add_bcs_containers():
    """添加BCSContainers数据表记录 ."""
    now = timezone.now()
    BCSContainer.objects.all().delete()

    BCSContainer.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'image': 'host/namespace/apisix:latest',
            'name': 'apisix',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_name': 'api-gateway-0',
            'resource_limits_cpu': 8,
            'resource_limits_memory': 8589934592,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 536870912,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'running',
            'monitor_status': 'success',
            'unique_hash': BCSContainer.hash_unique_key(2, 'BCS-K8S-00000', "bcs-system", "api-gateway-0", "apisix"),
            'workload_name': 'api-gateway',
            'workload_type': 'StatefulSet',
        }
    )

    BCSContainer.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'image': 'host/namespace/gateway-discovery:latest',
            'name': 'gateway-discovery',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_name': 'api-gateway-0',
            'resource_limits_cpu': 2,
            'resource_limits_memory': 1073741824,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 536870912,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'running',
            'monitor_status': 'failed',
            'unique_hash': BCSContainer.hash_unique_key(
                2, 'BCS-K8S-00000', "bcs-system", "api-gateway-0", "gateway-discovery"
            ),
            'workload_name': 'api-gateway',
            'workload_type': 'StatefulSet',
        }
    )

    BCSContainer.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'image': 'docker.io/host/etcd:latest',
            'name': 'etcd',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_name': 'api-gateway-etcd-0',
            'resource_limits_cpu': 0,
            'resource_limits_memory': 0,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'running',
            'monitor_status': 'disabled',
            'unique_hash': BCSContainer.hash_unique_key(2, 'BCS-K8S-00000', "bcs-system", "api-gateway-etcd-0", "etcd"),
            'workload_name': 'api-gateway-etcd',
            'workload_type': 'StatefulSet',
        }
    )

    BCSContainer.objects.create(
        **{
            'created_at': '2022-01-01T00:00:00Z',
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00002',
            'bk_biz_id': 100,
            'deleted_at': None,
            'image': 'docker.io/host/etcd:latest',
            'name': 'etcd',
            'namespace': 'namespace_a',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_name': 'api-gateway-etcd-0',
            'resource_limits_cpu': 0,
            'resource_limits_memory': 0,
            'resource_requests_cpu': 0,
            'resource_requests_memory': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'status': 'running',
            'monitor_status': 'disabled',
            'unique_hash': BCSContainer.hash_unique_key(
                100, 'BCS-K8S-000002', "namespace_a", "api-gateway-etcd-0", "etcd"
            ),
            'workload_name': 'api-gateway-etcd',
            'workload_type': 'StatefulSet',
        }
    )


@pytest.fixture
def add_bcs_service():
    """添加BCSService数据表记录 ."""
    now = timezone.now()
    BCSService.objects.all().delete()

    BCSService.objects.create(
        **{
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '1.1.1.1',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'endpoint_count': 4,
            'external_ip': '<none>',
            'monitor_status': '',
            'name': 'api-gateway',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-0',
            'ports': '9013:31001/TCP,9010:31000/TCP,9014:31003/TCP,9009:31002/TCP',
            'status': '',
            'type': 'NodePort',
            'unique_hash': BCSService.hash_unique_key(2, 'BCS-K8S-00000', 'bcs-system', 'api-gateway'),
        }
    )
    BCSService.objects.create(
        **{
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '2.2.2.2',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'endpoint_count': 2,
            'external_ip': '<none>',
            'monitor_status': '',
            'name': 'api-gateway-etcd',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-etcd-0',
            'ports': '9012/TCP,9011/TCP',
            'status': '',
            'type': 'ClusterIP',
            'unique_hash': BCSService.hash_unique_key(2, 'BCS-K8S-00000', 'bcs-system', 'api-gateway-etcd'),
        }
    )
    BCSService.objects.create(
        **{
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '3.3.3.3',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'endpoint_count': 6,
            'external_ip': '<none>',
            'monitor_status': '',
            'name': 'elasticsearch-data',
            'namespace': 'namespace',
            'pod_count': 3,
            'pod_name_list': 'elasticsearch-data-2,elasticsearch-data-1,elasticsearch-data-0',
            'ports': '9200/TCP,9300/TCP',
            'status': '',
            'type': 'ClusterIP',
            'unique_hash': BCSService.hash_unique_key(2, 'BCS-K8S-00000', 'namespace', 'elasticsearch-data'),
        }
    )
    BCSService.objects.create(
        **{
            'last_synced_at': now,
            'bcs_cluster_id': 'BCS-K8S-00002',
            'bk_biz_id': 100,
            'cluster_ip': '3.3.3.3',
            'created_at': '2022-01-01T00:00:00Z',
            'deleted_at': None,
            'endpoint_count': 6,
            'external_ip': '<none>',
            'monitor_status': '',
            'name': 'elasticsearch-data',
            'namespace': 'namespace_a',
            'pod_count': 3,
            'pod_name_list': 'elasticsearch-data-2,elasticsearch-data-1,elasticsearch-data-0',
            'ports': '9200/TCP,9300/TCP',
            'status': '',
            'type': 'ClusterIP',
            'unique_hash': BCSService.hash_unique_key(2, 'BCS-K8S-00002', 'namespace_a', 'elasticsearch-data'),
        }
    )


@pytest.fixture
def add_bcs_cluster_info():
    BCSClusterInfo.objects.all().delete()

    BCSClusterInfo.objects.create(
        **{
            "cluster_id": "BCS-K8S-00000",
            "bcs_api_cluster_id": "BCS-K8S-00000",
            "bk_biz_id": 2,
            "project_id": "1",
            "status": "running",
            "domain_name": "domain_name_1",
            "port": 9004,
            "server_address_path": "clusters",
            "api_key_type": "authorization",
            "api_key_content": "",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": True,
            "cert_content": None,
            "K8sMetricDataID": 1,
            "CustomMetricDataID": 2,
            "K8sEventDataID": 3,
            "CustomEventDataID": 4,
            "SystemLogDataID": 0,
            "CustomLogDataID": 0,
            "creator": "admin",
            "last_modify_user": "",
        }
    )

    BCSClusterInfo.objects.create(
        **{
            "cluster_id": "BCS-K8S-00001",
            "bcs_api_cluster_id": "BCS-K8S-00001",
            "bk_biz_id": 2,
            "project_id": "2",
            "status": "running",
            "domain_name": "domain_name_2",
            "port": 9004,
            "server_address_path": "clusters",
            "api_key_type": "authorization",
            "api_key_content": "",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": True,
            "cert_content": None,
            "K8sMetricDataID": 5,
            "CustomMetricDataID": 6,
            "K8sEventDataID": 7,
            "CustomEventDataID": 8,
            "SystemLogDataID": 0,
            "CustomLogDataID": 0,
            "creator": "admin",
            "last_modify_user": "",
        }
    )


@pytest.fixture
def monkeypatch_request_performance_data(monkeypatch):
    monkeypatch.setattr(
        FetchK8sNodePerformanceResource,
        "request_performance_data",
        lambda *args, **kwargs: [
            (
                'system_cpu_summary_usage',
                False,
                [
                    {
                        "_result_": 9.075679523575623,
                        "_time_": 1669281660000,
                        "instance": "1.1.1.1:9101",
                    }
                ],
            ),
            (
                'system_load_load15',
                False,
                [
                    {
                        "_result_": 1.38,
                        "_time_": 1669281720000,
                        "instance": "1.1.1.1:9101",
                    }
                ],
            ),
            (
                'system_io_util',
                False,
                [
                    {
                        "_result_": 4.1202831312984495,
                        "_time_": 1669281720000,
                        "instance": "1.1.1.1:9101",
                    }
                ],
            ),
            (
                'system_disk_in_use',
                False,
                [
                    {
                        "_result_": 15.570738330489176,
                        "_time_": 1669281660000,
                        "instance": "1.1.1.1:9101",
                    },
                    {
                        "_result_": 15.570854758048107,
                        "_time_": 1669281720000,
                        "instance": "2.2.2.2:9101",
                    },
                ],
            ),
            (
                'system_mem_pct_used',
                False,
                [
                    {
                        "_result_": 52.49868644464842,
                        "_time_": 1669281660000,
                        "instance": "1.1.1.1:9101",
                    },
                    {
                        "_result_": 52.502145105798235,
                        "_time_": 1669281720000,
                        "instance": "2.2.2.2:9101",
                    },
                ],
            ),
            (
                'system_cpu_summary_usage',
                True,
                [
                    {
                        "_result_": 10.545429644132964,
                        "_time_": 1669348200000,
                    }
                ],
            ),
            (
                'system_load_load15',
                True,
                [
                    {
                        "_result_": 1.19,
                        "_time_": 1669348200000,
                    }
                ],
            ),
            (
                'system_io_util',
                True,
                [
                    {
                        "_result_": 4.79581937143171,
                        "_time_": 1669348200000,
                    }
                ],
            ),
            (
                'system_disk_in_use',
                True,
                [
                    {
                        "_result_": 16.898492020154194,
                        "_time_": 1669348200000,
                    }
                ],
            ),
            (
                'system_mem_pct_used',
                True,
                [
                    {
                        "_result_": 48.81595433782338,
                        "_time_": 1669348200000,
                    }
                ],
            ),
        ],
    )


@pytest.fixture
def monkeypatch_kubernetes_fetch_k8s_event_log(monkeypatch):
    """返回一个集群的事件日志 ."""
    monkeypatch.setattr(
        FetchK8sEventLogResource, "perform_request", lambda self, params: MOCK_KUBERNETES_FETCH_K8S_EVENT_LOG
    )


@pytest.fixture
def monkeypatch_api_cmdb_get_host_by_topo_node(monkeypatch):
    mock_return_value = [
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-a",
                "bk_host_innerip": "10.0.0.1",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-b",
                "bk_host_innerip": "10.0.0.2",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-c",
                "bk_host_innerip": "10.0.0.3",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
    ]
    monkeypatch.setattr(GetHostByTopoNode, "perform_request", lambda *args, **kwargs: mock_return_value)


@pytest.fixture
def monkeypatch_api_cmdb_get_host_by_ip(monkeypatch):
    mock_return_value = [
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-a",
                "bk_host_innerip": "10.0.0.1",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-b",
                "bk_host_innerip": "10.0.0.2",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
        Host(
            {
                "bk_biz_id": 2,
                "bk_isp_name": "2",
                "bk_os_name": "ubuntu",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "operator": ["user1"],
                "bk_bak_operator": ["user2"],
                "bk_os_version": "linux",
                "bk_host_outerip": "",
                "bk_supplier_account": "0",
                "bk_host_name": "bk_host_name-c",
                "bk_host_innerip": "10.0.0.3",
                "bk_set_ids": [1, 2],
                "bk_module_ids": [1, 2],
                "bk_province_name": "130000",
                "bk_state_name": "DE",
                "bk_state": "测试中",
            }
        ),
    ]
    monkeypatch.setattr(GetHostByIP, "perform_request", lambda *args, **kwargs: mock_return_value)


@pytest.fixture
def monkeypatch_get_kubernetes_cpu_analysis_metrics_value(monkeypatch):
    def return_value(self, params):
        group_by = params["group_by"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        data_source_params = params["data_source_params"]
        key_name = data_source_params["key_name"]
        result = ("unknown", [])
        if not bcs_cluster_id:
            if key_name == "cpu_cores":
                result = (
                    'cpu_cores',
                    [
                        {'_time_': 1679553600000, '_result_': 205.04999999999993},
                        {'_time_': 1679553660000, '_result_': 205.04999999999993},
                    ],
                )
            elif key_name == "limits_cpu_cores":
                result = (
                    'pre_allocatable_usage_ratio',
                    [
                        {'_time_': 1679553600000, '_result_': 29.193367471348513},
                        {'_time_': 1679553660000, '_result_': 29.14459887832242},
                    ],
                )
            elif key_name == "requests_cpu_cores":
                result = (
                    'limits_cpu_cores',
                    [
                        {'_time_': 1679553600000, '_result_': 276.6599999999997},
                        {'_time_': 1679553660000, '_result_': 276.5599999999997},
                    ],
                )
            elif key_name == "requests_cpu_cores":
                result = (
                    'requests_cpu_cores',
                    [
                        {'_time_': 1679553600000, '_result_': 59.86100000000009},
                        {'_time_': 1679553660000, '_result_': 59.76100000000009},
                    ],
                )
        else:
            if not group_by:
                if key_name == "cpu_cores":
                    result = (
                        'cpu_cores',
                        [
                            {'_time_': 1679363640000, '_result_': 112},
                            {'_time_': 1679363700000, '_result_': 112},
                        ],
                    )
                elif key_name == "limits_cpu_cores":
                    result = (
                        'limits_cpu_cores',
                        [
                            {'_time_': 1679363640000, '_result_': 282.3999999999998},
                            {'_time_': 1679363700000, '_result_': 282.3999999999998},
                        ],
                    )
                elif key_name == "pre_allocatable_usage_ratio":
                    result = (
                        'pre_allocatable_usage_ratio',
                        [
                            {'_time_': 1679363640000, '_result_': 34.08928571428583},
                            {'_time_': 1679363700000, '_result_': 34.08928571428583},
                        ],
                    )
                elif key_name == "requests_cpu_cores":
                    result = (
                        'requests_cpu_cores',
                        [
                            {'_time_': 1679363640000, '_result_': 38.18000000000013},
                            {'_time_': 1679363700000, '_result_': 38.18000000000013},
                        ],
                    )

            else:
                if key_name == "limits_cpu_cores":
                    result = (
                        'limits_cpu_cores',
                        [
                            {'namespace': 'bcs-system', '_time_': 1679400420000, '_result_': 44},
                            {'namespace': 'bcs-system', '_time_': 1679400480000, '_result_': 44},
                            {
                                'namespace': 'bkmonitor-operator',
                                '_time_': 1679400420000,
                                '_result_': 21.599999999999994,
                            },
                            {
                                'namespace': 'bkmonitor-operator',
                                '_time_': 1679400480000,
                                '_result_': 21.599999999999994,
                            },
                            {'namespace': 'blueking', '_time_': 1679400420000, '_result_': 196.7},
                            {'namespace': 'blueking', '_time_': 1679400480000, '_result_': 196.7},
                            {'namespace': 'default', '_time_': 1679400420000, '_result_': 16.599999999999998},
                            {'namespace': 'default', '_time_': 1679400480000, '_result_': 16.599999999999998},
                            {'namespace': 'istio-system', '_time_': 1679400420000, '_result_': 2},
                            {'namespace': 'istio-system', '_time_': 1679400480000, '_result_': 2},
                            {'namespace': 'kube-system', '_time_': 1679400420000, '_result_': 0.7},
                            {'namespace': 'kube-system', '_time_': 1679400480000, '_result_': 0.7},
                        ],
                    )
                elif key_name == "requests_cpu_cores":
                    result = (
                        'requests_cpu_cores',
                        [
                            {'namespace': 'bcs-system', '_time_': 1679400300000, '_result_': 4.4609999999999985},
                            {'namespace': 'bcs-system', '_time_': 1679400360000, '_result_': 4.4609999999999985},
                            {
                                'namespace': 'bkmonitor-operator',
                                '_time_': 1679400300000,
                                '_result_': 2.3500000000000005,
                            },
                            {
                                'namespace': 'bkmonitor-operator',
                                '_time_': 1679400360000,
                                '_result_': 2.3500000000000005,
                            },
                            {'namespace': 'blueking', '_time_': 1679400300000, '_result_': 26.875000000000036},
                            {'namespace': 'blueking', '_time_': 1679400360000, '_result_': 26.875000000000036},
                            {'namespace': 'default', '_time_': 1679400300000, '_result_': 1.004},
                            {'namespace': 'default', '_time_': 1679400360000, '_result_': 1.004},
                            {'namespace': 'istio-system', '_time_': 1679400300000, '_result_': 0.62},
                            {'namespace': 'istio-system', '_time_': 1679400360000, '_result_': 0.62},
                            {'namespace': 'kube-system', '_time_': 1679400300000, '_result_': 1.5500000000000005},
                            {'namespace': 'kube-system', '_time_': 1679400360000, '_result_': 1.5500000000000005},
                        ],
                    )

        return result

    monkeypatch.setattr(GetKubernetesCpuAnalysis, "request_unify_query", return_value)


@pytest.fixture
def monkeypatch_get_kubernetes_memory_analysis_metrics_value(monkeypatch):
    def return_value(self, params):
        group_by = params["group_by"]
        data_source_params = params["data_source_params"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        key_name = data_source_params["key_name"]
        if not bcs_cluster_id:
            if key_name == "allocatable_memory_bytes":
                result = (
                    'allocatable_memory_bytes',
                    [
                        {'_time_': 1679555220000, '_result_': 434384023552},
                        {'_time_': 1679555280000, '_result_': 434384023552},
                    ],
                )
            elif key_name == "requests_memory_bytes":
                result = (
                    'requests_memory_bytes',
                    [
                        {'_time_': 1679555220000, '_result_': 76799203072},
                        {'_time_': 1679555280000, '_result_': 76799203072},
                    ],
                )
            elif key_name == "pre_allocatable_usage_ratio":
                result = (
                    'pre_allocatable_usage_ratio',
                    [
                        {'_time_': 1679555220000, '_result_': 17.68002479557271},
                        {'_time_': 1679555280000, '_result_': 17.68002479557271},
                    ],
                )
            elif key_name == "limits_memory_bytes":
                result = (
                    'limits_memory_bytes',
                    [
                        {'_time_': 1679555220000, '_result_': 286999349504},
                        {'_time_': 1679555280000, '_result_': 286999349504},
                    ],
                )
        else:
            if not group_by:
                if key_name == "allocatable_memory_bytes":
                    result = (
                        'allocatable_memory_bytes',
                        [
                            {'_time_': 1679400900000, '_result_': 233041498112},
                            {'_time_': 1679400960000, '_result_': 233041498112},
                        ],
                    )
                elif key_name == "limits_memory_bytes":
                    result = (
                        'limits_memory_bytes',
                        [
                            {'_time_': 1679400900000, '_result_': 430293647360},
                            {'_time_': 1679400960000, '_result_': 430293647360},
                        ],
                    )
                elif key_name == "pre_allocatable_usage_ratio":
                    result = (
                        'pre_allocatable_usage_ratio',
                        [
                            {'_time_': 1679400900000, '_result_': 24.605201412000095},
                            {'_time_': 1679400960000, '_result_': 24.605201412000095},
                        ],
                    )
                elif key_name == "requests_memory_bytes":
                    result = (
                        'requests_memory_bytes',
                        [
                            {'_time_': 1679400900000, '_result_': 57340329984},
                            {'_time_': 1679400960000, '_result_': 57340329984},
                        ],
                    )
            else:
                if key_name == "requests_memory_bytes":
                    result = (
                        'requests_memory_bytes',
                        [
                            {'namespace': 'bcs-system', '_time_': 1679400780000, '_result_': 8407482368},
                            {'namespace': 'bcs-system', '_time_': 1679400840000, '_result_': 8407482368},
                            {'namespace': 'bcs-system', '_time_': 1679400900000, '_result_': 8407482368},
                            {'namespace': 'bcs-system', '_time_': 1679400960000, '_result_': 8407482368},
                            {'namespace': 'bcs-system', '_time_': 1679401020000, '_result_': 8407482368},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400780000, '_result_': 2889875456},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400840000, '_result_': 2889875456},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400900000, '_result_': 2889875456},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400960000, '_result_': 2889875456},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679401020000, '_result_': 2889875456},
                            {'namespace': 'blueking', '_time_': 1679400780000, '_result_': 40233861120},
                            {'namespace': 'blueking', '_time_': 1679400840000, '_result_': 40233861120},
                            {'namespace': 'blueking', '_time_': 1679400900000, '_result_': 40233861120},
                            {'namespace': 'blueking', '_time_': 1679400960000, '_result_': 40233861120},
                            {'namespace': 'blueking', '_time_': 1679401020000, '_result_': 40233861120},
                            {'namespace': 'default', '_time_': 1679400780000, '_result_': 1610612736},
                            {'namespace': 'default', '_time_': 1679400840000, '_result_': 1610612736},
                            {'namespace': 'default', '_time_': 1679400900000, '_result_': 1610612736},
                            {'namespace': 'default', '_time_': 1679400960000, '_result_': 1610612736},
                            {'namespace': 'default', '_time_': 1679401020000, '_result_': 1610612736},
                            {'namespace': 'istio-system', '_time_': 1679400780000, '_result_': 2348810240},
                            {'namespace': 'istio-system', '_time_': 1679400840000, '_result_': 2348810240},
                            {'namespace': 'istio-system', '_time_': 1679400900000, '_result_': 2348810240},
                            {'namespace': 'istio-system', '_time_': 1679400960000, '_result_': 2348810240},
                            {'namespace': 'istio-system', '_time_': 1679401020000, '_result_': 2348810240},
                            {'namespace': 'kube-system', '_time_': 1679400780000, '_result_': 618659840},
                            {'namespace': 'kube-system', '_time_': 1679400840000, '_result_': 618659840},
                            {'namespace': 'kube-system', '_time_': 1679400900000, '_result_': 618659840},
                            {'namespace': 'kube-system', '_time_': 1679400960000, '_result_': 618659840},
                            {'namespace': 'kube-system', '_time_': 1679401020000, '_result_': 618659840},
                        ],
                    )
                elif key_name == "limits_memory_bytes":
                    result = (
                        'limits_memory_bytes',
                        [
                            {'namespace': 'bcs-system', '_time_': 1679400840000, '_result_': 56908316672},
                            {'namespace': 'bcs-system', '_time_': 1679400900000, '_result_': 56908316672},
                            {'namespace': 'bcs-system', '_time_': 1679400960000, '_result_': 56908316672},
                            {'namespace': 'bcs-system', '_time_': 1679401020000, '_result_': 56908316672},
                            {'namespace': 'bcs-system', '_time_': 1679401080000, '_result_': 56908316672},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400840000, '_result_': 14722007040},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400900000, '_result_': 14722007040},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679400960000, '_result_': 14722007040},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679401020000, '_result_': 14722007040},
                            {'namespace': 'bkmonitor-operator', '_time_': 1679401080000, '_result_': 14722007040},
                            {'namespace': 'blueking', '_time_': 1679400840000, '_result_': 346403373056},
                            {'namespace': 'blueking', '_time_': 1679400900000, '_result_': 346403373056},
                            {'namespace': 'blueking', '_time_': 1679400960000, '_result_': 346403373056},
                            {'namespace': 'blueking', '_time_': 1679401020000, '_result_': 346403373056},
                            {'namespace': 'blueking', '_time_': 1679401080000, '_result_': 346403373056},
                            {'namespace': 'default', '_time_': 1679400840000, '_result_': 9126805504},
                            {'namespace': 'default', '_time_': 1679400900000, '_result_': 9126805504},
                            {'namespace': 'default', '_time_': 1679400960000, '_result_': 9126805504},
                            {'namespace': 'default', '_time_': 1679401020000, '_result_': 9126805504},
                            {'namespace': 'default', '_time_': 1679401080000, '_result_': 9126805504},
                            {'namespace': 'istio-system', '_time_': 1679400840000, '_result_': 2147483648},
                            {'namespace': 'istio-system', '_time_': 1679400900000, '_result_': 2147483648},
                            {'namespace': 'istio-system', '_time_': 1679400960000, '_result_': 2147483648},
                            {'namespace': 'istio-system', '_time_': 1679401020000, '_result_': 2147483648},
                            {'namespace': 'istio-system', '_time_': 1679401080000, '_result_': 2147483648},
                            {'namespace': 'kube-system', '_time_': 1679400840000, '_result_': 723517440},
                            {'namespace': 'kube-system', '_time_': 1679400900000, '_result_': 723517440},
                            {'namespace': 'kube-system', '_time_': 1679400960000, '_result_': 723517440},
                            {'namespace': 'kube-system', '_time_': 1679401020000, '_result_': 723517440},
                            {'namespace': 'kube-system', '_time_': 1679401080000, '_result_': 723517440},
                        ],
                    )

        return result

    monkeypatch.setattr(GetKubernetesMemoryAnalysis, "request_unify_query", return_value)


@pytest.fixture
def monkeypatch_get_kubernetes_disk_analysis_metrics_value(monkeypatch):
    def return_value(self, params):
        data_source_params = params["data_source_params"]
        key_name = data_source_params["key_name"]

        if key_name == "system_disk_used":
            result = (
                'system_disk_used',
                [
                    {'_time_': 1679401740000, '_result_': 3680240844800},
                    {'_time_': 1679401800000, '_result_': 3682174853120},
                ],
            )
        elif key_name == "system_disk_total":
            result = (
                'system_disk_total',
                [
                    {'_time_': 1679401740000, '_result_': 15212864638976},
                    {'_time_': 1679401800000, '_result_': 15212864638976},
                ],
            )
        elif key_name == "disk_usage_ratio":
            result = (
                'disk_usage_ratio',
                [
                    {'_time_': 1679401740000, '_result_': 24.19163604053288},
                    {'_time_': 1679401800000, '_result_': 24.204349019750776},
                ],
            )
        return result

    monkeypatch.setattr(GetKubernetesDiskAnalysis, "request_unify_query", return_value)


@pytest.fixture
def monkeypatch_get_kubernetes_over_commit_analysis_metrics_value(monkeypatch):
    def return_value(self, params):
        data_source_params = params["data_source_params"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        key_name = data_source_params["key_name"]

        result = ("unknown", {})
        if bcs_cluster_id:
            if key_name == "cpu_over_commit":
                result = (
                    'cpu_over_commit',
                    {
                        'metrics': [],
                        'series': [
                            {
                                'alias': '_result_',
                                'metric_field': '_result_',
                                'unit': '',
                                'target': 'bcs_cluster_id="BCS-K8S-00000"',
                                'dimensions': {'bcs_cluster_id': 'BCS-K8S-00000'},
                                'datapoints': [
                                    [-0.5153571428571417, 1679538180000],
                                    [-0.5153571428571417, 1679538240000],
                                ],
                            }
                        ],
                    },
                )
            elif key_name == "memory_over_commit":
                result = (
                    'memory_over_commit',
                    {
                        'metrics': [],
                        'series': [
                            {
                                'alias': '_result_',
                                'metric_field': '_result_',
                                'unit': '',
                                'target': 'bcs_cluster_id="BCS-K8S-00000"',
                                'dimensions': {'bcs_cluster_id': 'BCS-K8S-00000'},
                                'datapoints': [
                                    [-0.6082111471513617, 1679538180000],
                                    [-0.6082111471513617, 1679538240000],
                                ],
                            }
                        ],
                    },
                )
        else:
            if key_name == "cpu_throttling_high":
                result = (
                    'cpu_throttling_high',
                    {
                        'metrics': [],
                        'series': [
                            {
                                'alias': '_result_',
                                'metric_field': '_result_',
                                'unit': '',
                                'target': '',
                                'dimensions': {},
                                'datapoints': [
                                    [0.2891203217606019, 1679538240000],
                                    [0.2728070149172382, 1679538300000],
                                ],
                            }
                        ],
                    },
                )
            elif key_name == "memory_oom_times":
                result = (
                    'memory_oom_times',
                    {
                        'metrics': [],
                        'series': [
                            {
                                'alias': '_result_',
                                'metric_field': '_result_',
                                'unit': '',
                                'target': '',
                                'dimensions': {},
                                'datapoints': [
                                    [0, 1679538240000],
                                    [0, 1679538300000],
                                ],
                            }
                        ],
                    },
                )

        return result

    monkeypatch.setattr(GetKubernetesOverCommitAnalysis, "request_single_performance_data", return_value)
