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

from api.bcs_storage.default import FetchResource
from core.drf_resource import resource


class TestGetKubernetesObjectCount:
    @pytest.mark.django_db
    def test_perform_request(
        self,
        monkeypatch,
        add_bcs_cluster_item_for_insert_and_delete,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_namespace,
    ):
        monkeypatch.setattr(FetchResource, "cache_type", None)
        actual = resource.scene_view.get_kubernetes_object_count({"bk_biz_id": 2})
        expect = [
            {'label': '集群', 'value': 0},
            {'label': 'Namespace', 'value': 2},
            {
                'label': '节点(Node)',
                'link': {
                    'target': 'blank',
                    'url': '?bizId=2#/k8s?dashboardId=node&sceneId=kubernetes&sceneType=overview',
                },
                'value': 0,
            },
            {
                'label': 'Pod',
                'link': {
                    'target': 'blank',
                    'url': '?bizId=2#/k8s?dashboardId=pod&sceneId=kubernetes&sceneType=overview',
                },
                'value': 0,
            },
        ]
        assert actual == expect

        actual = resource.scene_view.get_kubernetes_object_count({"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"})
        expect = [
            {'label': '集群', 'value': 0},
            {'label': 'Namespace', 'value': 2},
            {
                'label': '节点(Node)',
                'link': {
                    'target': 'blank',
                    'url': '?bizId=2#/k8s?dashboardId=node&sceneId=kubernetes&sceneType=overview',
                },
                'value': 0,
            },
            {
                'label': 'Pod',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=2#/k8s?dashboardId=pod&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                },
                'value': 0,
            },
        ]
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_by_space_id(
        self,
        monkeypatch,
        monkeypatch_bcs_storage_fetch_namespace,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
    ):
        monkeypatch.setattr(FetchResource, "cache_type", None)
        resources = ["master_node", "work_node", "pod", "container"]
        actual = resource.scene_view.get_kubernetes_object_count(
            {"bk_biz_id": -3, "resources": resources, "bcs_cluster_id": "BCS-K8S-00002"}
        )
        expect = [
            {
                'label': 'Pod',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=pod&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"}]}'
                    ),
                },
                'value': 0,
            },
            {
                'label': '容器',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=container&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00002"}]}'
                    ),
                },
                'value': 0,
            },
        ]
        assert actual == expect

        actual = resource.scene_view.get_kubernetes_object_count(
            {"bk_biz_id": -3, "resources": resources, "bcs_cluster_id": "BCS-K8S-00000"}
        )
        expect = [
            {
                'label': 'Master节点',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=node&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"roles":"control-plane"}]}'
                    ),
                },
                'value': 0,
            },
            {
                'label': 'Worker节点',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=node&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"},{"roles":""}]}'
                    ),
                },
                'value': 0,
            },
            {
                'label': 'Pod',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=pod&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                },
                'value': 0,
            },
            {
                'label': '容器',
                'link': {
                    'target': 'blank',
                    'url': (
                        '?bizId=-3#/k8s?dashboardId=container&sceneId=kubernetes&sceneType=overview'
                        '&queryData={"selectorSearch":[{"bcs_cluster_id":"BCS-K8S-00000"}]}'
                    ),
                },
                'value': 0,
            },
        ]
        assert actual == expect
