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
        'label_list': [],
        'metric_interval': '60s',
        'metric_path': '/metrics',
        'metric_port': 'http',
        'monitor_status': {'text': '正常', 'type': 'success'},
        'name': 'namespace-operator-stack-api-server',
        'namespace': 'namespace_a',
    }
]
FILTER = [
    {'id': 'success', 'name': 1, 'status': 'success', 'tips': '正常'},
    {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
    {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
]


class TestGetKubernetesServiceMonitorList:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_service_monitors,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [
                {"bcs_cluster_id": "BCS-K8S-00002"},
            ],
            "data": DATA,
            "bk_biz_id": 100,
        }
        actual = resource.scene_view.get_kubernetes_service_monitor_list(params)
        expect = {
            "columns": [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 400,
                    'min_width': 120,
                    'name': '名称',
                    'type': 'string',
                    'width': 248,
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
                    'id': 'metric_path',
                    'min_width': 120,
                    'name': 'Metric路径',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'metric_port',
                    'min_width': 120,
                    'name': '端口',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'metric_interval',
                    'min_width': 120,
                    'name': '周期(s)',
                    'type': 'string',
                },
                {'checked': False, 'disabled': False, 'id': 'label_list', 'min_width': 120, 'name': '标签', 'type': 'kv'},
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
            'sort': [],
            'total': 1,
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_service_monitors,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [
                {"bcs_cluster_id": "BCS-K8S-00002"},
            ],
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_service_monitor_list(params)
        expect = {
            "columns": [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 400,
                    'min_width': 120,
                    'name': '名称',
                    'type': 'string',
                    'width': 248,
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
                        {'text': 'namespace-operator', 'value': 'namespace-operator'},
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
                    'id': 'metric_path',
                    'min_width': 120,
                    'name': 'Metric路径',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'metric_port',
                    'min_width': 120,
                    'name': '端口',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'metric_interval',
                    'min_width': 120,
                    'name': '周期(s)',
                    'type': 'string',
                },
                {'checked': False, 'disabled': False, 'id': 'label_list', 'min_width': 120, 'name': '标签', 'type': 'kv'},
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
                        {'id': 'namespace-operator', 'name': 'namespace-operator'},
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
                    'label_list': [],
                    'metric_interval': '60s',
                    'metric_path': '/metrics',
                    'metric_port': 'http',
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': 'namespace-operator-stack-api-server',
                    'namespace': 'namespace_a',
                }
            ],
            'filter': FILTER,
            'sort': [],
            'total': 1,
        }
        assert actual == expect
