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


class TestGetKubernetesCluster:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_bcs_kubernetes_fetch_usage_radio,
    ):
        params = {"bcs_cluster_id": "BCS-K8S-00000", "bk_biz_id": 2}
        actual = resource.scene_view.get_kubernetes_cluster(params)
        expect = [
            {'key': 'bcs_cluster_id', 'name': '集群ID', 'type': 'string', 'value': 'BCS-K8S-00000'},
            {'key': 'name', 'name': '集群名称', 'type': 'string', 'value': '蓝鲸社区版7.0'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'RUNNING'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'environment', 'name': '环境', 'type': 'string', 'value': '正式'},
            {'key': 'node_count', 'name': '节点数量', 'type': 'number', 'value': 1},
            {
                'key': 'cpu_usage_ratio',
                'name': 'CPU使用率',
                'type': 'progress',
                'value': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
            },
            {
                'key': 'memory_usage_ratio',
                'name': '内存使用率',
                'type': 'progress',
                'value': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
            },
            {
                'key': 'disk_usage_ratio',
                'name': '磁盘使用率',
                'type': 'progress',
                'value': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
            },
            {'key': 'area_name', 'name': '区域', 'type': 'string', 'value': ''},
            {
                'key': 'created_at',
                'name': '创建时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {
                'key': 'updated_at',
                'name': '更新时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {'key': 'project_name', 'name': '所属项目', 'type': 'string', 'value': ''},
            {'key': 'description', 'name': '描述', 'type': 'string', 'value': ''},
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_uid(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_bcs_kubernetes_fetch_usage_radio,
    ):
        params = {
            "bk_biz_id": -102,
            "bcs_cluster_id": "BCS-K8S-00000",
        }
        instance = resource.scene_view.get_kubernetes_cluster(params)
        assert instance[0]["value"] == "BCS-K8S-00000"

        params = {
            "bk_biz_id": -102,
            "bcs_cluster_id": "unknown",
        }
        instance = resource.scene_view.get_kubernetes_cluster(params)
        assert instance == []

    @pytest.mark.django_db
    def test_perform_request__include_shared_cluster(
        self,
        monkeypatch_get_shared_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        monkeypatch_had_bkm_metricbeat_endpoint_up,
        monkeypatch_bcs_kubernetes_fetch_usage_radio,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        params = {
            "bk_biz_id": -103,
            "bcs_cluster_id": "BCS-K8S-00002",
        }
        actual = resource.scene_view.get_kubernetes_cluster(params)
        expect = [
            {'key': 'bcs_cluster_id', 'name': '集群ID', 'type': 'string', 'value': 'BCS-K8S-00002'},
            {'key': 'name', 'name': '集群名称', 'type': 'string', 'value': '蓝鲸社区版7.0'},
            {'key': 'status', 'name': '运行状态', 'type': 'string', 'value': 'RUNNING'},
            {'key': 'monitor_status', 'name': '采集状态', 'type': 'status', 'value': {'text': '正常', 'type': 'success'}},
            {'key': 'environment', 'name': '环境', 'type': 'string', 'value': '正式'},
            {'key': 'node_count', 'name': '节点数量', 'type': 'number', 'value': None},
            {
                'key': 'cpu_usage_ratio',
                'name': 'CPU使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {
                'key': 'memory_usage_ratio',
                'name': '内存使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {
                'key': 'disk_usage_ratio',
                'name': '磁盘使用率',
                'type': 'progress',
                'value': {'label': '', 'status': 'NODATA', 'value': 0},
            },
            {'key': 'area_name', 'name': '区域', 'type': 'string', 'value': ''},
            {
                'key': 'created_at',
                'name': '创建时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {
                'key': 'updated_at',
                'name': '更新时间',
                'type': 'string',
                'value': translate_timestamp_since('2022-01-01T00:00:00Z'),
            },
            {'key': 'project_name', 'name': '所属项目', 'type': 'string', 'value': ''},
            {'key': 'description', 'name': '描述', 'type': 'string', 'value': ''},
        ]
        assert actual == expect
