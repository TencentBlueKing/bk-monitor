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
    {'id': 'disabled', 'name': 1, 'status': 'disabled', 'tips': '无数据'},
]
SORT = [
    {'id': 'resource_usage_cpu', 'name': 'CPU使用量'},
    {'id': 'resource_usage_memory', 'name': '内存使用量'},
    {'id': 'resource_usage_disk', 'name': '磁盘使用量'},
]
DATA = [
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
        'image': 'docker.io/host/etcd:latest',
        'monitor_status': {'text': '无数据', 'type': 'disabled'},
        'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'etcd'},
        'namespace': 'namespace_a',
        'node_ip': {
            'target': 'blank',
            'url': (
                '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"ip":"2.2.2.2"}]}'
            ),
            'value': '2.2.2.2',
        },
        'node_name': {
            'target': 'blank',
            'url': (
                '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"node-2-2-2-2"}]}'
            ),
            'value': 'node-2-2-2-2',
        },
        'pod_name': {
            'target': 'blank',
            'url': (
                '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"api-gateway-etcd-0"}]}'
            ),
            'value': 'api-gateway-etcd-0',
        },
        'resource_usage_cpu': '',
        'resource_usage_disk': '',
        'resource_usage_memory': '',
        'status': 'running',
        'workload': {
            'target': 'blank',
            'url': (
                '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=detail'
                '&queryData={"selectorSearch":['
                '{"bcs_cluster_id":"BCS-K8S-00002"},{"workload_type":"StatefulSet"},{"name":"api-gateway-etcd"}]}'
            ),
            'value': 'StatefulSet:api-gateway-etcd',
        },
    }
]


