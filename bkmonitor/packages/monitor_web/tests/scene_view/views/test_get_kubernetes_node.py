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
class TestGetKubernetesNode:
    def test_perform_request(
        self,
        monkeypatch_request_performance_data,
        add_bcs_nodes,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {"bcs_cluster_id": "BCS-K8S-00000", "node_ip": "1.1.1.1", "bk_biz_id": 2}
        actual = resource.scene_view.get_kubernetes_node(params)
        expect = [
            {'key': 'name', 'name': '节点名称', 'type': 'string', 'value': 'master-1-1-1-1'},
            {
                'key': 'pod_count',
                'name': 'Pod数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"node_ip":"1.1.1.1"}]}'
                    ),
                    'value': 16,
                },
            },
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
            {'key': 'bk_cluster_name', 'name': '集群名称', 'type': 'string', 'value': ''},
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {'target': 'blank', 'url': '?bizId=2#/performance/detail/1.1.1.1-0', 'value': '1.1.1.1'},
            },
            {'key': 'cloud_id', 'name': '云区域', 'type': 'string', 'value': ''},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'Ready'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '异常', 'type': 'failed'}},
            {
                'key': 'system_cpu_summary_usage',
                'name': 'CPU使用率',
                'type': 'progress',
                'value': {'label': '9.08%', 'status': 'SUCCESS', 'value': 9.08},
            },
            {
                'key': 'system_mem_pct_used',
                'name': '应用内存使用率',
                'type': 'progress',
                'value': {'label': '52.5%', 'status': 'SUCCESS', 'value': 52.5},
            },
            {
                'key': 'system_io_util',
                'name': '磁盘IO使用率',
                'type': 'progress',
                'value': {'label': '4.12%', 'status': 'SUCCESS', 'value': 4.12},
            },
            {
                'key': 'system_disk_in_use',
                'name': '磁盘空间使用率',
                'type': 'progress',
                'value': {'label': '15.57%', 'status': 'SUCCESS', 'value': 15.57},
            },
            {'key': 'system_load_load15', 'name': 'CPU十五分钟负载', 'type': 'str', 'value': 1.38},
            {'key': 'taints', 'name': '污点', 'type': 'list', 'value': []},
            {'key': 'node_roles', 'name': '角色', 'type': 'list', 'value': ['control-plane', 'master']},
            {'key': 'endpoint_count', 'name': 'Endpoint数量', 'type': 'number', 'value': 19},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]

        assert actual == expect

    def test_perform_request__ci_space(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_request_performance_data,
        add_bcs_nodes,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {"bcs_cluster_id": "BCS-K8S-00002", "node_ip": "2.2.2.2", "bk_biz_id": -3}
        actual = resource.scene_view.get_kubernetes_node(params)
        expect = [
            {'key': 'name', 'name': '节点名称', 'type': 'string', 'value': 'node-2-2-2-2'},
            {
                'key': 'pod_count',
                'name': 'Pod数量',
                'type': 'link',
                'value': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=pod&sceneType=detail'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"},{"node_ip":"2.2.2.2"}]}'
                    ),
                    'value': 16,
                },
            },
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
            {
                'key': 'node_ip',
                'name': '节点IP',
                'type': 'link',
                'value': {'target': 'blank', 'url': '?bizId=100#/performance/detail/2.2.2.2-0', 'value': '2.2.2.2'},
            },
            {'key': 'cloud_id', 'name': '云区域', 'type': 'string', 'value': ''},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'Ready'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '异常', 'type': 'failed'}},
            {
                'key': 'system_cpu_summary_usage',
                'name': 'CPU使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {
                'key': 'system_mem_pct_used',
                'name': '应用内存使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {
                'key': 'system_io_util',
                'name': '磁盘IO使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {
                'key': 'system_disk_in_use',
                'name': '磁盘空间使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {'key': 'system_load_load15', 'name': 'CPU十五分钟负载', 'type': 'str', 'value': ''},
            {'key': 'taints', 'name': '污点', 'type': 'list', 'value': []},
            {'key': 'node_roles', 'name': '角色', 'type': 'list', 'value': []},
            {'key': 'endpoint_count', 'name': 'Endpoint数量', 'type': 'number', 'value': 19},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect
