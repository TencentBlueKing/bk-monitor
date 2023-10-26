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

from metadata import models


@pytest.fixture
def create_and_delete_record():
    models.InfluxDBClusterInfo.objects.create(host_name="host", cluster_name="default", host_readable=True)
    models.InfluxDBHostInfo.objects.create(
        host_name="host",
        domain_name="domain.com",
        port=123,
        username="username",
        password="password",
    )
    models.InfluxDBProxyStorage.objects.create(
        proxy_cluster_id=1, service_name="default_service", instance_cluster_name="default"
    )
    yield
    models.InfluxDBClusterInfo.objects.all().delete()
    models.InfluxDBHostInfo.objects.all().delete()
    models.InfluxDBProxyStorage.objects.all().delete()


class TestInfluxDBStorage(object):
    pytestmark = pytest.mark.django_db
    IS_CONSUL_MOCK = True
    es_index = {}

    def test_ensure_rp(self, create_and_delete_record, mocker):
        proxy_storage = models.InfluxDBProxyStorage.objects.get(proxy_cluster_id=1, service_name="default_service")
        test_influxdb_storage = models.InfluxDBStorage(
            table_id="table",
            storage_cluster_id=1,
            real_table_name="table",
            database="db1",
            source_duration_time="36h",
            use_default_rp=False,
            enable_refresh_rp=True,
            proxy_cluster_name="default",
            influxdb_proxy_storage_id=proxy_storage.id,
        )

        get_list_rp = mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "bkmonitor_rp_table", "duration": "24h", "default": True}],
        )
        alter_rp = mocker.patch("influxdb.client.InfluxDBClient.alter_retention_policy", return_value=None)

        # 36h
        test_influxdb_storage.ensure_rp()
        alter_rp.assert_called_with(name="bkmonitor_rp_table", database="db1", duration="36h", shard_duration="7d")

        # 3w
        test_influxdb_storage.source_duration_time = "3w"
        test_influxdb_storage.ensure_rp()
        alter_rp.assert_called_with(name="bkmonitor_rp_table", database="db1", duration="3w", shard_duration="7d")

        # 181d
        test_influxdb_storage.source_duration_time = "181d"
        test_influxdb_storage.ensure_rp()
        alter_rp.assert_called_with(name="bkmonitor_rp_table", database="db1", duration="181d", shard_duration="7d")

        create_rp = mocker.patch("influxdb.client.InfluxDBClient.create_retention_policy", return_value=None)
        # 不存在该RP
        test_influxdb_storage.table_id = "table2"

        # 36h
        test_influxdb_storage.source_duration_time = "36h"
        test_influxdb_storage.ensure_rp()
        create_rp.assert_called_with(
            name="bkmonitor_rp_table2",
            database="db1",
            duration="36h",
            replication=1,
            shard_duration="7d",
            default=False,
        )

        # 3w
        test_influxdb_storage.source_duration_time = "3w"
        test_influxdb_storage.ensure_rp()
        create_rp.assert_called_with(
            name="bkmonitor_rp_table2",
            database="db1",
            duration="3w",
            replication=1,
            shard_duration="7d",
            default=False,
        )

        # 181d
        test_influxdb_storage.source_duration_time = "181d"
        test_influxdb_storage.ensure_rp()
        create_rp.assert_called_with(
            name="bkmonitor_rp_table2",
            database="db1",
            duration="181d",
            replication=1,
            shard_duration="7d",
            default=False,
        )

        # skip1:使用默认RP 或 不周期刷新RP
        get_list_rp.reset_mock()
        test_influxdb_storage.use_default_rp = True
        get_list_rp = mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "bkmonitor_rp_table", "duration": "24h", "default": True}],
        )
        test_influxdb_storage.ensure_rp()
        get_list_rp.assert_not_called()

        get_list_rp.reset_mock()
        test_influxdb_storage.use_default_rp = False
        test_influxdb_storage.enable_refresh_rp = False
        get_list_rp = mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "bkmonitor_rp_table", "duration": "24h", "default": True}],
        )
        test_influxdb_storage.ensure_rp()
        get_list_rp.assert_not_called()

        # skip2:duration与原设置值一致，执行不到alter_rp的语句
        alter_rp.reset_mock()
        test_influxdb_storage.enable_refresh_rp = True
        test_influxdb_storage.table_id = "table2"
        test_influxdb_storage.source_duration_time = "24h"
        alter_rp = mocker.patch("influxdb.client.InfluxDBClient.alter_retention_policy", return_value=None)
        test_influxdb_storage.ensure_rp()
        alter_rp.assert_not_called()
