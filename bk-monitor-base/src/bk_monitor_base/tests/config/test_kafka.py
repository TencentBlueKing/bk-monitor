"""
Kafka 配置单元测试
"""

import pytest

from bk_monitor_base.config import Config
from bk_monitor_base.config.kafka import KafkaConfig


class TestKafkaConfig:
    """测试 KafkaConfig 配置类"""

    def test_default_config(self):
        """测试默认配置值"""
        config = KafkaConfig()

        assert config.host == "localhost"
        assert config.port == 9092
        assert config.security_protocol == "PLAINTEXT"
        assert config.sasl_mechanism == "PLAIN"
        assert config.sasl_plain_username == ""
        assert config.sasl_plain_password == ""
        assert config.extra_kwargs == {}

    def test_custom_config(self):
        """测试自定义配置"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9093,
            security_protocol="SASL_PLAINTEXT",
            sasl_mechanism="PLAIN",
            sasl_plain_username="user",
            sasl_plain_password="pass",
        )

        assert config.host == "kafka.example.com"
        assert config.port == 9093
        assert config.security_protocol == "SASL_PLAINTEXT"
        assert config.sasl_mechanism == "PLAIN"
        assert config.sasl_plain_username == "user"
        assert config.sasl_plain_password == "pass"

    def test_extra_kwargs_default_empty(self):
        """测试 extra_kwargs 默认为空字典"""
        config = KafkaConfig()
        assert config.extra_kwargs == {}

    def test_extra_kwargs_with_timeout_params(self):
        """测试 extra_kwargs 支持超时参数"""
        config = KafkaConfig(
            host="kafka.example.com",
            extra_kwargs={
                "request_timeout_ms": 30000,
                "consumer_timeout_ms": 5000,
                "connections_max_idle_ms": 600000,
            },
        )

        assert config.extra_kwargs["request_timeout_ms"] == 30000
        assert config.extra_kwargs["consumer_timeout_ms"] == 5000
        assert config.extra_kwargs["connections_max_idle_ms"] == 600000

    def test_config_with_alias(self):
        """测试通过别名初始化配置"""
        config = KafkaConfig(
            HOST="kafka.example.com",
            PORT=9094,
            SECURITY_PROTOCOL="SASL_SSL",
            SASL_MECHANISM="PLAIN",
            SASL_PLAIN_USERNAME="admin",
            SASL_PLAIN_PASSWORD="secret",
            EXTRA_KWARGS={"request_timeout_ms": 10000},
        )

        assert config.host == "kafka.example.com"
        assert config.port == 9094
        assert config.security_protocol == "SASL_SSL"
        assert config.extra_kwargs == {"request_timeout_ms": 10000}


class TestKafkaConnectionKwargs:
    """测试 get_connection_kwargs 方法"""

    def test_plaintext_connection_kwargs(self):
        """测试 PLAINTEXT 协议连接参数，不应包含 SASL 相关参数"""
        config = KafkaConfig(host="kafka.example.com", port=9092, security_protocol="PLAINTEXT")

        kwargs = config.get_connection_kwargs()

        assert kwargs["bootstrap_servers"] == "kafka.example.com:9092"
        assert kwargs["security_protocol"] == "PLAINTEXT"
        # PLAINTEXT 协议不应包含 SASL 相关参数
        assert "sasl_mechanism" not in kwargs
        assert "sasl_plain_username" not in kwargs
        assert "sasl_plain_password" not in kwargs

    def test_sasl_plaintext_connection_kwargs(self):
        """测试 SASL_PLAINTEXT 协议连接参数，应包含 SASL 相关参数"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9092,
            security_protocol="SASL_PLAINTEXT",
            sasl_mechanism="PLAIN",
            sasl_plain_username="user",
            sasl_plain_password="pass",
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["bootstrap_servers"] == "kafka.example.com:9092"
        assert kwargs["security_protocol"] == "SASL_PLAINTEXT"
        assert kwargs["sasl_mechanism"] == "PLAIN"
        assert kwargs["sasl_plain_username"] == "user"
        assert kwargs["sasl_plain_password"] == "pass"

    def test_sasl_ssl_connection_kwargs(self):
        """测试 SASL_SSL 协议连接参数，应包含 SASL 相关参数"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9093,
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_plain_username="ssl_user",
            sasl_plain_password="ssl_pass",
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["bootstrap_servers"] == "kafka.example.com:9093"
        assert kwargs["security_protocol"] == "SASL_SSL"
        assert kwargs["sasl_mechanism"] == "PLAIN"
        assert kwargs["sasl_plain_username"] == "ssl_user"
        assert kwargs["sasl_plain_password"] == "ssl_pass"

    def test_extra_kwargs_merged_into_connection_kwargs(self):
        """测试 extra_kwargs 被合并到连接参数中"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9092,
            extra_kwargs={
                "request_timeout_ms": 30000,
                "consumer_timeout_ms": 5000,
            },
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["bootstrap_servers"] == "kafka.example.com:9092"
        assert kwargs["request_timeout_ms"] == 30000
        assert kwargs["consumer_timeout_ms"] == 5000

    def test_extra_kwargs_with_sasl_protocol(self):
        """测试 SASL 协议下 extra_kwargs 与 SASL 参数共存"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9092,
            security_protocol="SASL_PLAINTEXT",
            sasl_mechanism="PLAIN",
            sasl_plain_username="user",
            sasl_plain_password="pass",
            extra_kwargs={
                "request_timeout_ms": 30000,
                "connections_max_idle_ms": 600000,
            },
        )

        kwargs = config.get_connection_kwargs()

        # 基础连接参数
        assert kwargs["bootstrap_servers"] == "kafka.example.com:9092"
        assert kwargs["security_protocol"] == "SASL_PLAINTEXT"
        # SASL 参数
        assert kwargs["sasl_mechanism"] == "PLAIN"
        assert kwargs["sasl_plain_username"] == "user"
        assert kwargs["sasl_plain_password"] == "pass"
        # 额外参数
        assert kwargs["request_timeout_ms"] == 30000
        assert kwargs["connections_max_idle_ms"] == 600000

    def test_extra_kwargs_can_override_defaults(self):
        """测试 extra_kwargs 可以覆盖内置参数（last write wins 语义）

        extra_kwargs 在合并时最后应用，因此可以覆盖内置字段。
        这是有意设计的行为，但使用时需谨慎，建议优先通过专用字段（如 security_protocol）配置。
        """
        config = KafkaConfig(
            host="kafka.example.com",
            port=9092,
            security_protocol="PLAINTEXT",
            extra_kwargs={"security_protocol": "SSL"},
        )

        kwargs = config.get_connection_kwargs()

        # extra_kwargs 覆盖了默认的 security_protocol
        assert kwargs["security_protocol"] == "SSL"

    def test_empty_extra_kwargs_no_side_effect(self):
        """测试空 extra_kwargs 不影响连接参数"""
        config_with_empty = KafkaConfig(host="kafka.example.com", port=9092, extra_kwargs={})
        config_default = KafkaConfig(host="kafka.example.com", port=9092)

        kwargs_with_empty = config_with_empty.get_connection_kwargs()
        kwargs_default = config_default.get_connection_kwargs()

        assert kwargs_with_empty == kwargs_default

    def test_connection_kwargs_immutability(self):
        """测试多次调用 get_connection_kwargs 返回独立副本"""
        config = KafkaConfig(
            host="kafka.example.com",
            port=9092,
            extra_kwargs={"request_timeout_ms": 30000},
        )

        kwargs1 = config.get_connection_kwargs()
        kwargs2 = config.get_connection_kwargs()

        # 修改其中一个不应该影响另一个
        kwargs1["new_key"] = "new_value"
        assert "new_key" not in kwargs2

        # 验证原始配置对象不受影响
        kwargs3 = config.get_connection_kwargs()
        assert "new_key" not in kwargs3


class TestKafkaConfigFromEnv:
    """测试从环境变量加载 Kafka 配置"""

    def test_env_config_basic(self, monkeypatch: pytest.MonkeyPatch):
        """测试从环境变量加载基础 Kafka 配置"""
        env_dict = {
            "KAFKA__DEFAULT__HOST": "env-kafka.example.com",
            "KAFKA__DEFAULT__PORT": "9093",
            "KAFKA__DEFAULT__SECURITY_PROTOCOL": "SASL_PLAINTEXT",
            "KAFKA__DEFAULT__SASL_MECHANISM": "PLAIN",
            "KAFKA__DEFAULT__SASL_PLAIN_USERNAME": "env_user",
            "KAFKA__DEFAULT__SASL_PLAIN_PASSWORD": "env_pass",
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        kafka_config = config.kafka["default"]

        assert kafka_config.host == "env-kafka.example.com"
        assert kafka_config.port == 9093
        assert kafka_config.security_protocol == "SASL_PLAINTEXT"
        assert kafka_config.sasl_plain_username == "env_user"
        assert kafka_config.sasl_plain_password == "env_pass"

    def test_env_config_extra_kwargs(self, monkeypatch: pytest.MonkeyPatch):
        """测试从环境变量加载额外 Kafka 参数"""
        env_dict = {
            "KAFKA__DEFAULT__HOST": "env-kafka.example.com",
            "KAFKA__DEFAULT__EXTRA_KWARGS": '{"request_timeout_ms": 30000, "consumer_timeout_ms": 5000}',
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        kafka_config = config.kafka["default"]

        assert kafka_config.extra_kwargs["request_timeout_ms"] == 30000
        assert kafka_config.extra_kwargs["consumer_timeout_ms"] == 5000

        kwargs = kafka_config.get_connection_kwargs()
        assert kwargs["request_timeout_ms"] == 30000
        assert kwargs["consumer_timeout_ms"] == 5000
