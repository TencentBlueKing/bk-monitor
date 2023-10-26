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
import os

import pytest
from django.conf import settings
from django.core.management import call_command
from mockredis import mock_redis_client

from metadata import models

pytestmark = pytest.mark.django_db

DEFAULT_CLUSTER_ID = 10000
DEFAULT_NAME = "test_influxdb_cluster"


@pytest.fixture
def create_and_delete_record():
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_CLUSTER_ID,
        cluster_name=DEFAULT_NAME,
        cluster_type="influxdb",
        domain_name="test_domain",
        port=10203,
        description="test",
        schema="http",
        is_default_cluster=False,
    )
    models.InfluxDBClusterInfo.objects.create(
        host_name=DEFAULT_NAME,
        cluster_name=DEFAULT_NAME,
    )
    models.InfluxDBProxyStorage.objects.create(proxy_cluster_id=DEFAULT_CLUSTER_ID, instance_cluster_name=DEFAULT_NAME)
    yield
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_CLUSTER_ID).delete()
    models.InfluxDBClusterInfo.objects.filter(cluster_name=DEFAULT_NAME).delete()
    models.InfluxDBProxyStorage.objects.filter(proxy_cluster_id=DEFAULT_CLUSTER_ID).delete()
    models.InfluxDBStorage.objects.filter(storage_cluster_id=DEFAULT_CLUSTER_ID).delete()


def test_error_params():
    # 三个参数都不存在
    with pytest.raises(Exception):
        call_command("init_metrics_and_refresh_router")

    # 任意参数不存在
    with pytest.raises(Exception):
        call_command("init_metrics_and_refresh_router", "--metric_content_path", "test")


def test_not_found_record(create_and_delete_record):
    path = os.path.join(settings.BASE_DIR, "metadata/tests/data/test_bkdata_metrics.txt")
    options = {"metric_content_path": path, "influxdb_proxy_cluster_id": 100001, "influxdb_cluster_names": "notfound"}
    with pytest.raises(Exception):
        call_command("init_metrics_and_refresh_router", **options)


def test_metric_data_error(create_and_delete_record):
    path = os.path.join(settings.BASE_DIR, "metadata/tests/data/test_bkdata_metrics.txt1")
    options = {
        "metric_content_path": path,
        "influxdb_proxy_cluster_id": DEFAULT_CLUSTER_ID,
        "influxdb_cluster_names": DEFAULT_NAME,
    }
    with pytest.raises(FileNotFoundError):
        call_command("init_metrics_and_refresh_router", **options)


def test_create_success(mocker, create_and_delete_record):
    path = os.path.join(settings.BASE_DIR, "metadata/tests/data/test_bkdata_metrics.txt")
    options = {
        "metric_content_path": path,
        "influxdb_proxy_cluster_id": DEFAULT_CLUSTER_ID,
        "influxdb_cluster_names": DEFAULT_NAME,
    }
    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    mocker.patch("metadata.task.config_refresh.refresh_influxdb_route", return_value=True)
    call_command("init_metrics_and_refresh_router", **options)
    # NOTE: 过滤条件中的`metric1`来自于上述`path`中内容
    data = models.InfluxDBStorage.objects.filter(real_table_name__in=["metric1", "metric2"])
    assert len(data) == 2


def consul_client(*args, **kwargs):
    return CustomConsul()


class CustomConsul:
    def __init__(self):
        self.kv = KVPut()


class KVPut:
    def put(self, *args, **kwargs):
        return True

    def delete(self, *args, **kwargs):
        return True
