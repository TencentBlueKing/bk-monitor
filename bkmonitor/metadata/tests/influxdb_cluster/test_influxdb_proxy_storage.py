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

from metadata.models import InfluxDBProxyStorage, constants
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools

FAKE_CLUSTER_SERVICE_NAME_ONE = "svc_test_one"
FAKE_CLUSTER_NAME_ONE = "cluster_one"
FAKE_CLUSTER_SERVICE_NAME_TWO = "svc_test_two"
FAKE_CLUSTER_NAME_TWO = "cluster_two"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_records():
    data = [
        InfluxDBProxyStorage(
            proxy_cluster_id=1,
            service_name=FAKE_CLUSTER_SERVICE_NAME_ONE,
            instance_cluster_name=FAKE_CLUSTER_NAME_ONE,
            creator="system",
            updater="system",
        ),
        InfluxDBProxyStorage(
            proxy_cluster_id=2,
            service_name=FAKE_CLUSTER_SERVICE_NAME_TWO,
            instance_cluster_name=FAKE_CLUSTER_NAME_TWO,
            creator="system",
            updater="system",
        ),
    ]
    InfluxDBProxyStorage.objects.bulk_create(data)
    yield
    InfluxDBProxyStorage.objects.all().delete()


class TestInfluxDBProxyStorage:
    def test_push_all_data(self, create_and_delete_records, patch_redis_tools, patch_consul_tool, mocker):
        # push 所有数据
        InfluxDBProxyStorage.push()

        # 校验 redis 数据
        key = f"{constants.INFLUXDB_KEY_PREFIX}:{constants.INFLUXDB_PROXY_STORAGE_INFO_KEY}"
        assert len(RedisTools.hgetall(key)) == 2

        redis_data = RedisTools.hget(key, FAKE_CLUSTER_SERVICE_NAME_ONE)
        assert type(redis_data) == bytes
        assert json.loads(redis_data.decode("utf-8")) == [FAKE_CLUSTER_NAME_ONE]

        # 校验 consul 数据
        client = consul_tools.HashConsul()
        assert client.get(
            InfluxDBProxyStorage.CONSUL_PATH.format(service_name=FAKE_CLUSTER_SERVICE_NAME_ONE)
        ) == json.dumps([FAKE_CLUSTER_NAME_ONE])

    def test_push_specific_cluster(self, create_and_delete_records, patch_redis_tools, patch_consul_tool, mocker):
        # push 特定的集群
        InfluxDBProxyStorage.push(FAKE_CLUSTER_SERVICE_NAME_ONE)

        key = f"{constants.INFLUXDB_KEY_PREFIX}:{constants.INFLUXDB_PROXY_STORAGE_INFO_KEY}"
        assert len(RedisTools.hgetall(key)) == 1

        redis_data = RedisTools.hget(key, FAKE_CLUSTER_SERVICE_NAME_ONE)
        assert type(redis_data) == bytes
        assert json.loads(redis_data.decode("utf-8")) == [FAKE_CLUSTER_NAME_ONE]

    def test_clean(self, create_and_delete_records, patch_redis_tools, patch_consul_tool, mocker):
        # 先推送数据
        InfluxDBProxyStorage.push()
        key = f"{constants.INFLUXDB_KEY_PREFIX}:{constants.INFLUXDB_PROXY_STORAGE_INFO_KEY}"
        assert len(RedisTools.hgetall(key)) == 2

        # 删除记录
        InfluxDBProxyStorage.objects.filter(service_name=FAKE_CLUSTER_SERVICE_NAME_ONE).delete()
        # 执行清理操作
        InfluxDBProxyStorage.clean()

        # 检查记录是否存在
        assert len(RedisTools.hgetall(key)) == 1
        redis_data = RedisTools.hget(key, FAKE_CLUSTER_SERVICE_NAME_ONE)
        assert redis_data is None

        # 检查 consul
        client = consul_tools.HashConsul()
        assert client.get(
            InfluxDBProxyStorage.CONSUL_PATH.format(service_name=FAKE_CLUSTER_SERVICE_NAME_TWO)
        ) == json.dumps([FAKE_CLUSTER_NAME_TWO])
