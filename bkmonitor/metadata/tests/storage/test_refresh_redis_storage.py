"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections import UserList
from unittest.mock import MagicMock, PropertyMock

import pytest
import fakeredis

from metadata.models.storage import ClusterInfo


class MockClusterList(UserList):
    """Mock ClusterInfo 查询结果列表"""

    def count(self):
        return len(self.data)


class TestRefreshRedisStorage:
    """测试刷新存储配置到 Redis"""

    @pytest.fixture
    def mock_redis(self, mocker):
        """Mock Redis 客户端"""
        mock_redis_client = fakeredis.FakeRedis(decode_responses=False)
        mock_redis_instance = MagicMock()
        mock_redis_instance.client = mock_redis_client
        mocker.patch("metadata.models.storage.RedisTools", return_value=mock_redis_instance)
        # 同时 mock RedisTools().client 属性
        from metadata.utils.redis_tools import RedisTools

        mocker.patch.object(RedisTools, "client", new_callable=PropertyMock, return_value=mock_redis_client)
        return mock_redis_client

    def test_refresh_redis_storage_config_single_cluster(self, mock_redis, mocker):
        """测试刷新单个存储集群配置到 Redis"""
        publish_spy = mocker.spy(mock_redis, "publish")

        # 创建 mock 集群信息
        cluster_info = ClusterInfo(
            cluster_id=1,
            cluster_name="test_cluster",
            cluster_type="influxdb",
            domain_name="test.example.com",
            port=8086,
            schema="http",
            username="test_user",
            password="test_password",
        )

        # Mock ClusterInfo.objects.all() 返回单个集群
        cluster_list = MockClusterList()
        cluster_list.append(cluster_info)
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

        # 执行刷新操作
        ClusterInfo.refresh_redis_storage_config()

        # 验证 Redis 中是否写入了配置
        redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
        stored_value = mock_redis.get(redis_key)

        # 验证配置已写入
        assert stored_value is not None

        # 验证配置内容正确
        if isinstance(stored_value, bytes):
            stored_value = stored_value.decode("utf-8")
        stored_config = json.loads(stored_value)

        assert stored_config["address"] == "http://test.example.com:8086"
        assert stored_config["username"] == "test_user"
        assert stored_config["password"] == "test_password"
        assert stored_config["type"] == "influxdb"
        assert publish_spy.call_count == 1
        assert publish_spy.call_args.args[0] == ClusterInfo.REDIS_CHANNEL

    def test_refresh_redis_storage_config_removes_stale_keys(self, mock_redis, mocker):
        """数据库删除 Storage 后，全量刷新应清理旧 Key 并通知 UQ。"""
        stale_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:999"
        mock_redis.set(stale_key, "{}")
        publish_spy = mocker.spy(mock_redis, "publish")
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=MockClusterList())

        ClusterInfo.refresh_redis_storage_config()

        assert mock_redis.get(stale_key) is None
        publish_spy.assert_called_once()
        assert publish_spy.call_args.args[0] == ClusterInfo.REDIS_CHANNEL

    def test_refresh_redis_storage_config_multiple_clusters(self, mock_redis, mocker):
        """测试刷新多个存储集群配置到 Redis"""
        # 创建多个 mock 集群信息
        cluster_list = MockClusterList()
        cluster_list.append(
            ClusterInfo(
                cluster_id=1,
                cluster_name="influxdb_cluster",
                cluster_type="influxdb",
                domain_name="influxdb.example.com",
                port=8086,
                schema="http",
                username="influx_user",
                password="influx_pass",
            )
        )
        cluster_list.append(
            ClusterInfo(
                cluster_id=2,
                cluster_name="kafka_cluster",
                cluster_type="kafka",
                domain_name="kafka.example.com",
                port=9092,
                schema="http",
                username="kafka_user",
                password="kafka_pass",
            )
        )
        cluster_list.append(
            ClusterInfo(
                cluster_id=3,
                cluster_name="redis_cluster",
                cluster_type="redis",
                domain_name="redis.example.com",
                port=6379,
                schema="tcp",  # 非 http/https，应该默认使用 http
                username="redis_user",
                password="redis_pass",
            )
        )

        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

        # 执行刷新操作
        ClusterInfo.refresh_redis_storage_config()

        # 验证所有集群配置都已写入 Redis
        for cluster in cluster_list:
            redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:{cluster.cluster_id}"
            stored_value = mock_redis.get(redis_key)

            assert stored_value is not None

            if isinstance(stored_value, bytes):
                stored_value = stored_value.decode("utf-8")
            stored_config = json.loads(stored_value)

            # 对于非 http/https 的 schema，应该默认使用 http
            expected_schema = cluster.schema if cluster.schema in ["http", "https"] else "http"
            assert stored_config["address"] == f"{expected_schema}://{cluster.domain_name}:{cluster.port}"
            assert stored_config["username"] == cluster.username
            assert stored_config["password"] == cluster.password
            assert stored_config["type"] == cluster.cluster_type

    def test_refresh_redis_storage_config_schema_handling(self, mock_redis, mocker):
        """测试不同 schema 的处理逻辑"""
        test_cases = [
            {"schema": "http", "expected_schema": "http"},
            {"schema": "https", "expected_schema": "https"},
            {"schema": "tcp", "expected_schema": "http"},  # 非 http/https 应该默认使用 http
            {"schema": "", "expected_schema": "http"},
            {"schema": None, "expected_schema": "http"},
        ]

        for test_case in test_cases:
            cluster_info = ClusterInfo(
                cluster_id=1,
                cluster_name="test_cluster",
                cluster_type="influxdb",
                domain_name="test.com",
                port=8086,
                schema=test_case["schema"],
                username="user",
                password="pass",
            )

            cluster_list = MockClusterList()
            cluster_list.append(cluster_info)
            mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

            # 清空 Redis
            mock_redis.flushdb()

            # 执行刷新操作
            ClusterInfo.refresh_redis_storage_config()

            # 验证地址格式
            redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
            stored_value = mock_redis.get(redis_key)
            assert stored_value is not None

            if isinstance(stored_value, bytes):
                stored_value = stored_value.decode("utf-8")
            stored_config = json.loads(stored_value)

            expected_address = f"{test_case['expected_schema']}://test.com:8086"
            assert stored_config["address"] == expected_address