class TestGetKubernetesContainerList:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_containers,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": 100,
        }
        actual = resource.scene_view.get_kubernetes_container_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '容器名称',
                    'overview_name': '概览',
                    'type': 'link',
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
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'running', 'value': 'running'}],
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
                    'id': 'pod_name',
                    'min_width': 120,
                    'name': 'Pod名称',
                    'type': 'link',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'workload',
                    'min_width': 120,
                    'name': '工作负载',
                    'type': 'link',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'node_name',
                    'min_width': 120,
                    'name': '节点名称',
                    'type': 'link',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'node_ip',
                    'min_width': 120,
                    'name': '节点IP',
                    'type': 'link',
                },
                {'checked': False, 'disabled': False, 'id': 'image', 'min_width': 120, 'name': '镜像', 'type': 'string'},
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_cpu',
                    'min_width': 120,
                    'name': 'CPU使用量',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_memory',
                    'min_width': 120,
                    'name': '内存使用量',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_disk',
                    'min_width': 120,
                    'name': '磁盘使用量',
                    'sortable': False,
                    'type': 'string',
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
                {
                    'children': [{'id': 'StatefulSet', 'name': 'StatefulSet'}],
                    'id': 'workload_type',
                    'multiable': False,
                    'name': 'workload_type',
                },
                {
                    'children': [{'id': 'api-gateway-etcd', 'name': 'api-gateway-etcd'}],
                    'id': 'workload_name',
                    'multiable': False,
                    'name': 'workload_name',
                },
                {
                    'children': [{'id': 'api-gateway-etcd-0', 'name': 'api-gateway-etcd-0'}],
                    'id': 'pod_name',
                    'multiable': False,
                    'name': 'pod_name',
                },
                {
                    'children': [{'id': '2.2.2.2', 'name': '2.2.2.2'}],
                    'id': 'node_ip',
                    'multiable': False,
                    'name': 'node_ip',
                },
                {
                    'children': [{'id': 'running', 'name': 'running'}],
                    'id': 'status',
                    'multiable': False,
                    'name': 'status',
                },
            ],
            'data': [
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
                    'image': 'docker.io/host/etcd:latest',
                    'monitor_status': {'text': '无数据', 'type': 'disabled'},
                    'name': {'icon': '', 'key': '', 'target': 'null_event', 'url': '', 'value': 'etcd'},
                    'namespace': 'namespace_a',
                    'node_ip': {
                        'target': 'blank',
                        'url': (
                            '?bizId=100#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                            '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"ip":"2.2.2.2"}]}'
                        ),
                        'value': '2.2.2.2',
                    },
                    'node_name': {
                        'target': 'blank',
                        'url': (
                            '?bizId=100#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                            '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"node-2-2-2-2"}]}'
                        ),
                        'value': 'node-2-2-2-2',
                    },
                    'pod_name': {
                        'target': 'blank',
                        'url': (
                            '?bizId=100#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                            '&queryData={"selectorSearch":['
                            '{"bcs_cluster_id":"BCS-K8S-00002"},'
                            '{"name":"api-gateway-etcd-0"}]}'
                        ),
                        'value': 'api-gateway-etcd-0',
                    },
                    'resource_usage_cpu': '',
                    'resource_usage_disk': '',
                    'resource_usage_memory': '',
                    'status': 'running',
                    'workload': {
                        'target': 'blank',
                        'url': (
                            '?bizId=100#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=detail'
                            '&queryData={"selectorSearch":'
                            '[{"bcs_cluster_id":"BCS-K8S-00002"},'
                            '{"workload_type":"StatefulSet"},'
                            '{"name":"api-gateway-etcd"}]}'
                        ),
                        'value': 'StatefulSet:api-gateway-etcd',
                    },
                }
            ],
            'filter': FILTER,
            'overview_data': {
                'age': '',
                'bcs_cluster_id': '',
                'image': '',
                'monitor_status': '',
                'name': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'namespace': '',
                'node_ip': '',
                'node_name': '',
                'pod_name': '',
                'resource_usage_cpu': '',
                'resource_usage_disk': '',
                'resource_usage_memory': '',
                'status': '',
                'workload': '',
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
        add_bcs_containers,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_container_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'name',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '容器名称',
                    'overview_name': '概览',
                    'type': 'link',
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
                        {'text': 'bcs-system', 'value': 'bcs-system'},
                        {'text': 'namespace_a', 'value': 'namespace_a'},
                    ],
                    'filterable': True,
                    'id': 'namespace',
                    'min_width': 120,
                    'name': 'NameSpace',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [{'text': 'running', 'value': 'running'}],
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
                    'id': 'pod_name',
                    'min_width': 120,
                    'name': 'Pod名称',
                    'type': 'link',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'workload',
                    'min_width': 120,
                    'name': '工作负载',
                    'type': 'link',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'node_name',
                    'min_width': 120,
                    'name': '节点名称',
                    'type': 'link',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'node_ip',
                    'min_width': 120,
                    'name': '节点IP',
                    'type': 'link',
                },
                {'checked': False, 'disabled': False, 'id': 'image', 'min_width': 120, 'name': '镜像', 'type': 'string'},
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_cpu',
                    'min_width': 120,
                    'name': 'CPU使用量',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_memory',
                    'min_width': 120,
                    'name': '内存使用量',
                    'sortable': False,
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'resource_usage_disk',
                    'min_width': 120,
                    'name': '磁盘使用量',
                    'sortable': False,
                    'type': 'string',
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
                        {'id': 'namespace_a', 'name': 'namespace_a'},
                    ],
                    'id': 'namespace',
                    'multiable': False,
                    'name': 'namespace',
                },
                {
                    'children': [{'id': 'StatefulSet', 'name': 'StatefulSet'}],
                    'id': 'workload_type',
                    'multiable': False,
                    'name': 'workload_type',
                },
                {
                    'children': [
                        {'id': 'api-gateway', 'name': 'api-gateway'},
                        {'id': 'api-gateway-etcd', 'name': 'api-gateway-etcd'},
                    ],
                    'id': 'workload_name',
                    'multiable': False,
                    'name': 'workload_name',
                },
                {
                    'children': [
                        {'id': 'api-gateway-0', 'name': 'api-gateway-0'},
                        {'id': 'api-gateway-etcd-0', 'name': 'api-gateway-etcd-0'},
                    ],
                    'id': 'pod_name',
                    'multiable': False,
                    'name': 'pod_name',
                },
                {
                    'children': [{'id': '2.2.2.2', 'name': '2.2.2.2'}],
                    'id': 'node_ip',
                    'multiable': False,
                    'name': 'node_ip',
                },
                {
                    'children': [{'id': 'running', 'name': 'running'}],
                    'id': 'status',
                    'multiable': False,
                    'name': 'status',
                },
            ],
            'data': DATA,
            'filter': FILTER,
            'overview_data': {
                'age': '',
                'bcs_cluster_id': '',
                'image': '',
                'monitor_status': '',
                'name': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'namespace': '',
                'node_ip': '',
                'node_name': '',
                'pod_name': '',
                'resource_usage_cpu': '',
                'resource_usage_disk': '',
                'resource_usage_memory': '',
                'status': '',
                'workload': '',
            },
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect
