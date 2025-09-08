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


class TestGetKubernetesContainer:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_containers,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "pod_name": "api-gateway-0",
            "container_name": "apisix",
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_container(params)
        expect = [
            {'key': 'name', 'name': '容器名称', 'type': 'string', 'value': 'apisix'},
            {
                'key': 'bcs_cluster_id',
                'name': '集群ID',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                    'value': 'BCS-K8S-00000',
                },
            },
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': ''},
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'bcs-system'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'running'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {
                'key': 'pod_name',
                'name': 'Pod名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"name":"api-gateway-0"}]}'
                    ),
                    'value': 'api-gateway-0',
                },
            },
            {
                'key': 'workload',
                'name': '工作负载',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=detail&'
                    'queryData={"selectorSearch":['
                    '{"bcs_cluster_id":"BCS-K8S-00000"},'
                    '{"workload_type":"StatefulSet"},'
                    '{"name":"api-gateway"}]}',
                    'value': 'StatefulSet:api-gateway',
                },
            },
            {
                'key': 'node_name',
                'name': '节点名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                    'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"name":"node-2-2-2-2"}]}',
                    'value': 'node-2-2-2-2',
                },
            },
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"ip":"2.2.2.2"}]}'
                    ),
                    'value': '2.2.2.2',
                },
            },
            {'key': 'image', 'name': '镜像', 'type': 'string', 'value': 'host/namespace/apisix:latest'},
            {'key': 'resource_usage_cpu', 'name': 'CPU使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_memory', 'name': '内存使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_disk', 'name': '磁盘使用量', 'type': 'string', 'value': ''},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_not_found(
        self,
        add_workloads,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "pod_name": "bcs-api-gateway-0",
            "container_name": "unknown",
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_container(params)
        expect = []
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_from_bcs_space(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_containers,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "pod_name": "api-gateway-0",
            "container_name": "apisix",
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_container(params)
        expect = [
            {'key': 'name', 'name': '容器名称', 'type': 'string', 'value': 'apisix'},
            {
                'key': 'bcs_cluster_id',
                'name': '集群ID',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=cluster&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                    'value': 'BCS-K8S-00000',
                },
            },
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': ''},
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'bcs-system'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'running'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {
                'key': 'pod_name',
                'name': 'Pod名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"name":"api-gateway-0"}]}'
                    ),
                    'value': 'api-gateway-0',
                },
            },
            {
                'key': 'workload',
                'name': '工作负载',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=detail&'
                        'queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00000"},'
                        '{"workload_type":"StatefulSet"},'
                        '{"name":"api-gateway"}]}'
                    ),
                    'value': 'StatefulSet:api-gateway',
                },
            },
            {
                'key': 'node_name',
                'name': '节点名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"name":"node-2-2-2-2"}]}'
                    ),
                    'value': 'node-2-2-2-2',
                },
            },
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"ip":"2.2.2.2"}]}'
                    ),
                    'value': '2.2.2.2',
                },
            },
            {'key': 'image', 'name': '镜像', 'type': 'string', 'value': 'host/namespace/apisix:latest'},
            {'key': 'resource_usage_cpu', 'name': 'CPU使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_memory', 'name': '内存使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_disk', 'name': '磁盘使用量', 'type': 'string', 'value': ''},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_containers,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00002",
            "namespace": "namespace_a",
            "pod_name": "api-gateway-etcd-0",
            "container_name": "etcd",
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_container(params)
        expect = [
            {'key': 'name', 'name': '容器名称', 'type': 'string', 'value': 'etcd'},
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
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': ''},
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'namespace_a'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'running'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '无数据', 'type': 'disabled'}},
            {
                'key': 'pod_name',
                'name': 'Pod名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail&'
                    'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"api-gateway-etcd-0"}]}',
                    'value': 'api-gateway-etcd-0',
                },
            },
            {
                'key': 'workload',
                'name': '工作负载',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=detail&'
                        'queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00002"},'
                        '{"workload_type":"StatefulSet"},'
                        '{"name":"api-gateway-etcd"}]}'
                    ),
                    'value': 'StatefulSet:api-gateway-etcd',
                },
            },
            {
                'key': 'node_name',
                'name': '节点名称',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                        'queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00002"},{"name":"node-2-2-2-2"}]}'
                    ),
                    'value': 'node-2-2-2-2',
                },
            },
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=node&sceneType=detail&'
                        'queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"ip":"2.2.2.2"}]}'
                    ),
                    'value': '2.2.2.2',
                },
            },
            {'key': 'image', 'name': '镜像', 'type': 'string', 'value': 'docker.io/host/etcd:latest'},
            {'key': 'resource_usage_cpu', 'name': 'CPU使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_memory', 'name': '内存使用量', 'type': 'string', 'value': ''},
            {'key': 'resource_usage_disk', 'name': '磁盘使用量', 'type': 'string', 'value': ''},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect
