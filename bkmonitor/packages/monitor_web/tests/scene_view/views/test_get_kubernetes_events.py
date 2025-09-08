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
import pytest

from core.drf_resource import resource


class TestGetKubernetesEvents:
    @pytest.mark.django_db
    def test_data_type_is_chart(self, monkeypatch_kubernetes_fetch_k8s_event_list):
        params = {
            "data_type": "chart",
            "result_table_id": "events",
            "data_source_label": "custom",
            "data_type_label": "event",
            "start_time": 1653393032,
            "end_time": 1653396632,
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_events(params)
        expect = {
            'metrics': [{'data_source_label': 'event', 'data_type_label': 'k8s', 'metric_field': 'result'}],
            'series': [
                {
                    'alias': '_result_',
                    'datapoints': [
                        [0, 1654578480000],
                        [0, 1654578540000],
                        [40, 1654578600000],
                        [0, 1654578660000],
                        [0, 1654578720000],
                        [0, 1654578780000],
                        [0, 1654578840000],
                        [0, 1654578900000],
                        [40, 1654578960000],
                        [0, 1654579020000],
                        [0, 1654579080000],
                        [0, 1654579140000],
                        [0, 1654579200000],
                        [40, 1654579260000],
                        [0, 1654579320000],
                        [0, 1654579380000],
                        [0, 1654579440000],
                        [0, 1654579500000],
                        [40, 1654579560000],
                        [0, 1654579620000],
                        [0, 1654579680000],
                        [0, 1654579740000],
                        [0, 1654579800000],
                        [40, 1654579860000],
                        [0, 1654579920000],
                        [0, 1654579980000],
                        [0, 1654580040000],
                        [0, 1654580100000],
                        [40, 1654580160000],
                        [0, 1654580220000],
                        [0, 1654580280000],
                        [0, 1654580340000],
                        [0, 1654580400000],
                        [40, 1654580460000],
                        [0, 1654580520000],
                        [0, 1654580580000],
                        [0, 1654580640000],
                        [0, 1654580700000],
                        [40, 1654580760000],
                        [0, 1654580820000],
                        [0, 1654580880000],
                        [0, 1654580940000],
                        [0, 1654581000000],
                        [40, 1654581060000],
                        [0, 1654581120000],
                        [0, 1654581180000],
                        [0, 1654581240000],
                        [0, 1654581300000],
                        [40, 1654581360000],
                        [0, 1654581420000],
                        [0, 1654581480000],
                        [0, 1654581540000],
                        [0, 1654581600000],
                        [40, 1654581660000],
                        [0, 1654581720000],
                        [0, 1654581780000],
                        [0, 1654581840000],
                        [0, 1654581900000],
                        [40, 1654581960000],
                        [0, 1654582020000],
                        [0, 1654582080000],
                    ],
                    'dimensions': {'kind': 'HorizontalPodAutoscaler'},
                    'metric_field': '_result_',
                    'stack': 'all',
                    'target': 'SUM(event){kind=HorizontalPodAutoscaler}',
                    'type': 'bar',
                }
            ],
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_data_type_is_events(self, monkeypatch_kubernetes_fetch_k8s_event_list):
        params = {
            "result_table_id": "events",
            "data_source_label": "custom",
            "data_type_label": "event",
            "data_format": "scene_view",
            "limit": 10,
            "offset": 0,
            "start_time": 1653393032,
            "end_time": 1653396632,
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_events(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'time',
                    'name': 'Time',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'namespace/name',
                    'name': 'Namespace/Name',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'event_name',
                    'name': 'Event Name',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'count',
                    'name': 'Count',
                    'props': {'width': 70},
                    'sortable': False,
                    'type': 'string',
                },
            ],
            'data': [
                {
                    'count': 20,
                    'data': {
                        '_id': '1',
                        '_index': 'v2_2_namespace_event_1_2_0',
                        '_score': None,
                        '_source': {
                            'dimensions': {
                                'bcs_cluster_id': 'BCS-K8S-40764',
                                'bk_biz_id': '551',
                                'kind': 'HorizontalPodAutoscaler',
                                'name': 'event-name-php',
                                'namespace': 'business-helm',
                            },
                            'event': {'content': 'failed to get memory ' 'utilization', 'count': 20},
                            'event_name': 'FailedGetResourceMetric',
                            'target': 'horizontal-pod-autoscaler',
                            'time': '1654581965000',
                        },
                        '_type': '_doc',
                        'sort': [1654581965000000000],
                    },
                    'event_name': 'FailedGetResourceMetric',
                    'kind': 'HorizontalPodAutoscaler',
                    'namespace/name': 'business-helm/event-name-php',
                    'time': '2022-06-07 14:06:05',
                }
            ],
            'total': 1,
        }
        assert actual == expect
