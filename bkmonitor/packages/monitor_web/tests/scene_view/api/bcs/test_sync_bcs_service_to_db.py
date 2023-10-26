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

from api.bcs.tasks import sync_bcs_service
from api.bcs_storage.default import FetchResource
from bkmonitor.models import BCSLabel, BCSService
from core.testing import assert_list_contains

logger = logging.getLogger("kubernetes")

pytestmark = pytest.mark.django_db


def test_sync_bcs_service_to_db(
    monkeypatch, add_bcs_cluster_item_for_update_and_delete, monkeypatch_bcs_storage_fetch_k8s_service_list_by_cluster
):
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"

    BCSService.objects.all().delete()
    BCSLabel.objects.all().delete()

    service_models = sync_bcs_service(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(service_model) for service_model in service_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '1.1.1.1',
            'deleted_at': None,
            'endpoint_count': 4,
            'external_ip': '<none>',
            'labels': [],
            'monitor_status': '',
            'name': 'api-gateway',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-0',
            'ports': '9008:31001/TCP,9010:31000/TCP,9007:31003/TCP,9009:31002/TCP',
            'status': '',
            'type': 'NodePort',
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '2.2.2.2',
            'deleted_at': None,
            'endpoint_count': 2,
            'external_ip': '<none>',
            'labels': [],
            'monitor_status': '',
            'name': 'api-gateway-etcd',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-etcd-0',
            'ports': '9012/TCP,9011/TCP',
            'status': '',
            'type': 'ClusterIP',
        },
    ]
    assert_list_contains(actual, expect)


def test_sync_bcs_service_to_db_for_update(
    monkeypatch,
    add_bcs_service,
    add_bcs_cluster_item_for_update_and_delete,
    monkeypatch_bcs_storage_fetch_k8s_service_list_by_cluster,
):
    monkeypatch.setattr(FetchResource, "cache_type", None)

    bcs_cluster_id = "BCS-K8S-00000"
    service_models = sync_bcs_service(bcs_cluster_id=bcs_cluster_id)
    actual = [model_to_dict(service_model) for service_model in service_models]
    expect = [
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '1.1.1.1',
            'deleted_at': None,
            'endpoint_count': 4,
            'external_ip': '<none>',
            'labels': [],
            'monitor_status': '',
            'name': 'api-gateway',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-0',
            'ports': '9008:31001/TCP,9010:31000/TCP,9007:31003/TCP,9009:31002/TCP',
            'status': '',
            'type': 'NodePort',
        },
        {
            'bcs_cluster_id': 'BCS-K8S-00000',
            'bk_biz_id': 2,
            'cluster_ip': '2.2.2.2',
            'deleted_at': None,
            'endpoint_count': 2,
            'external_ip': '<none>',
            'labels': [],
            'monitor_status': '',
            'name': 'api-gateway-etcd',
            'namespace': 'bcs-system',
            'pod_count': 1,
            'pod_name_list': 'api-gateway-etcd-0',
            'ports': '9012/TCP,9011/TCP',
            'status': '',
            'type': 'ClusterIP',
        },
    ]
    assert_list_contains(actual, expect)
