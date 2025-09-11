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


@pytest.mark.django_db(databases=["default", "monitor_api"])
class TestGetKubernetesPod:
    def test_perform_request(self, add_bcs_cluster_item_for_update_and_delete, add_bcs_pods):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "pod_name": "api-gateway-0",
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_pod(params)
        expect = [
            {'key': 'name', 'name': 'Pod名称', 'type': 'string', 'value': 'api-gateway-0'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'Running'},
            {'key': 'ready', 'name': '是否就绪(实例运行数/期望数)', 'type': 'string', 'value': '2/2'},
            {
                'key': 'bcs_cluster_id',
                'name': '集群ID',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                    'value': 'BCS-K8S-00000',
                },
            },
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': '蓝鲸社区版7.0'},
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'bcs-system'},
            {
                'key': 'total_container_count',
                'name': '容器数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00000"},'
                        '{"pod_name":"api-gateway-0"}]}'
                    ),
                    'value': 2,
                },
            },
            {'key': 'restarts', 'name': '重启次数', 'type': 'number', 'value': 0},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {
                'key': 'request_cpu_usage_ratio',
                'name': 'CPU使用率(request)',
                'type': 'progress',
                'value': {'label': '1.0%', 'status': 'SUCCESS', 'value': 1.0},
            },
            {
                'key': 'limit_cpu_usage_ratio',
                'name': 'CPU使用率(limit)',
                'type': 'progress',
                'value': {'label': '2.0%', 'status': 'SUCCESS', 'value': 2.0},
            },
            {
                'key': 'request_memory_usage_ratio',
                'name': '内存使用率(request)',
                'type': 'progress',
                'value': {'label': '3.0%', 'status': 'SUCCESS', 'value': 3.0},
            },
            {
                'key': 'limit_memory_usage_ratio',
                'name': '内存使用率(limit) ',
                'type': 'progress',
                'value': {'label': '4.0%', 'status': 'SUCCESS', 'value': 4.0},
            },
            {'key': 'resource_usage_cpu', 'name': 'CPU使用量', 'type': 'string', 'value': '20m'},
            {'key': 'resource_usage_memory', 'name': '内存使用量', 'type': 'string', 'value': '788MB'},
            {'key': 'resource_usage_disk', 'name': '磁盘使用量', 'type': 'string', 'value': '315MB'},
            {'key': 'resource_requests_cpu', 'name': 'cpu request', 'type': 'string', 'value': '0'},
            {'key': 'resource_limits_cpu', 'name': 'cpu limit', 'type': 'string', 'value': '10000m'},
            {'key': 'resource_requests_memory', 'name': 'memory request', 'type': 'string', 'value': '1GB'},
            {'key': 'resource_limits_memory', 'name': 'memory limit', 'type': 'string', 'value': '9GB'},
            {'key': 'pod_ip', 'name': 'Pod IP', 'type': 'string', 'value': '1.1.1.1'},
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"ip":"2.2.2.2"}]}'
                    ),
                    'value': '2.2.2.2',
                },
            },
            {
                'key': 'node_name',
                'name': '节点名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00000"},'
                        '{"name":"node-2-2-2-2"}]}'
                    ),
                    'value': 'node-2-2-2-2',
                },
            },
            {'key': 'workload', 'name': '工作负载', 'type': 'string', 'value': 'StatefulSet:api-gateway'},
            {
                'key': 'label_list',
                'name': '标签',
                'type': 'kv',
                'value': [{'key': 'key_1', 'value': 'value_1'}, {'key': 'key_2', 'value': 'value_2'}],
            },
            {
                'key': 'images',
                'name': '镜像',
                'type': 'list',
                'value': ['host/namespace/apisix:latest', 'host/namespace/gateway-discovery:latest'],
            },
        ]
        assert actual == expect

    def test_perform_request_by_space_id(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_pods,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00002",
            "namespace": "namespace_a",
            "pod_name": "api-gateway-2",
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_pod(params)
        expect = [
            {'key': 'name', 'name': 'Pod名称', 'type': 'string', 'value': 'api-gateway-2'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'Completed'},
            {'key': 'ready', 'name': '是否就绪(实例运行数/期望数)', 'type': 'string', 'value': '2/2'},
            {
                'key': 'bcs_cluster_id',
                'name': '集群ID',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"}]}'
                    ),
                    'value': 'BCS-K8S-00002',
                },
            },
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': '蓝鲸社区版7.0'},
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'namespace_a'},
            {
                'key': 'total_container_count',
                'name': '容器数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00002"},'
                        '{"pod_name":"api-gateway-2"}]}'
                    ),
                    'value': 2,
                },
            },
            {'key': 'restarts', 'name': '重启次数', 'type': 'number', 'value': 10},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '异常', 'type': 'failed'}},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {
                'key': 'request_cpu_usage_ratio',
                'name': 'CPU使用率(request)',
                'type': 'progress',
                'value': {'label': '1.0%', 'status': 'SUCCESS', 'value': 1.0},
            },
            {
                'key': 'limit_cpu_usage_ratio',
                'name': 'CPU使用率(limit)',
                'type': 'progress',
                'value': {'label': '2.0%', 'status': 'SUCCESS', 'value': 2.0},
            },
            {
                'key': 'request_memory_usage_ratio',
                'name': '内存使用率(request)',
                'type': 'progress',
                'value': {'label': '3.0%', 'status': 'SUCCESS', 'value': 3.0},
            },
            {
                'key': 'limit_memory_usage_ratio',
                'name': '内存使用率(limit) ',
                'type': 'progress',
                'value': {'label': '4.0%', 'status': 'SUCCESS', 'value': 4.0},
            },
            {'key': 'resource_usage_cpu', 'name': 'CPU使用量', 'type': 'string', 'value': '30m'},
            {'key': 'resource_usage_memory', 'name': '内存使用量', 'type': 'string', 'value': '788MB'},
            {'key': 'resource_usage_disk', 'name': '磁盘使用量', 'type': 'string', 'value': '315MB'},
            {'key': 'resource_requests_cpu', 'name': 'cpu request', 'type': 'string', 'value': '0'},
            {'key': 'resource_limits_cpu', 'name': 'cpu limit', 'type': 'string', 'value': '10000m'},
            {'key': 'resource_requests_memory', 'name': 'memory request', 'type': 'string', 'value': '1GB'},
            {'key': 'resource_limits_memory', 'name': 'memory limit', 'type': 'string', 'value': '9GB'},
            {'key': 'pod_ip', 'name': 'Pod IP', 'type': 'string', 'value': '2.2.2.2'},
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"ip":"1.1.1.1"}]}'
                    ),
                    'value': '1.1.1.1',
                },
            },
            {
                'key': 'node_name',
                'name': '节点名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"node-1.1.1.1"}]}'
                    ),
                    'value': 'node-1.1.1.1',
                },
            },
            {'key': 'workload', 'name': '工作负载', 'type': 'string', 'value': 'StatefulSet:api-gateway'},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'images',
                'name': '镜像',
                'type': 'list',
                'value': ['host/namespace/apisix:latest', 'host/namespace/gateway-discovery:latest'],
            },
        ]
        assert actual == expect
