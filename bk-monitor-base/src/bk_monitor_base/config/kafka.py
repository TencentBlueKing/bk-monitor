from typing import Any

from pydantic import Field

from bk_monitor_base.config.base import BaseConfigModel


class KafkaConfig(BaseConfigModel):
    """Kafka 配置"""

    host: str = Field(default="localhost", alias="HOST", description="Kafka 服务器地址，格式: host")
    port: int = Field(default=9092, alias="PORT", description="Kafka 服务器端口")
    security_protocol: str = Field(default="PLAINTEXT", alias="SECURITY_PROTOCOL", description="Kafka 安全协议")
    sasl_mechanism: str = Field(default="PLAIN", alias="SASL_MECHANISM", description="Kafka SASL 机制")
    sasl_plain_username: str = Field(default="", alias="SASL_PLAIN_USERNAME", description="Kafka SASL PLAIN 用户名")
    sasl_plain_password: str = Field(default="", alias="SASL_PLAIN_PASSWORD", description="Kafka SASL PLAIN 密码")
    extra_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        alias="EXTRA_KWARGS",
        description="额外的 Kafka 连接参数，用于传递 kafka-python 支持的其他参数，如 request_timeout_ms、"
        "consumer_timeout_ms、connections_max_idle_ms 等",
    )

    def get_connection_kwargs(self) -> dict[str, Any]:
        """获取 Kafka 连接参数

        将基础连接参数（bootstrap_servers、security_protocol 及 SASL 参数）与
        extra_kwargs 中的额外参数合并后返回。extra_kwargs 在合并时最后应用，
        因此其中的键可以覆盖内置字段（如 security_protocol 等），使用时需注意。

        Returns:
            dict[str, Any]: Kafka 连接参数字典，可直接传入 KafkaProducer / KafkaConsumer。
                包含以下键：
                - bootstrap_servers: "<host>:<port>" 格式的 Kafka 服务器地址
                - security_protocol: 安全协议
                - sasl_mechanism / sasl_plain_username / sasl_plain_password:
                  仅在 SASL_PLAINTEXT 或 SASL_SSL 协议下包含
                - extra_kwargs 中的所有额外键值对（如超时参数等）

        Example:
            >>> config = KafkaConfig(
            ...     host="kafka.example.com",
            ...     port=9092,
            ...     extra_kwargs={"request_timeout_ms": 30000, "consumer_timeout_ms": 5000},
            ... )
            >>> kwargs = config.get_connection_kwargs()
            >>> # kwargs == {
            >>> #     "bootstrap_servers": "kafka.example.com:9092",
            >>> #     "security_protocol": "PLAINTEXT",
            >>> #     "request_timeout_ms": 30000,
            >>> #     "consumer_timeout_ms": 5000,
            >>> # }
        """
        kwargs: dict[str, Any] = {
            "bootstrap_servers": f"{self.host}:{self.port}",
            "security_protocol": self.security_protocol,
        }

        # 仅在使用 SASL 协议时传递 SASL 相关参数，避免在 PLAINTEXT 等协议下产生告警或错误
        if self.security_protocol in {"SASL_PLAINTEXT", "SASL_SSL"}:
            kwargs.update(
                {
                    "sasl_mechanism": self.sasl_mechanism,
                    "sasl_plain_username": self.sasl_plain_username,
                    "sasl_plain_password": self.sasl_plain_password,
                }
            )

        # 合并额外参数，允许用户自定义 kafka-python 支持的连接参数（如超时等）
        kwargs.update(self.extra_kwargs)

        return kwargs
