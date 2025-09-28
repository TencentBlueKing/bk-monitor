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

from core.drf_resource import resource


class TestGetKubernetesWorkloadStatus:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_deployments,
    ):
        params = {"type": "Deployment", "bk_biz_id": 2}
        actual = resource.scene_view.get_kubernetes_workload_status(params)
        expect = {
            'data': [
                {
                    'borderColor': '#2dcb56',
                    'color': '#2dcb56',
                    'link': {
                        'target': 'blank',
                        'url': (
                            '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=overview'
                            '&queryData={"selectorSearch":[{"workload_type":"Deployment"},{"status":"success"}]}'
                        ),
                    },
                    'name': '健康',
                    'value': 1,
                },
                {
                    'borderColor': '#ea3636',
                    'color': '#ea3636',
                    'link': {
                        'target': 'blank',
                        'url': (
                            '?bizId=2#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=overview'
                            '&queryData={"selectorSearch":[{"workload_type":"Deployment"},{"status":"failed"}]}'
                        ),
                    },
                    'name': '异常',
                    'value': 1,
                },
            ],
            'name': 'Deployment',
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_deployments,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
    ):
        params = {"type": "Deployment", "bk_biz_id": -3}
        actual = resource.scene_view.get_kubernetes_workload_status(params)
        expect = {
            'data': [
                {
                    'borderColor': '#2dcb56',
                    'color': '#2dcb56',
                    'link': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=overview'
                            '&queryData={"selectorSearch":[{"workload_type":"Deployment"},{"status":"success"}]}'
                        ),
                    },
                    'name': '健康',
                    'value': 1,
                },
                {
                    'borderColor': '#ea3636',
                    'color': '#ea3636',
                    'link': {
                        'target': 'blank',
                        'url': (
                            '?bizId=-3#/k8s?sceneId=kubernetes&dashboardId=workload&sceneType=overview'
                            '&queryData={"selectorSearch":[{"workload_type":"Deployment"},{"status":"failed"}]}'
                        ),
                    },
                    'name': '异常',
                    'value': 1,
                },
            ],
            'name': 'Deployment',
        }
        assert actual == expect
