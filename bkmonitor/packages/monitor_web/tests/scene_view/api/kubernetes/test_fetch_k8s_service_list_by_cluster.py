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
from api.bcs_storage.default import FetchResource
from api.kubernetes.default import FetchK8sServiceListByClusterResource
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import api


class TestFetchK8sServiceListByClusterResource:
    def test_fetch(self, monkeypatch, monkeypatch_bcs_storage_fetch_k8s_service_list_by_cluster):
        monkeypatch.setattr(FetchK8sServiceListByClusterResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"

        actual = api.kubernetes.fetch_k8s_service_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        expect = [
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'cluster': 'BCS-K8S-00000',
                'cluster_ip': '1.1.1.1',
                'created_at': '2022-01-01T00:00:00Z',
                'endpoint_count': 4,
                'external_ip': '<none>',
                'labels': {},
                'name': 'api-gateway',
                'namespace': 'bcs-system',
                'pod_count': 1,
                'pod_name': ['api-gateway-0'],
                'ports': ['9008:31001/TCP', '9010:31000/TCP', '9007:31003/TCP', '9009:31002/TCP'],
                'type': 'NodePort',
            },
            {
                'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                'bcs_cluster_id': 'BCS-K8S-00000',
                'cluster': 'BCS-K8S-00000',
                'cluster_ip': '2.2.2.2',
                'created_at': '2022-01-01T00:00:00Z',
                'endpoint_count': 2,
                'external_ip': '<none>',
                'labels': {},
                'name': 'api-gateway-etcd',
                'namespace': 'bcs-system',
                'pod_count': 1,
                'pod_name': ['api-gateway-etcd-0'],
                'ports': ['9012/TCP', '9011/TCP'],
                'type': 'ClusterIP',
            },
        ]

        assert actual == expect
