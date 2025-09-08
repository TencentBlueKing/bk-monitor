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
    FetchK8sNodeListResource,
)
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


class TestFetchK8sNodeListResource:
    @pytest.mark.django_db
    def test_fetch(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_node_and_endpoints,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sNodeListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sNodeListResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        actual = api.kubernetes.fetch_k8s_node_list(
            {
                "bk_biz_id": 2,
            }
        )
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00Z',
                'endpoint_count': 0,
                'label_list': [{'key': 'node-role.kubernetes.io/master', 'value': ''}],
                'labels': {'node-role.kubernetes.io/master': ''},
                'name': 'master-1-1-1-1',
                'node': {
                    'metadata': {
                        'creationTimestamp': '2022-01-01T00:00:00Z',
                        'labels': {'node-role.kubernetes.io/master': ''},
                        'name': 'master-1-1-1-1',
                    },
                    'spec': {},
                    'status': {
                        'addresses': [
                            {'address': '1.1.1.1', 'type': 'InternalIP'},
                            {'address': 'master-1-1-1-1', 'type': 'Hostname'},
                        ],
                        'conditions': [
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'FlannelIsUp',
                                'status': 'False',
                                'type': 'NetworkUnavailable',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasSufficientMemory',
                                'status': 'False',
                                'type': 'MemoryPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasNoDiskPressure',
                                'status': 'False',
                                'type': 'DiskPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasSufficientPID',
                                'status': 'False',
                                'type': 'PIDPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletReady',
                                'status': 'True',
                                'type': 'Ready',
                            },
                        ],
                    },
                },
                'node_ip': '1.1.1.1',
                'node_name': 'master-1-1-1-1',
                'node_roles': ['master'],
                'pod_count': 0,
                'status': 'Ready',
                'taints': [],
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'created_at': '2022-01-01T00:00:00Z',
                'endpoint_count': 6,
                'label_list': [],
                'labels': {},
                'name': 'node-2-2-2-2',
                'node': {
                    'metadata': {'creationTimestamp': '2022-01-01T00:00:00Z', 'name': 'node-2-2-2-2'},
                    'spec': {},
                    'status': {
                        'addresses': [
                            {'address': '2.2.2.2', 'type': 'InternalIP'},
                            {'address': 'node-2-2-2-2', 'type': 'Hostname'},
                        ],
                        'conditions': [
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'FlannelIsUp',
                                'status': 'False',
                                'type': 'NetworkUnavailable',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasSufficientMemory',
                                'status': 'False',
                                'type': 'MemoryPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasNoDiskPressure',
                                'status': 'False',
                                'type': 'DiskPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletHasSufficientPID',
                                'status': 'False',
                                'type': 'PIDPressure',
                            },
                            {
                                'lastHeartbeatTime': '2022-01-01T00:00:00Z',
                                'lastTransitionTime': '2022-01-01T00:00:00Z',
                                'reason': 'KubeletReady',
                                'status': 'True',
                                'type': 'Ready',
                            },
                        ],
                    },
                },
                'node_ip': '2.2.2.2',
                'node_name': 'node-2-2-2-2',
                'node_roles': [],
                'pod_count': 0,
                'status': 'Ready',
                'taints': [],
            },
        ]
        assert actual == expect
