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


class TestGetKubernetesService:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        monkeypatch,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_service,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bcs-system",
            "service_name": "api-gateway",
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_service(params)
        expect = [
            {'key': 'name', 'name': '服务名称', 'type': 'string', 'value': 'api-gateway'},
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
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'type', 'name': '类型', 'type': 'string', 'value': 'NodePort'},
            {'key': 'cluster_ip', 'name': 'Cluster IP', 'type': 'string', 'value': '1.1.1.1'},
            {'key': 'external_ip', 'name': 'External IP', 'type': 'string', 'value': '<none>'},
            {
                'key': 'ports',
                'name': 'Ports',
                'type': 'list',
                'value': ['9013:31001/TCP', '9010:31000/TCP', '9014:31003/TCP', '9009:31002/TCP'],
            },
            {'key': 'endpoint_count', 'name': 'Endpoint数量', 'type': 'number', 'value': 4},
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
                        '{"namespace":"bcs-system"},'
                        '{"service_name":"api-gateway"}]}'
                    ),
                    'value': 1,
                },
            },
            {'key': 'pod_name_list', 'name': 'Pod名称', 'type': 'list', 'value': ['api-gateway-0']},
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since("2022-01-01T00:00:00Z"),
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_service,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_fetch_k8s_bkm_metricbeat_endpoint_up,
    ):
        params = {
            "bcs_cluster_id": "BCS-K8S-00002",
            "namespace": "namespace_a",
            "service_name": "elasticsearch-data",
            "bk_biz_id": -3,
        }
        actual = resource.scene_view.get_kubernetes_service(params)
        expect = [
            {'key': 'name', 'name': '服务名称', 'type': 'string', 'value': 'elasticsearch-data'},
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
            {'key': 'type', 'name': '类型', 'type': 'string', 'value': 'ClusterIP'},
            {'key': 'cluster_ip', 'name': 'Cluster IP', 'type': 'string', 'value': '3.3.3.3'},
            {'key': 'external_ip', 'name': 'External IP', 'type': 'string', 'value': '<none>'},
            {'key': 'ports', 'name': 'Ports', 'type': 'list', 'value': ['9200/TCP', '9300/TCP']},
            {'key': 'endpoint_count', 'name': 'Endpoint数量', 'type': 'number', 'value': 6},
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
                        '{"namespace":"namespace_a"},'
                        '{"service_name":"elasticsearch-data"}]}'
                    ),
                    'value': 3,
                },
            },
            {
                'key': 'pod_name_list',
                'name': 'Pod名称',
                'type': 'list',
                'value': ['elasticsearch-data-2', 'elasticsearch-data-1', 'elasticsearch-data-0'],
            },
            {
                'key': 'age',
                'name': '存活时间',
                'type': 'string',
                'value': translate_timestamp_since("2022-01-01T00:00:00Z"),
            },
        ]
        assert actual == expect
