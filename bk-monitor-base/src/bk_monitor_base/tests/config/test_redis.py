"""
Redis 配置单元测试
"""

import pytest

from bk_monitor_base.config import Config
from bk_monitor_base.config.redis import RedisConfig, RedisMode


class TestRedisConfig:
    """测试 Redis 配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = RedisConfig()

        # 连接配置
        assert config.mode == RedisMode.SINGLE
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password == ""

        # 连接池配置
        assert config.max_connections == 50
        assert config.socket_timeout == 10
        assert config.socket_connect_timeout == 10
        assert config.socket_keepalive is True

        # Sentinel 模式配置
        assert config.sentinel_name == ""
        assert config.sentinel_hosts == []
        assert config.sentinel_password == ""

        # Cluster 模式配置
        assert config.cluster_nodes == []

    def test_custom_single_mode_config(self):
        """测试自定义单机模式配置"""
        config = RedisConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password="test_password",
            max_connections=100,
            socket_timeout=20,
            socket_connect_timeout=15,
            socket_keepalive=False,
        )

        assert config.mode == RedisMode.SINGLE
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == "test_password"
        assert config.max_connections == 100
        assert config.socket_timeout == 20
        assert config.socket_connect_timeout == 15
        assert config.socket_keepalive is False

    def test_sentinel_mode_config(self):
        """测试哨兵模式配置"""
        config = RedisConfig(
            mode=RedisMode.SENTINEL,
            sentinel_name="mymaster",
            sentinel_hosts=[("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
            password="master_password",
            db=2,
        )

        assert config.mode == RedisMode.SENTINEL
        assert config.sentinel_name == "mymaster"
        assert config.sentinel_hosts == [("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)]
        assert config.password == "master_password"
        assert config.sentinel_password == ""
        assert config.db == 2

    def test_sentinel_mode_with_sentinel_password(self):
        """测试哨兵模式配置（哨兵节点单独密码）"""
        config = RedisConfig(
            mode=RedisMode.SENTINEL,
            sentinel_name="mymaster",
            sentinel_hosts=[("sentinel1", 26379), ("sentinel2", 26379)],
            password="master_password",
            sentinel_password="sentinel_password",
        )

        assert config.mode == RedisMode.SENTINEL
        assert config.password == "master_password"
        assert config.sentinel_password == "sentinel_password"

    def test_cluster_mode_config(self):
        """测试集群模式配置"""
        config = RedisConfig(
            mode=RedisMode.CLUSTER,
            cluster_nodes=[
                ("node1.example.com", 6379),
                ("node2.example.com", 6379),
                ("node3.example.com", 6379),
            ],
            password="cluster_password",
        )

        assert config.mode == RedisMode.CLUSTER
        assert config.cluster_nodes == [
            ("node1.example.com", 6379),
            ("node2.example.com", 6379),
            ("node3.example.com", 6379),
        ]
        assert config.password == "cluster_password"


class TestRedisConnectionKwargs:
    """测试 get_connection_kwargs 方法"""

    def test_single_mode_connection_kwargs(self):
        """测试单机模式连接参数"""
        config = RedisConfig(
            host="localhost",
            port=6379,
            db=0,
            password="test_password",
            max_connections=50,
            socket_timeout=10,
            socket_connect_timeout=10,
            socket_keepalive=True,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 6379
        assert kwargs["db"] == 0
        assert kwargs["password"] == "test_password"
        assert kwargs["max_connections"] == 50
        assert kwargs["socket_timeout"] == 10
        assert kwargs["socket_connect_timeout"] == 10
        assert kwargs["socket_keepalive"] is True

    def test_single_mode_without_password(self):
        """测试单机模式无密码连接参数"""
        config = RedisConfig(host="localhost", port=6379, db=0)

        kwargs = config.get_connection_kwargs()

        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 6379
        assert kwargs["db"] == 0
        assert "password" not in kwargs  # 空密码应该被移除

    def test_sentinel_mode_connection_kwargs(self):
        """测试哨兵模式连接参数"""
        config = RedisConfig(
            mode=RedisMode.SENTINEL,
            sentinel_name="mymaster",
            sentinel_hosts=[("sentinel1", 26379), ("sentinel2", 26379)],
            password="master_password",
            db=1,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["sentinel_name"] == "mymaster"
        assert kwargs["sentinels"] == [("sentinel1", 26379), ("sentinel2", 26379)]
        assert kwargs["password"] == "master_password"
        assert kwargs["db"] == 1
        assert "host" not in kwargs
        assert "port" not in kwargs
        assert "sentinel_kwargs" not in kwargs  # 没有单独的哨兵密码

    def test_sentinel_mode_with_sentinel_password_kwargs(self):
        """测试哨兵模式连接参数（哨兵节点单独密码）"""
        config = RedisConfig(
            mode=RedisMode.SENTINEL,
            sentinel_name="mymaster",
            sentinel_hosts=[("sentinel1", 26379), ("sentinel2", 26379)],
            password="master_password",
            sentinel_password="sentinel_password",
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["sentinel_name"] == "mymaster"
        assert kwargs["sentinels"] == [("sentinel1", 26379), ("sentinel2", 26379)]
        assert kwargs["password"] == "master_password"
        assert kwargs["sentinel_kwargs"] == {"password": "sentinel_password"}

    def test_cluster_mode_connection_kwargs(self):
        """测试集群模式连接参数"""
        config = RedisConfig(
            mode=RedisMode.CLUSTER,
            cluster_nodes=[
                ("node1.example.com", 6379),
                ("node2.example.com", 6379),
                ("node3.example.com", 6379),
            ],
            password="cluster_password",
            db=0,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["startup_nodes"] == [
            ("node1.example.com", 6379),
            ("node2.example.com", 6379),
            ("node3.example.com", 6379),
        ]
        assert kwargs["password"] == "cluster_password"
        assert kwargs["db"] == 0
        assert "host" not in kwargs
        assert "port" not in kwargs

    def test_connection_kwargs_filters_none_values(self):
        """测试连接参数过滤 None 值"""
        config = RedisConfig(host="localhost", port=6379, db=0, password="")

        kwargs = config.get_connection_kwargs()

        # 空字符串的密码会被转换为 None 并过滤掉
        assert "password" not in kwargs
        # 其他有效值应该保留
        assert "host" in kwargs
        assert "port" in kwargs
        assert "db" in kwargs

    def test_connection_kwargs_includes_pool_settings(self):
        """测试连接参数包含连接池设置"""
        config = RedisConfig(
            host="localhost",
            port=6379,
            max_connections=100,
            socket_timeout=20,
            socket_connect_timeout=15,
            socket_keepalive=False,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["max_connections"] == 100
        assert kwargs["socket_timeout"] == 20
        assert kwargs["socket_connect_timeout"] == 15
        assert kwargs["socket_keepalive"] is False


class TestRedisMode:
    """测试 RedisMode 枚举"""

    def test_redis_mode_values(self):
        """测试 Redis 模式枚举值"""
        assert RedisMode.SINGLE == "single"
        assert RedisMode.SENTINEL == "sentinel"
        assert RedisMode.CLUSTER == "cluster"

    def test_redis_mode_assignment(self):
        """测试 Redis 模式赋值"""
        config = RedisConfig(mode="single")
        assert config.mode == RedisMode.SINGLE

        config = RedisConfig(mode="sentinel")
        assert config.mode == RedisMode.SENTINEL

        config = RedisConfig(mode="cluster")
        assert config.mode == RedisMode.CLUSTER


class TestRedisConfigWithAliases:
    """测试使用别名初始化配置"""

    def test_config_with_uppercase_aliases(self):
        """测试使用大写别名初始化配置"""
        config = RedisConfig(
            MODE="sentinel",
            HOST="redis.example.com",
            PORT=6380,
            DB=2,
            PASSWORD="test_pass",
            MAX_CONNECTIONS=200,
            SOCKET_TIMEOUT=30,
            SOCKET_CONNECT_TIMEOUT=25,
            SOCKET_KEEPALIVE=False,
            SENTINEL_NAME="mymaster",
            SENTINEL_HOSTS=[("s1", 26379), ("s2", 26379)],
            SENTINEL_PASSWORD="sentinel_pass",
        )

        assert config.mode == RedisMode.SENTINEL
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 2
        assert config.password == "test_pass"
        assert config.max_connections == 200
        assert config.socket_timeout == 30
        assert config.socket_connect_timeout == 25
        assert config.socket_keepalive is False
        assert config.sentinel_name == "mymaster"
        assert config.sentinel_hosts == [("s1", 26379), ("s2", 26379)]
        assert config.sentinel_password == "sentinel_pass"

    def test_config_with_cluster_alias(self):
        """测试使用别名初始化集群配置"""
        config = RedisConfig(
            MODE="cluster",
            CLUSTER_NODES=[("n1", 6379), ("n2", 6379), ("n3", 6379)],
            PASSWORD="cluster_pass",
        )

        assert config.mode == RedisMode.CLUSTER
        assert config.cluster_nodes == [("n1", 6379), ("n2", 6379), ("n3", 6379)]
        assert config.password == "cluster_pass"


class TestRedisConfigFromEnv:
    """测试从环境变量加载配置"""

    def test_env_config_single_mode(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量配置 - 单机模式"""
        env_dict = {
            "REDIS__DEFAULT__HOST": "env-redis.example.com",
            "REDIS__DEFAULT__PORT": "6380",
            "REDIS__DEFAULT__DB": "2",
            "REDIS__DEFAULT__PASSWORD": "env_password",
            "REDIS__DEFAULT__MAX_CONNECTIONS": "100",
            "REDIS__DEFAULT__SOCKET_TIMEOUT": "20",
            "REDIS__DEFAULT__SOCKET_CONNECT_TIMEOUT": "15",
            "REDIS__DEFAULT__SOCKET_KEEPALIVE": "false",
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        redis_config = config.redis["default"]

        assert redis_config.mode == RedisMode.SINGLE
        assert redis_config.host == "env-redis.example.com"
        assert redis_config.port == 6380
        assert redis_config.db == 2
        assert redis_config.password == "env_password"
        assert redis_config.max_connections == 100
        assert redis_config.socket_timeout == 20
        assert redis_config.socket_connect_timeout == 15
        assert redis_config.socket_keepalive is False

    def test_env_config_sentinel_mode(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量配置 - 哨兵模式"""
        env_dict = {
            "REDIS__DEFAULT__MODE": "sentinel",
            "REDIS__DEFAULT__SENTINEL_NAME": "env_master",
            "REDIS__DEFAULT__SENTINEL_HOSTS": '[["sentinel1", 26379], ["sentinel2", 26379]]',
            "REDIS__DEFAULT__PASSWORD": "master_pass",
            "REDIS__DEFAULT__SENTINEL_PASSWORD": "sentinel_pass",
            "REDIS__DEFAULT__DB": "1",
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        redis_config = config.redis["default"]

        assert redis_config.mode == RedisMode.SENTINEL
        assert redis_config.sentinel_name == "env_master"
        # JSON 解析后是列表，但 pydantic 会转换为元组
        assert redis_config.sentinel_hosts == [("sentinel1", 26379), ("sentinel2", 26379)]
        assert redis_config.password == "master_pass"
        assert redis_config.sentinel_password == "sentinel_pass"
        assert redis_config.db == 1

    def test_env_config_cluster_mode(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量配置 - 集群模式"""
        env_dict = {
            "REDIS__DEFAULT__MODE": "cluster",
            "REDIS__DEFAULT__CLUSTER_NODES": '[["node1", 6379], ["node2", 6379], ["node3", 6379]]',
            "REDIS__DEFAULT__PASSWORD": "cluster_pass",
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        redis_config = config.redis["default"]

        assert redis_config.mode == RedisMode.CLUSTER
        # JSON 解析后是列表，但 pydantic 会转换为元组
        assert redis_config.cluster_nodes == [("node1", 6379), ("node2", 6379), ("node3", 6379)]
        assert redis_config.password == "cluster_pass"


class TestRedisConfigExtras:
    """测试额外配置处理"""

    def test_extra_fields_ignored(self):
        """测试额外字段被忽略"""
        # BaseConfigModel 设置了 extra="ignore"，应该忽略未定义的字段
        config = RedisConfig(
            host="localhost",
            port=6379,
            unknown_field="should_be_ignored",
            another_unknown=123,
        )

        assert config.host == "localhost"
        assert config.port == 6379
        assert not hasattr(config, "unknown_field")
        assert not hasattr(config, "another_unknown")

    def test_connection_kwargs_immutability(self):
        """测试连接参数的独立性"""
        config = RedisConfig(host="localhost", port=6379, db=0, password="test_pass")

        kwargs1 = config.get_connection_kwargs()
        kwargs2 = config.get_connection_kwargs()

        # 修改其中一个不应该影响另一个
        kwargs1["new_key"] = "new_value"
        assert "new_key" not in kwargs2

        # 验证原始配置对象不受影响
        kwargs3 = config.get_connection_kwargs()
        assert "new_key" not in kwargs3
