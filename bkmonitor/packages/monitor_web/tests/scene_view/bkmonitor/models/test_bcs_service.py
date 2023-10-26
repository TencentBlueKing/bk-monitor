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

from api.bcs_storage.default import FetchResource
from bkmonitor.models import BCSService
from core.testing import assert_list_contains


class TestBCSService:
    @pytest.mark.django_db
    def test_load_list_from_api(self, monkeypatch, monkeypatch_bcs_storage_fetch_k8s_service_list_by_cluster):
        monkeypatch.setattr(FetchResource, "cache_type", None)

        models = BCSService.load_list_from_api({"BCS-K8S-00000": 2})
        actual = [model_to_dict(model) for model in models]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'cluster_ip': '1.1.1.1',
                'created_at': '2022-01-01T00:00:00Z',
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
                'created_at': '2022-01-01T00:00:00Z',
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

    @pytest.mark.django_db
    def test_sync_resource_usage(
        self,
        monkeypatch,
        add_bcs_pods,
        add_bcs_service,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
    ):
        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"

        actual = BCSService.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        assert actual is None

        actual = [model_to_dict(model) for model in BCSService.objects.all()]
        expect = [
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'cluster_ip': '1.1.1.1',
                'deleted_at': None,
                'endpoint_count': 4,
                'external_ip': '<none>',
                'labels': [],
                'monitor_status': 'success',
                'name': 'api-gateway',
                'namespace': 'bcs-system',
                'pod_count': 1,
                'pod_name_list': 'api-gateway-0',
                'ports': '9013:31001/TCP,9010:31000/TCP,9014:31003/TCP,9009:31002/TCP',
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
                'monitor_status': 'success',
                'name': 'api-gateway-etcd',
                'namespace': 'bcs-system',
                'pod_count': 1,
                'pod_name_list': 'api-gateway-etcd-0',
                'ports': '9012/TCP,9011/TCP',
                'status': '',
                'type': 'ClusterIP',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bk_biz_id': 2,
                'cluster_ip': '3.3.3.3',
                'deleted_at': None,
                'endpoint_count': 6,
                'external_ip': '<none>',
                'labels': [],
                'monitor_status': 'disabled',
                'name': 'elasticsearch-data',
                'namespace': 'namespace',
                'pod_count': 3,
                'pod_name_list': 'elasticsearch-data-2,elasticsearch-data-1,elasticsearch-data-0',
                'ports': '9200/TCP,9300/TCP',
                'status': '',
                'type': 'ClusterIP',
            },
            {
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bk_biz_id': 100,
                'cluster_ip': '3.3.3.3',
                'deleted_at': None,
                'endpoint_count': 6,
                'external_ip': '<none>',
                'labels': [],
                'monitor_status': '',
                'name': 'elasticsearch-data',
                'namespace': 'namespace_a',
                'pod_count': 3,
                'pod_name_list': 'elasticsearch-data-2,elasticsearch-data-1,elasticsearch-data-0',
                'ports': '9200/TCP,9300/TCP',
                'status': '',
                'type': 'ClusterIP',
            },
        ]
        assert_list_contains(actual, expect)
