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


class TestFetchK8sEventLogResourceResource:
    def test_fetch(self, monkeypatch, monkeypatch_kubernetes_fetch_k8s_event_log):
        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"

        params = {
            "start_time": 1663725331,
            "end_time": 1663728931,
            "where": [
                {"key": "type", "method": "eq", "value": ["Normal", "Warning"]},
                {"key": "name", "method": "eq", "value": ["bk-monitor-1-2"], "condition": "and"},
            ],
            "result_table_id": "2_bkmonitor_event_1",
            "limit": 0,
            "offset": 0,
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "select": ["count(dimensions.event_type) as event_type"],
            "group_by": ["dimensions.event_type"],
        }
        actual = api.kubernetes.fetch_k8s_event_log(params)
        expect = {
            '_shards': {'failed': 0, 'skipped': 0, 'successful': 2, 'total': 2},
            'aggregations': {
                'dimensions.type': {
                    'buckets': [
                        {
                            'doc_count': 638,
                            'key': 'Warning',
                            'time': {
                                'buckets': [
                                    {
                                        'doc_count': 53,
                                        'event_type': {'value': 0},
                                        'key': 1663746060000,
                                        'key_as_string': '1663746060000',
                                    },
                                    {
                                        'doc_count': 54,
                                        'event_type': {'value': 54},
                                        'key': 1663749360000,
                                        'key_as_string': '1663749360000',
                                    },
                                ]
                            },
                        },
                        {
                            'doc_count': 11,
                            'key': 'Normal',
                            'time': {
                                'buckets': [
                                    {
                                        'doc_count': 8,
                                        'event_type': {'value': 8},
                                        'key': 1663747320000,
                                        'key_as_string': '1663747320000',
                                    },
                                    {
                                        'doc_count': 3,
                                        'event_type': {'value': 3},
                                        'key': 1663747920000,
                                        'key_as_string': '1663747920000',
                                    },
                                ]
                            },
                        },
                    ],
                    'doc_count_error_upper_bound': 0,
                    'sum_other_doc_count': 0,
                }
            },
            'hits': {
                'hits': [
                    {
                        '_id': '1',
                        '_index': 'v2_namespace_event_1_2_0',
                        '_score': None,
                        '_source': {
                            'dimensions': {
                                'apiVersion': 'autoscaling/v2beta2',
                                'bcs_cluster_id': 'BCS-K8S-00000',
                                'bk_biz_id': '2',
                                'host': '',
                                'kind': 'HorizontalPodAutoscaler',
                                'name': 'hpa-soc-backend-scan-producer',
                                'namespace': 'namespace-1',
                                'type': 'Warning',
                            },
                            'event': {'content': 'missing request for ' 'memory', 'count': 20},
                            'event_name': 'FailedGetResourceMetric',
                            'target': 'horizontal-pod-autoscaler',
                            'time': '1663749405000',
                        },
                        '_type': '_doc',
                        'sort': [1663749405000000000],
                    },
                    {
                        '_id': '2',
                        '_index': 'v2_namespace_event_1_2_0',
                        '_score': None,
                        '_source': {
                            'dimensions': {
                                'apiVersion': 'autoscaling/v2beta2',
                                'bcs_cluster_id': 'BCS-K8S-00000',
                                'bk_biz_id': '2',
                                'host': '',
                                'kind': 'HorizontalPodAutoscaler',
                                'name': 'hpa-batch-scheduler-worker',
                                'namespace': 'namespace-1',
                                'type': 'Warning',
                            },
                            'event': {'content': 'missing request for cpu', 'count': 20},
                            'event_name': 'FailedGetResourceMetric',
                            'target': 'horizontal-pod-autoscaler',
                            'time': '1663749405000',
                        },
                        '_type': '_doc',
                        'sort': [1663749405000000000],
                    },
                ],
                'max_score': None,
                'total': {'relation': 'eq', 'value': 649},
            },
            'timed_out': False,
            'took': 27,
        }
        assert actual == expect
