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


class TestGetKubernetesWorkload:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_workloads,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "workload_name": "bcs-cluster-manager",
            "workload_type": "Deployment",
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_workload(params)
        expect = [
            {'key': 'name', 'name': '工作负载名称', 'type': 'string', 'value': 'bcs-cluster-manager'},
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
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'success'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'type', 'name': '类型', 'type': 'string', 'value': 'Deployment'},
            {'key': 'images', 'name': '镜像', 'type': 'string', 'value': 'images'},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'pod_count',
                'name': 'Pod数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00000"},'
                        '{"workload_name":"bcs-cluster-manager"}]}'
                    ),
                    'value': 1,
                },
            },
            {
                'key': 'container_count',
                'name': '容器数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00000"},'
                        '{"workload_name":"bcs-cluster-manager"}]}'
                    ),
                    'value': 0,
                },
            },
            {
                'key': 'resources',
                'name': '资源',
                'type': 'kv',
                'value': [
                    {'key': 'requests memory', 'value': '2GB'},
                    {'key': 'limits cpu', 'value': '2000m'},
                    {'key': 'limits memory', 'value': '2GB'},
                ],
            },
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
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_workloads,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00002",
            "namespace": "namespace_a",
            "workload_name": "bcs-cluster-manager",
            "workload_type": "Deployment",
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_workload(params)
        expect = [
            {'key': 'name', 'name': '工作负载名称', 'type': 'string', 'value': 'bcs-cluster-manager'},
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
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'success'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'type', 'name': '类型', 'type': 'string', 'value': 'Deployment'},
            {'key': 'images', 'name': '镜像', 'type': 'string', 'value': 'images'},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'pod_count',
                'name': 'Pod数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00002"},'
                        '{"workload_name":"bcs-cluster-manager"}]}'
                    ),
                    'value': 1,
                },
            },
            {
                'key': 'container_count',
                'name': '容器数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=container&sceneType=detail'
                        '&queryData={"selectorSearch":['
                        '{"bcs_cluster_id":"BCS-K8S-00002"},'
                        '{"workload_name":"bcs-cluster-manager"}]}'
                    ),
                    'value': 0,
                },
            },
            {
                'key': 'resources',
                'name': '资源',
                'type': 'kv',
                'value': [
                    {'key': 'requests memory', 'value': '2GB'},
                    {'key': 'limits cpu', 'value': '2000m'},
                    {'key': 'limits memory', 'value': '2GB'},
                ],
            },
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect
