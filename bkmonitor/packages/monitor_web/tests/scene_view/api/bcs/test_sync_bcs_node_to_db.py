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

from api.bcs.tasks import sync_bcs_node
from api.bcs_storage.default import FetchResource
from bkmonitor.models import BCSLabel, BCSNode, BCSNodeLabels
from core.testing import assert_list_contains

logger = logging.getLogger("kubernetes")

pytestmark = pytest.mark.django_db


@pytest.mark.django_db
def test_sync_bcs_node_to_db(
    monkeypatch,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_storage_fetch_node_and_endpoints,
    monkeypatch_api_cmdb_get_host_by_ip,
):
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"

    BCSNode.objects.all().delete()
    BCSLabel.objects.all().delete()

    node_models = sync_bcs_node(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(node_model) for node_model in node_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cloud_id': '0',
            'deleted_at': None,
            'endpoint_count': 0,
            'ip': '1.1.1.1',
            'monitor_status': '',
            'name': 'master-1-1-1-1',
            'pod_count': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'roles': 'master',
            'status': 'Ready',
            'taints': '',
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cloud_id': '0',
            'deleted_at': None,
            'endpoint_count': 6,
            'ip': '2.2.2.2',
            'labels': [],
            'monitor_status': '',
            'name': 'node-2-2-2-2',
            'pod_count': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'roles': '',
            'status': 'Ready',
            'taints': '',
        },
    ]
    assert_list_contains(actual, expect)

    assert BCSLabel.objects.all().count() == 1
    actual = list(BCSLabel.objects.all().order_by("key").values_list("key", flat=True))
    assert actual == ['node-role.kubernetes.io/master']
    assert BCSNodeLabels.objects.all().count() == 1


@pytest.mark.django_db
def test_sync_bcs_node_to_db_for_update(
    monkeypatch,
    add_bcs_nodes,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_storage_fetch_node_and_endpoints,
    monkeypatch_api_cmdb_get_host_by_ip,
):
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"
    node_models = sync_bcs_node(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(node_model) for node_model in node_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cloud_id': '0',
            'deleted_at': None,
            'endpoint_count': 0,
            'ip': '1.1.1.1',
            'monitor_status': '',
            'name': 'master-1-1-1-1',
            'pod_count': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'roles': 'master',
            'status': 'Ready',
            'taints': '',
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cloud_id': '0',
            'deleted_at': None,
            'endpoint_count': 6,
            'ip': '2.2.2.2',
            'monitor_status': '',
            'name': 'node-2-2-2-2',
            'pod_count': 0,
            'resource_usage_cpu': None,
            'resource_usage_disk': None,
            'resource_usage_memory': None,
            'roles': '',
            'status': 'Ready',
            'taints': '',
        },
    ]
    assert_list_contains(actual, expect)
