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
from django.conf import settings
from django.forms.models import model_to_dict

from api.bcs.tasks import sync_bcs_cluster_to_db
from api.bcs_storage.default import FetchResource
from api.kubernetes.default import FetchK8sClusterListResource
from bkmonitor.models import BCSCluster
from core.testing import assert_dict_contains

logger = logging.getLogger("kubernetes")

pytestmark = pytest.mark.django_db


def test_sync_cluster_to_db_for_insert(
    monkeypatch,
    monkeypatch_cluster_management_fetch_clusters,
    monkeypatch_bcs_storage_fetch_node_and_endpoints,
    monkeypatch_unify_query_query_data,
    monkeypatch_list_spaces,
    add_bcs_cluster_item_for_insert_and_delete,
):
    monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
    monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
    monkeypatch.setattr(FetchResource, "cache_type", None)

    sync_bcs_cluster_to_db()
    assert BCSCluster.objects.all().count() == 2
    cluster_instances = BCSCluster.objects.all().order_by("bcs_cluster_id")
    actual = model_to_dict(cluster_instances[0])
    expect = {
        'alert_status': 'enabled',
        'area_name': '',
        'bcs_cluster_id': 'BCS-K8S-00000',
        'bcs_monitor_data_source': 'prometheus',
        'bk_biz_id': 2,
        'bkmonitor_operator_deployed': False,
        'bkmonitor_operator_first_deployed': None,
        'bkmonitor_operator_last_deployed': None,
        'bkmonitor_operator_version': None,
        'cpu_usage_ratio': 0.0,
        'data_source': 'api',
        'deleted_at': None,
        'disk_usage_ratio': 0.0,
        'environment': 'prod',
        'gray_status': False,
        'labels': [],
        'memory_usage_ratio': 0.0,
        'monitor_status': '',
        'name': '蓝鲸社区版7.0',
        'node_count': 1,
        'project_name': '',
        'space_uid': 'bkci__test_bcs_project',
        'status': 'RUNNING',
    }
    assert_dict_contains(actual, expect)

    actual = model_to_dict(cluster_instances[1])
    expect = {
        'alert_status': 'enabled',
        'area_name': '',
        'bcs_cluster_id': 'BCS-K8S-00002',
        'bcs_monitor_data_source': 'prometheus',
        'bk_biz_id': 100,
        'bkmonitor_operator_deployed': False,
        'bkmonitor_operator_first_deployed': None,
        'bkmonitor_operator_last_deployed': None,
        'bkmonitor_operator_version': None,
        'cpu_usage_ratio': 0.0,
        'data_source': 'api',
        'deleted_at': None,
        'disk_usage_ratio': 0.0,
        'environment': 'prod',
        'gray_status': False,
        'labels': [],
        'memory_usage_ratio': 0.0,
        'monitor_status': '',
        'name': '共享集群',
        'node_count': 1,
        'project_name': '',
        'space_uid': 'bkci__test_shared_bcs_project',
        'status': 'RUNNING',
    }
    assert_dict_contains(actual, expect)


def test_sync_cluster_to_db_for_update(
    monkeypatch,
    monkeypatch_cluster_management_fetch_clusters,
    monkeypatch_bcs_storage_fetch_node_and_endpoints,
    monkeypatch_unify_query_query_data,
    monkeypatch_list_spaces,
    add_bcs_cluster_item_for_update_and_delete,
):
    monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
    monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
    monkeypatch.setattr(FetchResource, "cache_type", None)

    sync_bcs_cluster_to_db()
    assert BCSCluster.objects.all().count() == 2
    cluster_instances = BCSCluster.objects.all().order_by("bcs_cluster_id")
    actual = model_to_dict(cluster_instances[0])
    expect = {
        'alert_status': 'enabled',
        'area_name': '',
        'bcs_cluster_id': 'BCS-K8S-00000',
        'bcs_monitor_data_source': 'prometheus',
        'bk_biz_id': 2,
        'bkmonitor_operator_deployed': False,
        'bkmonitor_operator_first_deployed': None,
        'bkmonitor_operator_last_deployed': None,
        'bkmonitor_operator_version': None,
        'cpu_usage_ratio': 35.982743483580045,
        'data_source': 'api',
        'deleted_at': None,
        'disk_usage_ratio': 35.982743483580045,
        'environment': 'prod',
        'gray_status': False,
        'labels': [],
        'memory_usage_ratio': 35.982743483580045,
        'monitor_status': 'success',
        'name': '蓝鲸社区版7.0',
        'node_count': 1,
        'project_name': '',
        'space_uid': 'bkci__test_bcs_project',
        'status': 'RUNNING',
    }
    assert_dict_contains(actual, expect)

    actual = model_to_dict(cluster_instances[1])
    expect = {
        'alert_status': 'enabled',
        'area_name': '',
        'bcs_cluster_id': 'BCS-K8S-00002',
        'bcs_monitor_data_source': 'prometheus',
        'bk_biz_id': 100,
        'bkmonitor_operator_deployed': False,
        'bkmonitor_operator_first_deployed': None,
        'bkmonitor_operator_last_deployed': None,
        'bkmonitor_operator_version': None,
        'cpu_usage_ratio': 37.982743483580045,
        'data_source': 'api',
        'deleted_at': None,
        'disk_usage_ratio': 37.982743483580045,
        'environment': 'prod',
        'gray_status': False,
        'labels': [],
        'memory_usage_ratio': 37.982743483580045,
        'monitor_status': 'success',
        'name': '共享集群',
        'node_count': 1,
        'project_name': '',
        'space_uid': 'bkci__test_shared_bcs_project',
        'status': 'RUNNING',
        'unique_hash': 'e046bf23a5df0284f0b430bd0ffdb42e',
    }
    assert_dict_contains(actual, expect)
