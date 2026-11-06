"""
Redis 配置
"""

from enum import Enum
from typing import Any

from pydantic import Field

from .base import BaseConfigModel


class RedisMode(str, Enum):
    """Redis 模式"""

    SINGLE = "single"
    SENTINEL = "sentinel"
    CLUSTER = "cluster"


class RedisConfig(BaseConfigModel):
    """Redis 配置"""

    # 连接配置
    mode: RedisMode = Field(default=RedisMode.SINGLE, alias="MODE", description="Redis 模式")
    host: str = Field(default="localhost", alias="HOST", description="主机地址")
    port: int = Field(default=6379, alias="PORT", description="端口")
    db: int = Field(default=0, alias="DB", description="数据库索引")
    password: str = Field(default="", alias="PASSWORD", description="密码（单机模式/主节点密码）")

    # 连接池配置
    max_connections: int = Field(default=50, alias="MAX_CONNECTIONS", description="最大连接数")
    socket_timeout: int = Field(default=10, alias="SOCKET_TIMEOUT", description="套接字超时时间（秒）")
    socket_connect_timeout: int = Field(default=10, alias="SOCKET_CONNECT_TIMEOUT", description="连接超时时间（秒）")
    socket_keepalive: bool = Field(default=True, alias="SOCKET_KEEPALIVE", description="是否启用 TCP keepalive")

    # Sentinel 模式配置
    sentinel_name: str = Field(default="", alias="SENTINEL_NAME", description="Sentinel 服务名称")
    sentinel_hosts: list[tuple[str, int]] = Field(
        default_factory=list, alias="SENTINEL_HOSTS", description="Sentinel 主机列表，格式: [(host, port), ...]"
    )
    sentinel_password: str = Field(
        default="", alias="SENTINEL_PASSWORD", description="Sentinel 节点密码（如果为空则使用 password 字段）"
    )

    # Cluster 模式配置
    cluster_nodes: list[tuple[str, int]] = Field(
        default_factory=list, alias="CLUSTER_NODES", description="集群节点列表，格式: [(host, port), ...]"
    )

    def get_connection_kwargs(self) -> dict[str, Any]:
        """获取连接参数

        Returns:
            dict: Redis 连接参数字典

        Example:
            >>> # 单机模式
            >>> config = RedisConfig(host="localhost", port=6379, db=0)
            >>> kwargs = config.get_connection_kwargs()
            >>> import redis
            >>> client = redis.Redis(**kwargs)

            >>> # 哨兵模式（主节点和哨兵使用不同密码）
            >>> config = RedisConfig(
            ...     mode=RedisMode.SENTINEL,
            ...     sentinel_name="mymaster",
            ...     sentinel_hosts=[("sentinel1", 26379), ("sentinel2", 26379)],
            ...     password="master_password",
            ...     sentinel_password="sentinel_password"
            ... )
            >>> kwargs = config.get_connection_kwargs()
        """
        kwargs: dict[str, Any] = {
            "db": self.db,
            "password": self.password if self.password else None,
            "max_connections": self.max_connections,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_connect_timeout,
            "socket_keepalive": self.socket_keepalive,
        }

        if self.mode == RedisMode.SINGLE:
            kwargs.update({"host": self.host, "port": self.port})
        elif self.mode == RedisMode.SENTINEL:
            sentinel_kwargs: dict[str, Any] = {
                "sentinel_name": self.sentinel_name,
                "sentinels": self.sentinel_hosts,
            }
            # 如果设置了 sentinel_password，则单独配置哨兵密码
            # 否则使用主节点密码（password 字段）
            if self.sentinel_password:
                sentinel_kwargs["sentinel_kwargs"] = {"password": self.sentinel_password}
            kwargs.update(sentinel_kwargs)
        elif self.mode == RedisMode.CLUSTER:
            kwargs.update({"startup_nodes": self.cluster_nodes})

        # 移除值为 None 的键
        return {k: v for k, v in kwargs.items() if v is not None}
