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

import logging

import pytest
from django.forms.models import model_to_dict

from api.bcs.tasks import sync_bcs_pod
from api.bcs_storage.default import FetchResource
from api.kubernetes.default import (
    FetchK8sPodAndContainerListByClusterResource,
    FetchK8sPodListByClusterResource,
)
from bkmonitor.models import BCSLabel, BCSPod, BCSPodLabels
from core.testing import assert_list_contains

logger = logging.getLogger("kubernetes")


pytestmark = pytest.mark.django_db


def test_sync_bcs_pod_to_db(
    monkeypatch, add_bcs_cluster_item_for_update_and_delete, monkeypatch_bcs_storage_fetch_pod_list_by_cluster
):
    monkeypatch.setattr(FetchK8sPodAndContainerListByClusterResource, "cache_type", None)
    monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"

    BCSPod.objects.all().delete()
    BCSLabel.objects.all().delete()

    pod_models, container_models = sync_bcs_pod(bcs_cluster_id)
    actual = [model_to_dict(pod_model) for pod_model in pod_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
            'limit_cpu_usage_ratio': 0,
            'limit_memory_usage_ratio': 0,
            'monitor_status': '',
            'name': 'api-gateway-0',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_ip': '1.1.1.1',
            'ready_container_count': 2,
            'request_cpu_usage_ratio': 0,
            'request_memory_usage_ratio': 0,
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
            'deleted_at': None,
            'images': 'host/etcd:latest',
            'limit_cpu_usage_ratio': 0,
            'limit_memory_usage_ratio': 0,
            'monitor_status': '',
            'name': 'api-gateway-etcd-0',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_ip': '1.1.1.1',
            'ready_container_count': 1,
            'request_cpu_usage_ratio': 0,
            'request_memory_usage_ratio': 0,
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

    assert BCSLabel.objects.all().count() == 3
    actual = list(BCSLabel.objects.all().order_by("value").values_list("value", flat=True))
    assert actual == ['etcd', 'etcd-0', 'gateway-discovery']
    assert BCSPodLabels.objects.all().count() == 3

    actual = [model_to_dict(container_model) for container_model in container_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'image': 'host/namespace/apisix:latest',
            'monitor_status': '',
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
            'monitor_status': '',
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
            'monitor_status': '',
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
    ]
    assert_list_contains(actual, expect)


def test_sync_bcs_pod_to_db_for_update(
    monkeypatch,
    add_bcs_containers,
    add_bcs_pods,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_storage_fetch_pod_list_by_cluster,
):
    monkeypatch.setattr(FetchK8sPodAndContainerListByClusterResource, "cache_type", None)
    monkeypatch.setattr(FetchK8sPodListByClusterResource, "cache_type", None)
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"
    sync_bcs_pod(bcs_cluster_id)
    pod_models, container_models = sync_bcs_pod(bcs_cluster_id)
    actual = [model_to_dict(pod_model) for pod_model in pod_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'images': 'host/namespace/apisix:latest,host/namespace/gateway-discovery:latest',
            'limit_cpu_usage_ratio': 0,
            'limit_memory_usage_ratio': 0,
            'monitor_status': '',
            'name': 'api-gateway-0',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_ip': '1.1.1.1',
            'ready_container_count': 2,
            'request_cpu_usage_ratio': 0,
            'request_memory_usage_ratio': 0,
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
            'deleted_at': None,
            'images': 'host/etcd:latest',
            'limit_cpu_usage_ratio': 0,
            'limit_memory_usage_ratio': 0,
            'monitor_status': '',
            'name': 'api-gateway-etcd-0',
            'namespace': 'bcs-system',
            'node_ip': '2.2.2.2',
            'node_name': 'node-2-2-2-2',
            'pod_ip': '1.1.1.1',
            'ready_container_count': 1,
            'request_cpu_usage_ratio': 0,
            'request_memory_usage_ratio': 0,
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

    actual = [model_to_dict(container_model) for container_model in container_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'deleted_at': None,
            'image': 'host/namespace/apisix:latest',
            'monitor_status': '',
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
            'monitor_status': '',
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
            'monitor_status': '',
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
    ]
    assert_list_contains(actual, expect)
