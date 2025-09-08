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

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sPodListByClusterResource,
    FetchK8sWorkloadListByClusterResource,
)
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


class TestFetchK8sWorkloadListByClusterResource:
    @pytest.mark.django_db
    def test_fetch(
        self,
        monkeypatch,
        monkeypatch_bcs_storage_fetch_k8s_workload_list_by_cluster,
        monkeypatch_bcs_kubernetes_fetch_k8s_pod_list_by_cluster,
    ):
        monkeypatch.setattr(FetchK8sWorkloadListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"

        actual = api.kubernetes.fetch_k8s_workload_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                'active': 0,
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 0,
                'created_at': '2022-01-01T00:00:00Z',
                'images': '',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'schedule': None,
                'status': 'success',
                'suspend': 'false',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'bcs-cluster-manager',
                'workload_type': 'CronJob',
            },
            {
                'active': 0,
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 0,
                'created_at': '2022-01-01T00:00:00Z',
                'images': '',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'deployment-operator',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'schedule': None,
                'status': 'success',
                'suspend': 'false',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'deployment-operator',
                'workload_type': 'CronJob',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'available': None,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'current': None,
                'desired': None,
                'images': 'host/namespace/image-name:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': None,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'up_to_date': None,
                'workload_labels': {},
                'workload_name': 'bcs-cluster-manager',
                'workload_type': 'DaemonSet',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'available': None,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'current': None,
                'desired': None,
                'images': 'host/namespace/deployment-operator:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'deployment-operator',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': None,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'up_to_date': None,
                'workload_labels': {},
                'workload_name': 'deployment-operator',
                'workload_type': 'DaemonSet',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'available': 1,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/image-name:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': 1,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'up_to_date': 1,
                'workload_labels': {},
                'workload_name': 'bcs-cluster-manager',
                'workload_type': 'Deployment',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'available': 1,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/deployment-operator:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'deployment-operator',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': 1,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'up_to_date': 1,
                'workload_labels': {},
                'workload_name': 'deployment-operator',
                'workload_type': 'Deployment',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'completions': 'None/1',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/image-name:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'bcs-cluster-manager',
                'workload_type': 'Job',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'completions': 'None/1',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/deployment-operator:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'deployment-operator',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'deployment-operator',
                'workload_type': 'Job',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/image-name:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': 1,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'bcs-cluster-manager',
                'workload_type': 'StatefulSet',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/namespace/deployment-operator:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'deployment-operator',
                'namespace': 'bcs-system',
                'pod_count': 0,
                'pod_name': [],
                'ready': 1,
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': None,
                'workload_labels': {},
                'workload_name': 'deployment-operator',
                'workload_type': 'StatefulSet',
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_filter(
        self,
        monkeypatch,
        monkeypatch_bcs_storage_fetch_k8s_workload_list_with_job,
        monkeypatch_bcs_kubernetes_fetch_k8s_pod_list_by_cluster,
    ):
        monkeypatch.setattr(FetchK8sWorkloadListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_workload_list_by_cluster(
            {"bcs_cluster_id": bcs_cluster_id, "workload_type_list": ["Job"]}
        )
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'completions': 'None/1',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/image:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'crontab-job-name-1-1111111111',
                'namespace': 'crontab-job',
                'pod_count': 0,
                'pod_name': [],
                'ready_status': 'available',
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': 'CronJob',
                'workload_labels': {},
                'workload_name': 'crontab-job-name-1-1111111111',
                'workload_type': 'Job',
            }
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_filter_by_replica_set(
        self,
        monkeypatch,
        monkeypatch_bcs_storage_fetch_k8s_workload_list_with_replica_set,
        monkeypatch_bcs_kubernetes_fetch_k8s_pod_list_by_cluster,
    ):
        monkeypatch.setattr(FetchK8sWorkloadListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.kubernetes.fetch_k8s_workload_list_by_cluster(
            {"bcs_cluster_id": bcs_cluster_id, "workload_type_list": ["ReplicaSet"]}
        )
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'container_number': 1,
                'created_at': '2022-01-01T00:00:00Z',
                'images': 'host/amg/workload-admin-service:latest',
                'label_list': [],
                'labels': {},
                'limits_cpu': 0,
                'limits_memory': 0,
                'name': 'workload-docker-workload-admin-service-111111111',
                'namespace': 'workload-docker',
                'pod_count': 0,
                'pod_name': [],
                'requests_cpu': 0,
                'requests_memory': 0,
                'resources': [
                    {'key': 'requests.cpu', 'value': 0},
                    {'key': 'limits.cpu', 'value': 0},
                    {'key': 'requests.memory', 'value': '0B'},
                    {'key': 'limits.memory', 'value': '0B'},
                ],
                'status': 'success',
                'top_workload_type': 'Deployment',
                'workload_labels': {},
                'workload_name': 'workload-docker-workload-admin-service-111111111',
                'workload_type': 'ReplicaSet',
            }
        ]
        assert actual == expect
