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

from bkmonitor.models import BCSServiceMonitor
from core.testing import assert_list_contains


class TestBCSServiceMonitor:
    @pytest.mark.django_db
    def test_sync_resource_usage(
        self,
        monkeypatch,
        add_service_monitors,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"

        actual = BCSServiceMonitor.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        assert actual is None

        actual = [model_to_dict(model) for model in BCSServiceMonitor.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'endpoints': '',
                'labels': [],
                'metric_interval': '30s',
                'metric_path': '/metrics',
                'metric_port': 'https',
                'monitor_status': 'disabled',
                'name': 'namespace-operator-stack-api-server',
                'namespace': 'namespace-operator',
                'status': '',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'deleted_at': None,
                'endpoints': '',
                'labels': [],
                'metric_interval': '60s',
                'metric_path': '/metrics',
                'metric_port': 'http',
                'monitor_status': 'success',
                'name': 'namespace-operator-stack-api-server',
                'namespace': 'namespace_a',
                'status': '',
            },
        ]
        assert_list_contains(actual, expect)

        bk_biz_id = 100
        bcs_cluster_id = "BCS-K8S-00002"
        actual = BCSServiceMonitor.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        assert actual is None
        actual = [model_to_dict(model) for model in BCSServiceMonitor.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'deleted_at': None,
                'endpoints': '',
                'labels': [],
                'metric_interval': '30s',
                'metric_path': '/metrics',
                'metric_port': 'https',
                'monitor_status': 'disabled',
                'name': 'namespace-operator-stack-api-server',
                'namespace': 'namespace-operator',
                'status': '',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'deleted_at': None,
                'endpoints': '',
                'labels': [],
                'metric_interval': '60s',
                'metric_path': '/metrics',
                'metric_port': 'http',
                'monitor_status': 'disabled',
                'name': 'namespace-operator-stack-api-server',
                'namespace': 'namespace_a',
                'status': '',
            },
        ]
        assert_list_contains(actual, expect)
