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
from django.db.models import Q
from django.forms.models import model_to_dict

from bkmonitor.models import BCSWorkload
from core.testing import assert_list_contains


class TestBCSWorkload:
    @pytest.mark.django_db
    def test_sync_resource_usage(self, add_bcs_pods, add_workloads):
        bcs_cluster_id = "BCS-K8S-00000"
        bk_biz_id = 2

        actual = BCSWorkload.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        expect = None
        assert actual == expect

        actual = [model_to_dict(model) for model in BCSWorkload.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'container_count': 0,
                'deleted_at': None,
                'images': 'images',
                'labels': [],
                'monitor_status': 'success',
                'name': 'bcs-cluster-manager',
                'namespace': 'bcs-system',
                'pod_count': 1,
                'pod_name_list': 'api-gateway-0',
                'resource_limits_cpu': 2.0,
                'resource_limits_memory': 2147483648,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 2147483648,
                'resource_usage_cpu': 0.0,
                'resource_usage_disk': 0,
                'resource_usage_memory': 0,
                'status': 'success',
                'type': 'Deployment',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'container_count': 0,
                'deleted_at': None,
                'images': 'images',
                'labels': [],
                'monitor_status': 'success',
                'name': 'bcs-cluster-manager',
                'namespace': 'namespace_a',
                'pod_count': 1,
                'pod_name_list': 'api-gateway-0',
                'resource_limits_cpu': 2.0,
                'resource_limits_memory': 2147483648,
                'resource_requests_cpu': 0.0,
                'resource_requests_memory': 2147483648,
                'resource_usage_cpu': 0.0,
                'resource_usage_disk': 0,
                'resource_usage_memory': 0,
                'status': 'success',
                'type': 'Deployment',
            },
        ]
        assert_list_contains(actual, expect)

    @pytest.mark.django_db
    def test_count_status_quantity(self, add_workloads):
        query_set_list = [Q()]
        actual = BCSWorkload.objects.count_service_status_quantity(query_set_list)
        expect = {'success': 2}
        assert actual == expect

        actual = BCSWorkload.objects.count_service_status_quantity(None)
        expect = {'success': 2}
        assert actual == expect
