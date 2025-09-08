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

COLUMNS = [
    {
        'checked': True,
        'disabled': False,
        'id': 'name',
        'max_width': 300,
        'min_width': 120,
        'name': '工作负载名称',
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
        'filter_list': [{'text': 'BCS-K8S-00000', 'value': 'BCS-K8S-00000'}],
        'filterable': True,
        'id': 'bcs_cluster_id',
        'min_width': 120,
        'name': '集群ID',
        'type': 'link',
    },
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'bcs-system', 'value': 'bcs-system'}],
        'filterable': True,
        'id': 'namespace',
        'min_width': 120,
        'name': 'NameSpace',
        'type': 'string',
    },
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'success', 'value': 'success'}],
        'filterable': True,
        'id': 'status',
        'min_width': 120,
        'name': '运行状态',
        'type': 'string',
    },
    {'checked': False, 'disabled': False, 'id': 'monitor_status', 'min_width': 120, 'name': '采集状态', 'type': 'status'},
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'Deployment', 'value': 'Deployment'}],
        'filterable': True,
        'id': 'type',
        'min_width': 120,
        'name': '类型',
        'type': 'string',
    },
    {'checked': False, 'disabled': False, 'id': 'images', 'min_width': 120, 'name': '镜像', 'type': 'string'},
    {'checked': False, 'disabled': False, 'id': 'label_list', 'min_width': 120, 'name': '标签', 'type': 'kv'},
    {'checked': False, 'disabled': False, 'id': 'container_count', 'min_width': 120, 'name': '容器数量', 'type': 'link'},
    {'checked': False, 'disabled': False, 'id': 'resources', 'min_width': 120, 'name': '资源', 'type': 'kv'},
    {'checked': True, 'disabled': False, 'id': 'age', 'min_width': 120, 'name': '存活时间', 'type': 'string'},
]
CONDITION_LIST = [
    {
        'children': [{'id': 'BCS-K8S-00000', 'name': 'BCS-K8S-00000'}],
        'id': 'bcs_cluster_id',
        'multiable': False,
        'name': 'cluster',
    },
    {
        'children': [{'id': 'bcs-system', 'name': 'bcs-system'}],
        'id': 'namespace',
        'multiable': False,
        'name': 'namespace',
    },
    {
        'children': [{'id': 'Deployment', 'name': 'Deployment'}],
        'id': 'type',
        'multiable': False,
        'name': 'workload_type',
    },
    {
        'children': [{'id': 'success', 'name': 'success'}],
        'id': 'status',
        'multiable': False,
        'name': 'status',
    },
]
FILTER = [
    {'id': 'success', 'name': 1, 'status': 'success', 'tips': '正常'},
    {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
    {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
]
OVERVIEW_DATA = {
    'age': '',
    'bcs_cluster_id': '',
    'container_count': {
        'target': 'blank',
        'url': '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=overview',
        'value': 0,
    },
    'images': '',
    'label_list': '',
    'monitor_status': '',
    'name': {
        'icon': OVERVIEW_ICON,
        'key': '',
        'target': 'null_event',
        'url': '',
        'value': '概览',
    },
    'namespace': '',
    'pod_count': {'label': 1, 'status': 'SUCCESS', 'value': 100},
    'resources': '',
    'status': '',
    'type': '',
}
SORT = [{'id': 'pod_count', 'name': 'Pod数量'}]

COLUMNS_BY_SPACE_ID = [
    {
        'checked': True,
        'disabled': False,
        'id': 'name',
        'max_width': 300,
        'min_width': 120,
        'name': '工作负载名称',
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
        'filter_list': [{'text': 'bcs-system', 'value': 'bcs-system'}, {'text': 'namespace_a', 'value': 'namespace_a'}],
        'filterable': True,
        'id': 'namespace',
        'min_width': 120,
        'name': 'NameSpace',
        'type': 'string',
    },
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'success', 'value': 'success'}],
        'filterable': True,
        'id': 'status',
        'min_width': 120,
        'name': '运行状态',
        'type': 'string',
    },
    {'checked': False, 'disabled': False, 'id': 'monitor_status', 'min_width': 120, 'name': '采集状态', 'type': 'status'},
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'Deployment', 'value': 'Deployment'}],
        'filterable': True,
        'id': 'type',
        'min_width': 120,
        'name': '类型',
        'type': 'string',
    },
    {'checked': False, 'disabled': False, 'id': 'images', 'min_width': 120, 'name': '镜像', 'type': 'string'},
    {'checked': False, 'disabled': False, 'id': 'label_list', 'min_width': 120, 'name': '标签', 'type': 'kv'},
    {'checked': False, 'disabled': False, 'id': 'container_count', 'min_width': 120, 'name': '容器数量', 'type': 'link'},
    {'checked': False, 'disabled': False, 'id': 'resources', 'min_width': 120, 'name': '资源', 'type': 'kv'},
    {'checked': True, 'disabled': False, 'id': 'age', 'min_width': 120, 'name': '存活时间', 'type': 'string'},
]
CONDITION_LIST_BY_SPACE_ID = [
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
            {'id': 'namespace_a', 'name': 'namespace_a'},
        ],
        'id': 'namespace',
        'multiable': False,
        'name': 'namespace',
    },
    {
        'children': [{'id': 'Deployment', 'name': 'Deployment'}],
        'id': 'type',
        'multiable': False,
        'name': 'workload_type',
    },
    {
        'children': [{'id': 'success', 'name': 'success'}],
        'id': 'status',
        'multiable': False,
        'name': 'status',
    },
]
OVERVIEW_DATA_BY_SPACE_ID = {
    'age': '',
    'bcs_cluster_id': '',
    'container_count': {
        'target': 'blank',
        'url': '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=overview',
        'value': 0,
    },
    'images': '',
    'label_list': '',
    'monitor_status': '',
    'name': {
        'icon': OVERVIEW_ICON,
        'key': '',
        'target': 'null_event',
        'url': '',
        'value': '概览',
    },
    'namespace': '',
    'pod_count': {'label': 2, 'status': 'SUCCESS', 'value': 100},
    'resources': '',
    'status': '',
    'type': '',
}


