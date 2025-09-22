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
import time

import pytest
from django.conf import settings

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import FetchK8sClusterListResource
from core.drf_resource import api

pytestmark = pytest.mark.django_db


class TestFetchUsageRatio:
    def test_fetch(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_node_and_endpoints,
        monkeypatch_bcs_kubernetes_fetch_usage_radio,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bk_biz_id = 2
        bcs_cluster_id = "BCS-K8S-00000"
        end_time = int(time.time() - 60)
        start_time = int(time.time() - 120)
        usage_types = ["cpu", "memory", "disk"]
        bulk_params = {
            "bk_biz_id": bk_biz_id,
            "usage_type": usage_types,
            "bcs_cluster_id": bcs_cluster_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        actual = api.kubernetes.fetch_usage_ratio(bulk_params)
        expect = {'cpu': 2.460417, 'disk': 7.817225, 'memory': 27.739831}

        assert actual == expect
