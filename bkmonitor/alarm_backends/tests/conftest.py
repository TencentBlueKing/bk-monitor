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

import fakeredis
import mock
import pytest
from django.conf import settings
from django.test import TestCase

from api.bcs_cluster_manager.default import FetchClustersResource
from bkmonitor.utils.elasticsearch.fake_elasticsearch import FakeElasticsearchBucket

pytestmark = pytest.mark.django_db


def pytest_configure():
    mock.patch(
        "alarm_backends.core.storage.redis.redis.Redis", return_value=fakeredis.FakeRedis(decode_responses=True)
    ).start()
    mock.patch(
        "elasticsearch_dsl.connections.Connections.create_connection", return_value=FakeElasticsearchBucket()
    ).start()
    settings.PUSH_MONITOR_EVENT_TO_FTA = False
    TestCase.databases = {"default", "monitor_api"}


MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS = [
    {
        "clusterID": "BCS-K8S-00000",
        "clusterName": "蓝鲸社区版7.0",
        "projectID": "0000000000",
        "businessID": "2",
        "environment": "prod",
        "createTime": "2022-05-15T21:43:32+08:00",
        "updateTime": "2022-05-15T21:43:32+08:00",
        "status": "RUNNING",
    }
]


@pytest.fixture
def monkeypatch_cluster_management_fetch_clusters(monkeypatch):
    """返回集群列表 ."""
    monkeypatch.setattr(
        FetchClustersResource, "perform_request", lambda self, params: MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS
    )
