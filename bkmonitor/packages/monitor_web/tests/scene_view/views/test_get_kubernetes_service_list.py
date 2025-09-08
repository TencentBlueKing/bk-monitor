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

from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import resource
from monitor_web.constants import OVERVIEW_ICON

FILTER = [
    {'id': 'success', 'name': 0, 'status': 'success', 'tips': '正常'},
    {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
    {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
]
SORT = [{'id': 'endpoint_count', 'name': 'Endpoint数量'}, {'id': 'pod_count', 'name': 'Pod数量'}]

DATA = [
    {
        'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
        'bcs_cluster_id': {
            'target': 'blank',
            'url': (
                '?bizId=100#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"}]}'
            ),
            'value': 'BCS-K8S-00002',
        },
        'cluster_ip': '3.3.3.3',
        'endpoint_count': 6,
        'external_ip': '<none>',
        'monitor_status': {'text': '异常', 'type': 'failed'},
        'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'elasticsearch-data'},
        'namespace': 'namespace_a',
        'pod_count': {'label': 3, 'status': 'SUCCESS', 'value': 100.0},
        'pod_name_list': ['elasticsearch-data-2', 'elasticsearch-data-1', 'elasticsearch-data-0'],
        'ports': ['9200/TCP', '9300/TCP'],
        'type': 'ClusterIP',
    }
]


class TestGetKubernetesServiceList:
    @pytest.mark.django_db
    def test_perform_request(self, add_bcs_cluster_item_for_update_and_delete, add_bcs_service):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": 100,
            "sort": "-pod_count",
        }
        actual = resource.scene_view.get_kubernetes_service_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '服务名称',
                    'overview_name': '概览',
                    'type': 'link',
                    'width': 248,
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'pod_count',
                    'min_width': 120,
                    'name': 'Pod数量',
                    'sortable': False,
                    'type': 'progress',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'BCS-K8S-00002', 'value': 'BCS-K8S-00002'}],
                    'filterable': True,
                    'id': 'bcs_cluster_id',
                    'min_width': 120,
                    'name': '集群ID',
                    'type': 'link',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'namespace_a', 'value': 'namespace_a'}],
                    'filterable': True,
                    'id': 'namespace',
                    'min_width': 120,
                    'name': 'NameSpace',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'monitor_status',
                    'min_width': 120,
                    'name': '采集状态',
                    'type': 'status',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'ClusterIP', 'value': 'ClusterIP'}],
                    'filterable': True,
                    'id': 'type',
                    'min_width': 120,
                    'name': '类型',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'cluster_ip',
                    'min_width': 120,
                    'name': 'Cluster IP',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'external_ip',
                    'min_width': 120,
                    'name': 'External IP',
                    'type': 'string',
                },
                {'checked': False, 'disabled': False, 'id': 'ports', 'min_width': 120, 'name': 'Ports', 'type': 'list'},
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'endpoint_count',
                    'min_width': 120,
                    'name': 'Endpoint数量',
                    'sortable': False,
                    'type': 'number',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'pod_name_list',
                    'min_width': 120,
                    'name': 'Pod名称',
                    'type': 'list',
                },
                {'checked': True, 'disabled': False, 'id': 'age', 'min_width': 120, 'name': '存活时间', 'type': 'string'},
            ],
            'condition_list': [
                {
                    'children': [{'id': 'BCS-K8S-00002', 'name': 'BCS-K8S-00002'}],
                    'id': 'bcs_cluster_id',
                    'multiable': False,
                    'name': 'cluster',
                },
                {
                    'children': [{'id': 'namespace_a', 'name': 'namespace_a'}],
                    'id': 'namespace',
                    'multiable': False,
                    'name': 'namespace',
                },
            ],
            'data': DATA,
            'filter': FILTER,
            'overview_data': {
                'age': '',
                'bcs_cluster_id': '',
                'cluster_ip': '',
                'endpoint_count': 6,
                'external_ip': '',
                'monitor_status': '',
                'name': {'icon': OVERVIEW_ICON, 'key': '', 'target': 'null_event', 'url': '', 'value': '概览'},
                'namespace': '',
                'pod_count': {'label': 3, 'status': 'SUCCESS', 'value': 100},
                'pod_name_list': '',
                'ports': '',
                'type': '',
            },
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_service,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": -3,
            "sort": "-pod_count",
        }
        actual = resource.scene_view.get_kubernetes_service_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '服务名称',
                    'overview_name': '概览',
                    'type': 'link',
                    'width': 248,
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'pod_count',
                    'min_width': 120,
                    'name': 'Pod数量',
                    'sortable': False,
                    'type': 'progress',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [
                        {'text': 'BCS-K8S-00000', 'value': 'BCS-K8S-00000'},
                        {'text': 'BCS-K8S-00002', 'value': 'BCS-K8S-00002'},
                    ],
                    'filterable': True,
                    'id': 'bcs_cluster_id',
                    'min_width': 120,
                    'name': '集群ID',
                    'type': 'link',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [
                        {'text': 'bcs-system', 'value': 'bcs-system'},
                        {'text': 'namespace', 'value': 'namespace'},
                        {'text': 'namespace_a', 'value': 'namespace_a'},
                    ],
                    'filterable': True,
                    'id': 'namespace',
                    'min_width': 120,
                    'name': 'NameSpace',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'monitor_status',
                    'min_width': 120,
                    'name': '采集状态',
                    'type': 'status',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [
                        {'text': 'ClusterIP', 'value': 'ClusterIP'},
                        {'text': 'NodePort', 'value': 'NodePort'},
                    ],
                    'filterable': True,
                    'id': 'type',
                    'min_width': 120,
                    'name': '类型',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'cluster_ip',
                    'min_width': 120,
                    'name': 'Cluster IP',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'external_ip',
                    'min_width': 120,
                    'name': 'External IP',
                    'type': 'string',
                },
                {'checked': False, 'disabled': False, 'id': 'ports', 'min_width': 120, 'name': 'Ports', 'type': 'list'},
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'endpoint_count',
                    'min_width': 120,
                    'name': 'Endpoint数量',
                    'sortable': False,
                    'type': 'number',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'pod_name_list',
                    'min_width': 120,
                    'name': 'Pod名称',
                    'type': 'list',
                },
                {'checked': True, 'disabled': False, 'id': 'age', 'min_width': 120, 'name': '存活时间', 'type': 'string'},
            ],
            'condition_list': [
                {
                    'children': [
                        {'id': 'BCS-K8S-00000', 'name': 'BCS-K8S-00000'},
                        {'id': 'BCS-K8S-00002', 'name': 'BCS-K8S-00002'},
                    ],
                    'id': 'bcs_cluster_id',
                    'multiable': False,
                    'name': 'cluster',
                },
                {
                    'children': [
                        {'id': 'bcs-system', 'name': 'bcs-system'},
                        {'id': 'namespace', 'name': 'namespace'},
                        {'id': 'namespace_a', 'name': 'namespace_a'},
                    ],
                    'id': 'namespace',
                    'multiable': False,
                    'name': 'namespace',
                },
            ],
            'data': [
                {
                    'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'bcs_cluster_id': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                            '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"}]}'
                        ),
                        'value': 'BCS-K8S-00002',
                    },
                    'cluster_ip': '3.3.3.3',
                    'endpoint_count': 6,
                    'external_ip': '<none>',
                    'monitor_status': {'text': '异常', 'type': 'failed'},
                    'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'elasticsearch-data'},
                    'namespace': 'namespace_a',
                    'pod_count': {'label': 3, 'status': 'SUCCESS', 'value': 37.5},
                    'pod_name_list': ['elasticsearch-data-2', 'elasticsearch-data-1', 'elasticsearch-data-0'],
                    'ports': ['9200/TCP', '9300/TCP'],
                    'type': 'ClusterIP',
                }
            ],
            'filter': FILTER,
            'overview_data': {
                'age': '',
                'bcs_cluster_id': '',
                'cluster_ip': '',
                'endpoint_count': 18,
                'external_ip': '',
                'monitor_status': '',
                'name': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'namespace': '',
                'pod_count': {'label': 8, 'status': 'SUCCESS', 'value': 100},
                'pod_name_list': '',
                'ports': '',
                'type': '',
            },
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect
