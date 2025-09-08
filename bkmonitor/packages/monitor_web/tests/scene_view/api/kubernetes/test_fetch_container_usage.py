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
from core.drf_resource import api


class TestFetchContainerUsage:
    def test_bulk_request(self, monkeypatch, monkeypatch_kubernetes_fetch_container_usage):
        bcs_cluster_id = "BCS-K8S-00000"
        bk_biz_id = 2

        usage_types = ["cpu", "memory", "disk"]
        group_by = ["namespace", "pod_name", "container_name"]
        bulk_params = [
            {
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
                "group_by": group_by,
                "usage_type": usage_type,
            }
            for usage_type in usage_types
        ]
        actual = api.kubernetes.fetch_container_usage.bulk_request(bulk_params)
        expect = [
            {
                'data': [
                    {
                        '_result_': 0.0008446444444444978,
                        '_time_': 1653128820000,
                        'container_name': 'api',
                        'namespace': 'namespace',
                        'pod_name': 'api-beat-77c5869696-dc4lj',
                    },
                    {
                        '_result_': 0.019931466666669926,
                        '_time_': 1653128820000,
                        'container_name': 'api',
                        'namespace': 'namespace',
                        'pod_name': 'api-web-5fc88fff94-d6sk2',
                    },
                    {
                        '_result_': 0.0027477777777777292,
                        '_time_': 1653128820000,
                        'container_name': 'api',
                        'namespace': 'namespace',
                        'pod_name': 'api-worker-79df54ffdb-7t66d',
                    },
                    {
                        '_result_': 0.017046800000005326,
                        '_time_': 1653128820000,
                        'container_name': 'api-server',
                        'namespace': 'namespace',
                        'pod_name': 'api-server-79dccc877b-6nmbw',
                    },
                ],
                'usage_type': 'cpu',
            },
            {
                'data': [
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'api-gateway-0',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'api-gateway-etcd-0',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'replicaSet-cl9mc',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'bcs-etcd-0',
                    },
                ],
                'usage_type': 'memory',
            },
            {
                'data': [
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'api-gateway-0',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'api-gateway-etcd-0',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'replicaSet-cl9mc',
                    },
                    {
                        '_result_': 131072,
                        '_time_': 1653128820000,
                        'container_name': 'POD',
                        'namespace': 'bcs-system',
                        'pod_name': 'bcs-etcd-0',
                    },
                ],
                'usage_type': 'disk',
            },
        ]
        assert actual == expect
