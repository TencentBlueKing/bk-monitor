# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import pytest
from django.conf import settings

from alarm_backends.core.cache.bcs_cluster import BcsClusterCacheManager
from api.kubernetes.default import FetchK8sClusterListResource

pytestmark = pytest.mark.django_db


class TestBcsClusterCacheManager:
    def test_get(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"

        BcsClusterCacheManager.refresh()
        actual = BcsClusterCacheManager.get(bcs_cluster_id)
        expect = {'name': '蓝鲸社区版7.0'}
        assert actual == expect
