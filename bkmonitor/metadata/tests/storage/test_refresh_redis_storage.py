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
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=MockClusterList())

        ClusterInfo.refresh_redis_storage_config()

        assert mock_redis.get(stale_key) is None

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

    def test_get_redis_storage_config_existing(self, mock_redis, mocker):
        """测试从 Redis 获取已存在的存储集群配置"""
        # 先写入配置到 Redis
        redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
        config_value = {
            "address": "http://test.example.com:8086",
            "username": "test_user",
            "password": "test_password",
            "type": "influxdb",
        }
        mock_redis.set(redis_key, json.dumps(config_value))

        # 从 Redis 读取配置
        result = ClusterInfo.get_redis_storage_config(1)

        # 验证配置内容
        assert result is not None
        assert result["address"] == config_value["address"]
        assert result["username"] == config_value["username"]
        assert result["password"] == config_value["password"]
        assert result["type"] == config_value["type"]

    def test_get_redis_storage_config_not_existing(self, mock_redis):
        """测试从 Redis 获取不存在的存储集群配置"""
        # 不写入任何配置，直接读取
        result = ClusterInfo.get_redis_storage_config(999)

        # 应该返回 None
        assert result is None

    def test_get_redis_storage_config_bytes_decoding(self, mock_redis):
        """测试从 Redis 获取配置时处理 bytes 类型数据"""
        # 写入 bytes 类型的配置（fakeredis 默认返回 bytes）
        redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
        config_value = {
            "address": "http://test.example.com:8086",
            "username": "test_user",
            "password": "test_password",
            "type": "influxdb",
        }
        mock_redis.set(redis_key, json.dumps(config_value))

        # 从 Redis 读取配置（fakeredis 返回 bytes）
        result = ClusterInfo.get_redis_storage_config(1)

        # 验证配置内容（应该能正确解码 bytes）
        assert result is not None
        assert result["address"] == config_value["address"]
        assert result["username"] == config_value["username"]
        assert result["password"] == config_value["password"]
        assert result["type"] == config_value["type"]

    def test_get_redis_storage_config_invalid_json(self, mock_redis):
        """测试从 Redis 获取无效 JSON 格式的配置"""
        # 写入无效的 JSON 字符串
        redis_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
        mock_redis.set(redis_key, "invalid json string")

        # 从 Redis 读取配置，应该捕获异常并返回 None
        result = ClusterInfo.get_redis_storage_config(1)

        # 应该返回 None（因为 JSON 解析失败）
        assert result is None

    def test_get_redis_storage_config_redis_error(self, mock_redis, mocker):
        """测试 Redis 连接错误时的处理"""
        # Mock Redis get 方法抛出异常
        mocker.patch.object(mock_redis, "get", side_effect=Exception("Redis connection error"))

        # 从 Redis 读取配置，应该捕获异常并返回 None
        result = ClusterInfo.get_redis_storage_config(1)

        # 应该返回 None（因为 Redis 连接失败）
        assert result is None

    def test_get_redis_storage_config_can_propagate_diagnostic_error(self, mock_redis, mocker):
        """诊断接口应能区分后端失败和配置不存在。"""
        mocker.patch.object(mock_redis, "get", side_effect=ConnectionError("Redis connection error"))

        with pytest.raises(ConnectionError, match="Redis connection error"):
            ClusterInfo.get_redis_storage_config(1, raise_on_error=True)

    def test_refresh_and_get_redis_storage_config_integration(self, mock_redis, mocker):
        """测试刷新和获取 Redis 配置的集成测试"""
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

        cluster_list = MockClusterList()
        cluster_list.append(cluster_info)
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

        # 1. 先刷新配置到 Redis
        ClusterInfo.refresh_redis_storage_config()

        # 2. 再从 Redis 读取配置
        result = ClusterInfo.get_redis_storage_config(1)

        # 3. 验证配置内容一致
        assert result is not None
        assert result["address"] == "http://test.example.com:8086"
        assert result["username"] == "test_user"
        assert result["password"] == "test_password"
        assert result["type"] == "influxdb"

    def test_redis_key_format(self, mock_redis, mocker):
        """测试 Redis key 格式是否正确"""
        # 创建 mock 集群信息
        cluster_info = ClusterInfo(
            cluster_id=123,
            cluster_name="test_cluster",
            cluster_type="influxdb",
            domain_name="test.example.com",
            port=8086,
            schema="http",
            username="test_user",
            password="test_password",
        )

        cluster_list = MockClusterList()
        cluster_list.append(cluster_info)
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

        # 执行刷新操作
        ClusterInfo.refresh_redis_storage_config()

        # 验证 Redis key 格式
        expected_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:123"
        stored_value = mock_redis.get(expected_key)
        assert stored_value is not None

        # 验证使用相同的 key 可以读取配置
        result = ClusterInfo.get_redis_storage_config(123)
        assert result is not None

    def test_get_all_redis_storage_config(self, mock_redis, mocker):
        """测试从 Redis 获取所有存储集群配置"""
        # 创建多个 mock 集群信息
        cluster_list = MockClusterList()
        cluster_list.append(
            ClusterInfo(
                cluster_id=1,
                cluster_name="cluster1",
                cluster_type="influxdb",
                domain_name="test1.com",
                port=8086,
                schema="http",
                username="user1",
                password="pass1",
            )
        )
        cluster_list.append(
            ClusterInfo(
                cluster_id=2,
                cluster_name="cluster2",
                cluster_type="kafka",
                domain_name="test2.com",
                port=9092,
                schema="http",
                username="user2",
                password="pass2",
            )
        )

        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)
        mocker.patch(
            "metadata.models.storage.ClusterInfo.objects.values_list",
            return_value=[1, 2],
        )

        # 先刷新配置到 Redis
        ClusterInfo.refresh_redis_storage_config()

        # 获取所有配置
        all_configs = ClusterInfo.get_all_redis_storage_config()

        # 验证返回了所有配置
        assert isinstance(all_configs, dict)
        assert len(all_configs) == 2
        assert "1" in all_configs
        assert "2" in all_configs
        assert all_configs["1"]["type"] == "influxdb"
        assert all_configs["2"]["type"] == "kafka"

    def test_get_all_consul_storage_config_can_propagate_partial_failure(self, mocker):
        """批量诊断中任一 Consul 读取失败都不能伪装成成功的部分结果。"""
        consul_client = MagicMock()
        consul_client.get.side_effect = RuntimeError("consul unavailable")
        mocker.patch("metadata.models.storage.consul_tools.HashConsul", return_value=consul_client)
        mocker.patch("metadata.models.storage.ClusterInfo.objects.values_list", return_value=[1])

        with pytest.raises(RuntimeError, match="consul unavailable"):
            ClusterInfo.get_all_consul_storage_config(raise_on_error=True)
