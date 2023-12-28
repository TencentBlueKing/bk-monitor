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
from django.core.management import call_command
from mockredis import mock_redis_client

from metadata import models

from .conftest import consul_client

pytestmark = pytest.mark.django_db


PROXY_STORAGE_CLUSTER_ID = 100001


@pytest.fixture
def create_and_delete_records(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.InfluxDBStorage.objects.filter(
        table_id__in=["test.rt", "test.rt1", "test.rt2", "test.rt3", "test.rt4"]
    ).delete()
    models.ClusterInfo.objects.filter(cluster_id__in=[101, 102, 103, 104]).delete()
    models.InfluxDBProxyStorage.objects.all().delete()

    models.InfluxDBProxyStorage.objects.create(
        id=PROXY_STORAGE_CLUSTER_ID, proxy_cluster_id=104, service_name="bkmonitorv3", instance_cluster_name="cluster3"
    )
    router_list = [
        models.InfluxDBStorage(
            table_id="test.rt",
            storage_cluster_id=101,
            real_table_name="rt",
            database="test",
            proxy_cluster_name="cluster1",
        ),
        models.InfluxDBStorage(
            table_id="test.rt1",
            storage_cluster_id=102,
            real_table_name="rt1",
            database="test",
            proxy_cluster_name="cluster2",
        ),
        models.InfluxDBStorage(
            table_id="test.rt2",
            storage_cluster_id=102,
            real_table_name="rt2",
            database="test",
            proxy_cluster_name="cluster2",
        ),
        models.InfluxDBStorage(
            table_id="test.rt3",
            storage_cluster_id=104,
            real_table_name="rt3",
            database="test",
            proxy_cluster_name="cluster3",
        ),
        models.InfluxDBStorage(
            table_id="test.rt4",
            storage_cluster_id=104,
            real_table_name="rt4",
            database="test",
            proxy_cluster_name="cluster3",
            influxdb_proxy_storage_id=PROXY_STORAGE_CLUSTER_ID,
        ),
    ]
    models.InfluxDBStorage.objects.bulk_create(router_list)

    cluster_list = [
        models.ClusterInfo(
            cluster_id=101,
            cluster_name="influxdb_test",
            cluster_type="influxdb",
            domain_name="influxdb-proxy.bkmonitorv3.service.consul",
            port="8080",
            description="test",
            is_default_cluster=False,
        ),
        models.ClusterInfo(
            cluster_id=102,
            cluster_name="influxdb_test1",
            cluster_type="influxdb",
            domain_name="influxdb-proxy.test-bkmonitorv3.service.consul",
            port="8080",
            description="test",
            is_default_cluster=False,
        ),
        models.ClusterInfo(
            cluster_id=103,
            cluster_name="influxdb_test2",
            cluster_type="influxdb",
            domain_name="influxdb-proxy.test2-bkmonitorv3.service.consul",
            port="8080",
            description="test",
            is_default_cluster=False,
        ),
        models.ClusterInfo(
            cluster_id=104,
            cluster_name="influxdb_test3",
            cluster_type="influxdb",
            domain_name="influxdb-proxy-test",
            port="8080",
            description="test",
            is_default_cluster=False,
        ),
    ]
    models.ClusterInfo.objects.bulk_create(cluster_list)
    yield
    models.InfluxDBStorage.objects.filter(
        table_id__in=["test.rt", "test.rt1", "test.rt2", "test.rt3", "test.rt4"]
    ).delete()
    models.ClusterInfo.objects.filter(cluster_id__in=[101, 102, 103, 104]).delete()
    models.InfluxDBProxyStorage.objects.all().delete()


def test_init_influxdb_proxy_storage(create_and_delete_records, mocker):
    mocker.patch("metadata.utils.redis_tools.setup_client", side_effect=mock_redis_client)
    # 执行命令
    call_command("init_influxdb_proxy_storage")

    # 数量匹配
    assert models.InfluxDBProxyStorage.objects.filter(proxy_cluster_id__in=[101, 102, 103, 104]).count() == 3
    assert (
        len(
            models.InfluxDBProxyStorage.objects.filter(
                proxy_cluster_id__in=[101, 102, 103, 104], service_name="bkmonitorv3"
            )
        )
        == 2
    )

    # 匹配值
    assert set(
        list(
            models.InfluxDBProxyStorage.objects.filter(proxy_cluster_id__in=[101, 102, 103, 104]).values_list(
                "service_name", flat=True
            )
        )
    ) == {
        "bkmonitorv3",
        "test-bkmonitorv3",
    }

    # 路由表属性更新
    assert (
        models.InfluxDBStorage.objects.get(table_id="test.rt").influxdb_proxy_storage_id
        == models.InfluxDBProxyStorage.objects.get(proxy_cluster_id=101, instance_cluster_name="cluster1").id
    )
