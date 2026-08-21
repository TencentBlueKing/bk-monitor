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
import time
from collections import UserList

import pytest

from metadata import config
from metadata.models.storage import ClusterInfo
from metadata.tests.conftest import MockHashConsul

# 这些测试不需要数据库，只需要 mock 对象
pytestmark = pytest.mark.django_db(transaction=True)


class MockClusterList(UserList):
    """Mock ClusterInfo 查询结果列表"""

    def count(self):
        return len(self.data)


class TestRefreshConsulStorage:
    """测试刷新存储配置到 Consul"""

    @pytest.fixture
    def mock_consul(self, mocker):
        """Mock Consul 客户端"""
        mock_hash_consul = MockHashConsul()
        mock_hash_consul._kv_store.clear()
        mock_hash_consul._call_history.clear()
        mocker.patch("metadata.models.storage.consul_tools.HashConsul", return_value=mock_hash_consul)
        return mock_hash_consul

    def test_refresh_consul_storage_config_single_cluster(self, mock_consul, mocker):
        """测试刷新单个存储集群配置到 Consul"""
        # 清空 mock_consul，避免之前测试的数据污染
        mock_consul._kv_store = {}

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
        ClusterInfo.refresh_consul_storage_config()

        # 验证 Consul 中是否写入了配置
        consul_path = "/".join([ClusterInfo.CONSUL_PREFIX_PATH, "1"])
        assert consul_path in mock_consul._kv_store  # 配置已写入
        assert ClusterInfo.CONSUL_VERSION_PATH in mock_consul._kv_store  # 版本信息已写入

        # 获取配置项
        config_data = mock_consul._kv_store[consul_path]
        stored_config = json.loads(config_data["Value"])

        # 验证配置内容正确
        assert stored_config["address"] == "http://test.example.com:8086"
        assert stored_config["username"] == "test_user"
        assert stored_config["password"] == "test_password"
        assert stored_config["type"] == "influxdb"

        # 验证版本信息已写入
        version_data = mock_consul._kv_store[ClusterInfo.CONSUL_VERSION_PATH]
        version_value = json.loads(version_data["Value"])
        assert "time" in version_value

    def test_consul_storage_paths_use_the_same_backend_app_prefix(self):
        """数据与版本必须位于同一 Consul 根路径，供 UQ Watch 正确触发。"""
        assert ClusterInfo.CONSUL_PREFIX_PATH.startswith(config.MIGRATION_CONSUL_PATH)
        assert ClusterInfo.CONSUL_VERSION_PATH.startswith(config.MIGRATION_CONSUL_PATH)

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("::1", "http://[::1]:9200"),
            ("[::1]", "http://[::1]:9200"),
            ("127.0.0.1", "http://127.0.0.1:9200"),
            ("storage.example.com", "http://storage.example.com:9200"),
        ],
    )
    def test_format_storage_address_handles_ipv6_literals(self, host, expected):
        assert ClusterInfo._format_storage_address("http", host, 9200) == expected

    def test_refresh_consul_storage_config_multiple_clusters(self, mock_consul, mocker):
        """测试刷新多个存储集群配置到 Consul"""
        # 清空 mock_consul，避免之前测试的数据污染
        mock_consul._kv_store = {}

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
        ClusterInfo.refresh_consul_storage_config()

        # 验证所有集群配置都已写入 Consul
        for cluster in cluster_list:
            consul_path = "/".join([ClusterInfo.CONSUL_PREFIX_PATH, str(cluster.cluster_id)])
            assert consul_path in mock_consul._kv_store

            config_data = mock_consul._kv_store[consul_path]
            stored_config = json.loads(config_data["Value"])

            # 对于非 http/https 的 schema，应该默认使用 http
            expected_schema = cluster.schema if cluster.schema in ["http", "https"] else "http"
            assert stored_config["address"] == f"{expected_schema}://{cluster.domain_name}:{cluster.port}"
            assert stored_config["username"] == cluster.username
            assert stored_config["password"] == cluster.password
            assert stored_config["type"] == cluster.cluster_type

        # 验证版本信息已写入
        assert ClusterInfo.CONSUL_VERSION_PATH in mock_consul._kv_store

    def test_refresh_consul_storage_config_schema_handling(self, mock_consul, mocker):
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

            # 清空 mock_consul
            mock_consul._kv_store = {}

            # 执行刷新操作
            ClusterInfo.refresh_consul_storage_config()

            # 验证地址格式
            consul_path = "/".join([ClusterInfo.CONSUL_PREFIX_PATH, "1"])
            assert consul_path in mock_consul._kv_store

            config_data = mock_consul._kv_store[consul_path]
            stored_config = json.loads(config_data["Value"])
            expected_address = f"{test_case['expected_schema']}://test.com:8086"
            assert stored_config["address"] == expected_address

    def test_refresh_consul_storage_config_version_info(self, mock_consul, mocker):
        """测试版本信息是否正确写入"""
        # 清空 mock_consul，避免之前测试的数据污染
        mock_consul._kv_store = {}

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

        # 执行刷新操作
        before_time = time.time()
        ClusterInfo.refresh_consul_storage_config()
        after_time = time.time()

        # 验证版本信息
        assert ClusterInfo.CONSUL_VERSION_PATH in mock_consul._kv_store
        version_data = mock_consul._kv_store[ClusterInfo.CONSUL_VERSION_PATH]
        version_value = json.loads(version_data["Value"])
        assert "time" in version_value
        version_time = version_value["time"]
        # 允许时间戳有小的误差（1秒），因为时间获取可能有延迟
        assert before_time - 1 <= version_time <= after_time + 1

    def test_refresh_consul_storage_config_empty_cluster_list(self, mock_consul, mocker):
        """测试空集群列表的处理"""
        # 清空 mock_consul，避免之前测试的数据污染
        mock_consul._kv_store = {}

        # Mock 空集群列表
        cluster_list = MockClusterList()
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)

        # 执行刷新操作
        ClusterInfo.refresh_consul_storage_config()

        # 验证只写入了版本信息，没有配置信息
        config_keys = [k for k in mock_consul._kv_store.keys() if k != ClusterInfo.CONSUL_VERSION_PATH]
        assert len(config_keys) == 0

        # 验证版本信息已写入
        assert ClusterInfo.CONSUL_VERSION_PATH in mock_consul._kv_store

    def test_refresh_consul_storage_config_removes_stale_keys(self, mock_consul, mocker):
        """数据库中不存在的 Consul Storage Key 应在全量刷新时删除。"""
        stale_key = f"{ClusterInfo.CONSUL_PREFIX_PATH}/999"
        mock_consul.put(stale_key, {"type": "influxdb"})
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=MockClusterList())

        ClusterInfo.refresh_consul_storage_config()

        assert stale_key not in mock_consul._kv_store

    def test_refresh_consul_storage_config_propagates_data_write_failure(self, mock_consul, mocker):
        """数据写入失败时不能推进 version 或把刷新任务标记为成功。"""
        cluster_list = MockClusterList(
            [
                ClusterInfo(
                    cluster_id=1,
                    cluster_name="test_cluster",
                    cluster_type="influxdb",
                    domain_name="test.example.com",
                    port=8086,
                    schema="http",
                )
            ]
        )
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=cluster_list)
        mocker.patch.object(mock_consul, "put", return_value=False)

        with pytest.raises(RuntimeError, match="put storage config to consul failed"):
            ClusterInfo.refresh_consul_storage_config()

        assert ClusterInfo.CONSUL_VERSION_PATH not in mock_consul._kv_store

    def test_refresh_consul_storage_config_propagates_version_write_failure(self, mock_consul, mocker):
        """version 写入失败也必须向任务层传播。"""
        mocker.patch("metadata.models.storage.ClusterInfo.objects.all", return_value=MockClusterList())
        mocker.patch.object(mock_consul, "put", return_value=False)

        with pytest.raises(RuntimeError, match="put storage version to consul failed"):
            ClusterInfo.refresh_consul_storage_config()
