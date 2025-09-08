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


class TestGetKubernetesServiceMonitor:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_service_monitors,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "namespace-operator",
            "name": "namespace-operator-stack-api-server",
            "bk_biz_id": 2,
            "metric_path": "/metrics",
            "metric_port": "https",
        }
        actual = resource.scene_view.get_kubernetes_service_monitor(params)
        expect = [
            {'key': 'name', 'name': '名称', 'type': 'string', 'value': 'namespace-operator-stack-api-server'},
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
            {'key': 'namespace', 'name': 'NameSpace', 'type': 'string', 'value': 'namespace-operator'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'metric_path', 'name': 'Metric路径', 'type': 'string', 'value': '/metrics'},
            {'key': 'metric_port', 'name': '端口', 'type': 'string', 'value': 'https'},
            {'key': 'metric_interval', 'name': '周期(s)', 'type': 'string', 'value': '30s'},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
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
        add_service_monitors,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00002",
            "namespace": "namespace_a",
            "name": "namespace-operator-stack-api-server",
            "bk_biz_id": -3,
            "metric_path": "/metrics",
            "metric_port": "http",
        }
        actual = resource.scene_view.get_kubernetes_service_monitor(params)
        expect = [
            {'key': 'name', 'name': '名称', 'type': 'string', 'value': 'namespace-operator-stack-api-server'},
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
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'metric_path', 'name': 'Metric路径', 'type': 'string', 'value': '/metrics'},
            {'key': 'metric_port', 'name': '端口', 'type': 'string', 'value': 'http'},
            {'key': 'metric_interval', 'name': '周期(s)', 'type': 'string', 'value': '60s'},
            {'key': 'label_list', 'name': '标签', 'type': 'kv', 'value': []},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
        ]
        assert actual == expect
