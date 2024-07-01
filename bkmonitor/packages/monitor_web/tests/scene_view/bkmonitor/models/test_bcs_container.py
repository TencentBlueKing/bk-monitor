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
from django.forms.models import model_to_dict

from bkmonitor.models import BCSContainer
from core.testing import assert_list_contains


class TestBCSContainer:
    @pytest.mark.django_db(databases=["default", "monitor_api"])
    @pytest.mark.parametrize("bcs_cluster_id", ["BCS-K8S-00000", None])
    def test_sync_resource_usage(
        self, add_bcs_containers, monkeypatch_kubernetes_fetch_container_usage, bcs_cluster_id
    ):
        bk_biz_id = 2
        BCSContainer.sync_resource_usage(bk_biz_id, bcs_cluster_id)

        actual = [model_to_dict(model) for model in BCSContainer.objects.filter(bk_biz_id=bk_biz_id)]
        expect = [
            {
                'bk_biz_id': 2,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'namespace': 'bcs-system',
                'pod_name': 'api-gateway-0',
                'name': 'apisix',
                'resource_usage_cpu': 0.001,
                'resource_usage_disk': 131074,
                'resource_usage_memory': 131072,
                'monitor_status': 'success',
            },
            # cpu 无数据，状态为 disabled
            {
                'bk_biz_id': 2,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'namespace': 'bcs-system',
                'pod_name': 'api-gateway-0',
                'name': 'gateway-discovery',
                'resource_usage_cpu': None,
                'resource_usage_disk': 131075,
                'resource_usage_memory': 131073,
                'monitor_status': 'disabled',
            },
            # 全部没有，重置
            {
                'bk_biz_id': 2,
                'bcs_cluster_id': 'BCS-K8S-00000',
                'namespace': 'bcs-system',
                'pod_name': 'api-gateway-etcd-0',
                'name': 'etcd',
                'resource_usage_cpu': None,
                'resource_usage_disk': None,
                'resource_usage_memory': None,
                'monitor_status': 'disabled',
            },
        ]
        assert_list_contains(actual, expect)