class TestGetKubernetesWorkloadList:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_workloads,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter": "",
            "page": 1,
            "page_size": 10,
            "keyword": "",
            "condition_list": [{"status": "success"}],
            "bk_biz_id": 2,
            "sort": "-pod_count",
        }
        actual = resource.scene_view.get_kubernetes_workload_list(params)
        expect = {
            'columns': COLUMNS,
            'condition_list': CONDITION_LIST,
            'data': [
                {
                    'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'bcs_cluster_id': {
                        'target': 'blank',
                        'url': (
                            '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                            '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                        ),
                        'value': 'BCS-K8S-00000',
                    },
                    'container_count': {
                        'target': 'blank',
                        'url': (
                            '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                            '&queryData={"selectorSearch":['
                            '{"bcs_cluster_id":"BCS-K8S-00000"},'
                            '{"workload_name":"bcs-cluster-manager"}]}'
                        ),
                        'value': 0,
                    },
                    'images': 'images',
                    'label_list': [],
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'bcs-cluster-manager'},
                    'namespace': 'bcs-system',
                    'pod_count': {'label': 1, 'status': 'SUCCESS', 'value': 100},
                    'resources': [
                        {'key': 'requests memory', 'value': '2GB'},
                        {'key': 'limits cpu', 'value': '2000m'},
                        {'key': 'limits memory', 'value': '2GB'},
                    ],
                    'status': 'success',
                    'type': 'Deployment',
                }
            ],
            'filter': FILTER,
            'overview_data': OVERVIEW_DATA,
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_status_is_disabled(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_workloads,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "status": "disabled",
            "page": 1,
            "page_size": 10,
            "keyword": "",
            "condition_list": [],
            "bk_biz_id": 2,
            "sort": "-pod_count",
        }
        actual = resource.scene_view.get_kubernetes_workload_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '工作负载名称',
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
                    'filter_list': [{'text': 'BCS-K8S-00000', 'value': 'BCS-K8S-00000'}],
                    'filterable': True,
                    'id': 'bcs_cluster_id',
                    'min_width': 120,
                    'name': '集群ID',
                    'type': 'link',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'bcs-system', 'value': 'bcs-system'}],
                    'filterable': True,
                    'id': 'namespace',
                    'min_width': 120,
                    'name': 'NameSpace',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'success', 'value': 'success'}],
                    'filterable': True,
                    'id': 'status',
                    'min_width': 120,
                    'name': '运行状态',
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
                    'filter_list': [{'text': 'Deployment', 'value': 'Deployment'}],
                    'filterable': True,
                    'id': 'type',
                    'min_width': 120,
                    'name': '类型',
                    'type': 'string',
                },
                {'checked': False, 'disabled': False, 'id': 'images', 'min_width': 120, 'name': '镜像', 'type': 'string'},
                {'checked': False, 'disabled': False, 'id': 'label_list', 'min_width': 120, 'name': '标签', 'type': 'kv'},
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'container_count',
                    'min_width': 120,
                    'name': '容器数量',
                    'type': 'link',
                },
                {'checked': False, 'disabled': False, 'id': 'resources', 'min_width': 120, 'name': '资源', 'type': 'kv'},
                {'checked': True, 'disabled': False, 'id': 'age', 'min_width': 120, 'name': '存活时间', 'type': 'string'},
            ],
            'condition_list': CONDITION_LIST,
            'data': [],
            'filter': [
                {'id': 'success', 'name': 1, 'status': 'success', 'tips': '正常'},
                {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
                {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
            ],
            'sort': SORT,
            'overview_data': OVERVIEW_DATA,
            'total': 0,
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_workloads,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [],
            "bk_biz_id": -3,
            "sort": "-pod_count",
        }
        actual = resource.scene_view.get_kubernetes_workload_list(params)
        expect = {
            'columns': COLUMNS_BY_SPACE_ID,
            'condition_list': CONDITION_LIST_BY_SPACE_ID,
            'data': [
                {
                    'age': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'bcs_cluster_id': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                            '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                        ),
                        'value': 'BCS-K8S-00000',
                    },
                    'container_count': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                            '&queryData={"selectorSearch":['
                            '{"bcs_cluster_id":"BCS-K8S-00000"},'
                            '{"workload_name":"bcs-cluster-manager"}]}'
                        ),
                        'value': 0,
                    },
                    'images': 'images',
                    'label_list': [],
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'bcs-cluster-manager'},
                    'namespace': 'bcs-system',
                    'pod_count': {'label': 1, 'status': 'SUCCESS', 'value': 50.0},
                    'resources': [
                        {'key': 'requests memory', 'value': '2GB'},
                        {'key': 'limits cpu', 'value': '2000m'},
                        {'key': 'limits memory', 'value': '2GB'},
                    ],
                    'status': 'success',
                    'type': 'Deployment',
                },
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
                    'container_count': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                            '&queryData={"selectorSearch":['
                            '{"bcs_cluster_id":"BCS-K8S-00002"},'
                            '{"workload_name":"bcs-cluster-manager"}]}'
                        ),
                        'value': 0,
                    },
                    'images': 'images',
                    'label_list': [],
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'bcs-cluster-manager'},
                    'namespace': 'namespace_a',
                    'pod_count': {'label': 1, 'status': 'SUCCESS', 'value': 50.0},
                    'resources': [
                        {'key': 'requests memory', 'value': '2GB'},
                        {'key': 'limits cpu', 'value': '2000m'},
                        {'key': 'limits memory', 'value': '2GB'},
                    ],
                    'status': 'success',
                    'type': 'Deployment',
                },
            ],
            'filter': [
                {'id': 'success', 'name': 2, 'status': 'success', 'tips': '正常'},
                {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
                {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
            ],
            'overview_data': OVERVIEW_DATA_BY_SPACE_ID,
            'sort': SORT,
            'total': 2,
        }
        assert actual == expect
