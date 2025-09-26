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

from django.conf import settings

from api.bcs_storage.default import FetchResource
from core.drf_resource import api


class TestFetchResource:
    def test_get_namespace(self, monkeypatch, monkeypatch_bcs_storage_fetch_namespace):
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        actual = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Namespace"})
        expect = [
            {
                'metadata': {'creationTimestamp': '2022-01-01T00:00:00Z', 'name': 'bcs-system'},
                'spec': {'finalizers': ['kubernetes']},
                'status': {'phase': 'Active'},
            },
            {
                'metadata': {'creationTimestamp': '2022-01-01T00:00:00Z', 'name': 'bcs-system-2'},
                'spec': {'finalizers': ['kubernetes']},
                'status': {'phase': 'Active'},
            },
        ]
        assert actual == expect

    def test_with_page(self, monkeypatch, monkeypatch_bcs_storage_base):
        monkeypatch.setattr(FetchResource, "cache_type", None)
        bcs_cluster_id = "BCS-K8S-00000"

        monkeypatch.setattr(settings, "BCS_STORAGE_PAGE_SIZE", 1)
        actual = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Namespace"})
        expect = [{'id': 1, 'username': 'username_a'}, {'id': 2, 'username': 'username_b'}]
        assert actual == expect

        monkeypatch.setattr(settings, "BCS_STORAGE_PAGE_SIZE", 2)
        actual = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Namespace"})
        expect = [
            {'id': 1, 'username': 'username_a'},
            {'id': 2, 'username': 'username_b'},
            {'id': 6, 'username': 'username_f'},
        ]
        assert actual == expect

        monkeypatch.setattr(settings, "BCS_STORAGE_PAGE_SIZE", 3)
        actual = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Namespace", "offset": 0, "limit": 3})
        expect = [{'id': 1, 'username': 'username_a'}, {'id': 2, 'username': 'username_b'}]
        assert actual == expect
