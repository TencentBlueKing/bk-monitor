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

from api.bcs.tasks import sync_bcs_workload
from bkmonitor.models import BCSLabel, BCSWorkload
from core.testing import assert_list_contains

logger = logging.getLogger("kubernetes")

pytestmark = pytest.mark.django_db


def test_sync_bcs_workload_to_db(
    monkeypatch,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_kubernetes_fetch_k8s_workload_list_by_cluster,
):
    bcs_cluster_id = "BCS-K8S-00000"

    BCSWorkload.objects.all().delete()
    BCSLabel.objects.all().delete()

    workload_models = sync_bcs_workload(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(workload_model) for workload_model in workload_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'container_count': 1,
            'deleted_at': None,
            'images': 'host/namespace/image-name:latest',
            'labels': [],
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
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'container_count': 1,
            'deleted_at': None,
            'images': 'host/namespace/deployment-operator:latest',
            'labels': [],
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
            'status': 'success',
            'type': 'Deployment',
        },
    ]
    assert_list_contains(actual, expect)


def test_sync_bcs_workload_to_db_for_update(
    monkeypatch,
    add_workloads,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_kubernetes_fetch_k8s_workload_list_by_cluster,
):
    bcs_cluster_id = "BCS-K8S-00000"
    workload_models = sync_bcs_workload(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(workload_model) for workload_model in workload_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'container_count': 1,
            'deleted_at': None,
            'images': 'host/namespace/image-name:latest',
            'labels': [],
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
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'container_count': 1,
            'deleted_at': None,
            'images': 'host/namespace/deployment-operator:latest',
            'labels': [],
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
            'status': 'success',
            'type': 'Deployment',
        },
    ]
    assert_list_contains(actual, expect)
