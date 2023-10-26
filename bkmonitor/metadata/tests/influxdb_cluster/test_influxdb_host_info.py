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
import json

import pytest
from django.conf import settings

from metadata import models
from metadata.models import constants
from metadata.models.influxdb_cluster import InfluxDBHostInfo, InfluxDBTool
from metadata.utils.redis_tools import RedisTools

pytestmark = pytest.mark.django_db


class TestInfluxDBHostInfo(object):

    domain_name = "domain.com"
    influxdb_host_name = "host1"
    port = 123
    influxdb_username = "username"
    influxdb_password = "password"

    pytestmark = pytest.mark.django_db
    IS_CONSUL_MOCK = True
    es_index = {}

    def test_judge_shard(self):
        duration0 = "inF"
        duration1 = "qwer"
        duration2 = "10m"
        duration3 = "0h"
        duration4 = "3h"
        duration5 = "2w"
        duration6 = "181d"
        assert InfluxDBHostInfo.judge_shard(duration0) == "7d"
        try:
            InfluxDBHostInfo.judge_shard(duration1)
        except ValueError as e:
            assert str(e) == "source_duration_time format is incorrect!"
        try:
            InfluxDBHostInfo.judge_shard(duration2)
        except ValueError as e:
            assert str(e) == "retention policy duration must be at least 1h0m0s"
        try:
            InfluxDBHostInfo.judge_shard(duration3)
        except ValueError as e:
            assert str(e) == "source_duration_time format is incorrect!"
        assert InfluxDBHostInfo.judge_shard(duration4) == "1h"
        assert InfluxDBHostInfo.judge_shard(duration5) == "1d"
        assert InfluxDBHostInfo.judge_shard(duration6) == "7d"

    def test_duration_rationality_judgment(self):
        duration0 = "12ww"
        duration1 = "10m"
        duration2 = "0h"
        duration3 = "15d"
        try:
            InfluxDBHostInfo.duration_rationality_judgment(duration0)
        except ValueError as e:
            assert str(e) == "source_duration_time format is incorrect!"
        try:
            InfluxDBHostInfo.duration_rationality_judgment(duration1)
        except ValueError as e:
            assert str(e) == "retention policy duration must be at least 1h0m0s"
        try:
            InfluxDBHostInfo.duration_rationality_judgment(duration2)
        except ValueError as e:
            assert str(e) == "source_duration_time format is incorrect!"
        assert InfluxDBHostInfo.duration_rationality_judgment(duration3) is True

    def test_update_default_rp(self, mocker):
        # 提前准备好对应的信息
        models.InfluxDBHostInfo.objects.all().delete()
        test_influxdb_host_info = models.InfluxDBHostInfo.create_host_info(
            host_name=self.influxdb_host_name,
            domain_name="domain.com",
            port=123,
            username=self.influxdb_username,
            password=self.influxdb_password,
        )
        settings.TS_DATA_SAVED_DAYS = 1
        refresh_databases = ["db1"]
        mocker.patch("influxdb.client.InfluxDBClient.get_list_database", return_value=[{"name": "db1"}])
        get_list_rp = mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "rp1", "duration": "36h", "default": True}],
        )
        alter_rp = mocker.patch("influxdb.client.InfluxDBClient.alter_retention_policy", return_value=None)

        # 1d
        test_influxdb_host_info.update_default_rp(refresh_databases)
        alter_rp.assert_called_with(name="rp1", database="db1", duration="1d", default=True, shard_duration="7d")

        # 10d
        settings.TS_DATA_SAVED_DAYS = 10
        test_influxdb_host_info.update_default_rp(refresh_databases)
        alter_rp.assert_called_with(name="rp1", database="db1", duration="10d", default=True, shard_duration="7d")

        # 181d
        settings.TS_DATA_SAVED_DAYS = 181
        test_influxdb_host_info.update_default_rp(refresh_databases)
        alter_rp.assert_called_with(name="rp1", database="db1", duration="181d", default=True, shard_duration="7d")

        # skip1:该db不在需要刷新的set当中，不会执行到get_list_rp的语句
        get_list_rp.reset_mock()
        refresh_databases = ["db2"]
        get_list_rp = mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "rp1", "duration": "36h", "default": True}],
        )
        test_influxdb_host_info.update_default_rp(refresh_databases)
        get_list_rp.assert_not_called()

        # skip2:不是默认的rp配置，不会执行到alter_rp的语句
        alter_rp.reset_mock()
        refresh_databases = ["db1"]
        mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "rp1", "duration": "36h", "default": False}],
        )
        alter_rp = mocker.patch("influxdb.client.InfluxDBClient.alter_retention_policy", return_value=None)
        test_influxdb_host_info.update_default_rp(refresh_databases)
        alter_rp.assert_not_called()

        # skip3:发现默认配置和settings中的配置是一致的，不会执行到alter_rp的语句
        alter_rp.reset_mock()
        settings.TS_DATA_SAVED_DAYS = 1
        mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies",
            return_value=[{"name": "rp1", "duration": "24h", "default": True}],
        )
        alter_rp = mocker.patch("influxdb.client.InfluxDBClient.alter_retention_policy", return_value=None)
        test_influxdb_host_info.update_default_rp(refresh_databases)
        alter_rp.assert_not_called()

        # 删除创建的 host_info，以免影响后续的测试
        models.InfluxDBHostInfo.objects.filter(host_name=self.influxdb_host_name).delete()


def test_push_to_redis_success(patch_redis_tools):
    """测试成功写入redis"""
    key = "push_test"
    field = "push_field"
    value = json.dumps({"test": "test"})

    InfluxDBTool.push_to_redis(key, field, value)

    redis_data = RedisTools.hget(f"{constants.INFLUXDB_KEY_PREFIX}:{key}", field)
    assert type(redis_data) == bytes
    assert redis_data.decode('utf8') == value


@pytest.fixture
def create_and_delete_record():
    params = [
        models.InfluxDBClusterInfo(host_name="host1", cluster_name="cluster1"),
        models.InfluxDBClusterInfo(host_name="host2", cluster_name="cluster2"),
    ]
    models.InfluxDBClusterInfo.objects.bulk_create(params)
    yield
    models.InfluxDBClusterInfo.objects.all().delete()


class TestInfluxDBClusterInfo:
    def test_clean_redis_cluster_config(self, create_and_delete_record, patch_redis_tools):
        key = f"{constants.INFLUXDB_KEY_PREFIX}:{constants.INFLUXDB_CLUSTER_INFO_KEY}"
        push_data = {
            "cluster1": json.dumps(["host1"]),
            "cluster2": json.dumps(["host2"]),
            "cluster3": json.dumps(["host3"]),
        }
        RedisTools.hmset_to_redis(key, push_data)

        # 检测 key 下数量为3
        assert len(RedisTools.hgetall(key)) == 3

        # 删除不存在的 key
        models.InfluxDBClusterInfo.clean_redis_cluster_config()
        # 检测 key 为 2
        assert len(RedisTools.hgetall(key)) == 2
