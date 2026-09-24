"""
Elasticsearch 配置
"""

from typing import Any

from pydantic import Field, field_validator

from .base import BaseConfigModel


class ElasticsearchConfig(BaseConfigModel):
    """Elasticsearch 配置类。

    该类用于管理 Elasticsearch 的连接配置和索引配置，支持通过环境变量覆盖默认值。

    Attributes:
        hosts: ES 主机列表，支持多节点配置
        username: 认证用户名
        password: 认证密码
        verify_certs: 是否验证 SSL 证书
        ca_certs: CA 证书路径
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
        es_index_prefix: ES 索引前缀，用于区分不同环境的索引
        es_using: ES 连接别名，用于指定使用的 ES 连接
        max_offset: ES 分页查询的最大偏移量，防止深度分页
        max_mapping_fields: ES 索引映射字段数上限
        number_of_shards: ES 索引分片数，影响数据分布和查询性能
        number_of_replicas: ES 索引副本数，影响数据可靠性和查询性能
        sniff_on_start: 启动时是否嗅探集群节点
        sniff_on_connection_fail: 连接失败时是否嗅探
        sniffer_timeout: 嗅探超时时间
        maxsize: 连接池最大连接数

    Example:
        >>> from bk_monitor_base.config import get_config
        >>> config = get_config()
        >>> es_config = config.elasticsearch["default"]
        >>> print(es_config.hosts)
        ['http://localhost:9200']
    """

    # 连接配置
    hosts: list[str] = Field(
        default_factory=lambda: ["http://localhost:9200"],
        alias="HOSTS",
        description="ES 主机列表，支持多节点配置",
    )
    username: str = Field(default="", alias="USERNAME", description="认证用户名")
    password: str = Field(default="", alias="PASSWORD", description="认证密码")
    verify_certs: bool = Field(default=True, alias="VERIFY_CERTS", description="是否验证 SSL 证书")
    ca_certs: str = Field(default="", alias="CA_CERTS", description="CA 证书路径")

    # 请求配置
    timeout: int = Field(default=30, alias="TIMEOUT", description="请求超时时间（秒）")
    max_retries: int = Field(default=3, alias="MAX_RETRIES", description="最大重试次数")

    es_using: str = Field(default="default", alias="ES_USING", description="ES 连接别名，用于指定使用的 ES 连接")
    max_offset: int = Field(default=50000, alias="ES_MAX_OFFSET", description="ES 分页查询的最大偏移量，防止深度分页")
    max_mapping_fields: int = Field(default=1000, alias="ES_MAX_MAPPING_FIELDS", description="ES 索引映射字段数上限")
    number_of_shards: int = Field(
        default=3, alias="NUMBER_OF_SHARDS", description="ES 索引分片数，影响数据分布和查询性能"
    )
    number_of_replicas: int = Field(
        default=2, alias="NUMBER_OF_REPLICAS", description="ES 索引副本数，影响数据可靠性和查询性能"
    )

    # 集群嗅探配置
    sniff_on_start: bool = Field(default=False, alias="SNIFF_ON_START", description="启动时是否嗅探集群节点")
    sniff_on_connection_fail: bool = Field(
        default=False, alias="SNIFF_ON_CONNECTION_FAIL", description="连接失败时是否嗅探"
    )
    sniffer_timeout: int = Field(default=60, alias="SNIFFER_TIMEOUT", description="嗅探超时时间（秒）")

    # 连接池配置
    maxsize: int = Field(default=10, alias="MAXSIZE", description="连接池最大连接数")

    @field_validator("hosts", mode="before")
    @classmethod
    def validate_hosts(cls, v: Any) -> list[str]:
        """验证并转换 hosts 字段

        支持以下输入格式：
        - 字符串: "http://localhost:9200" -> ["http://localhost:9200"]
        - 列表: ["http://host1:9200", "http://host2:9200"]
        - 逗号分隔的字符串: "http://host1:9200,http://host2:9200"
        """
        # 统一处理空值
        if not v:
            raise ValueError("hosts cannot be empty")

        if isinstance(v, str):
            # 处理逗号分隔的字符串
            if "," in v:
                hosts = [host.strip() for host in v.split(",") if host.strip()]
                if not hosts:
                    raise ValueError("hosts string cannot be empty")
                return hosts

            # 处理单个字符串
            host = v.strip()
            if not host:
                raise ValueError("hosts string cannot be empty")
            return [host]

        if isinstance(v, list):
            # 过滤空字符串并检查
            hosts = [h for h in v if h and (isinstance(h, str) and h.strip())]  # pyright: ignore[reportUnknownVariableType]

            if not hosts:
                raise ValueError("hosts list cannot be empty")

            return hosts

        raise ValueError(f"hosts must be a string or list, got {type(v)}")

    def get_connection_kwargs(self) -> dict[str, Any]:
        """获取连接参数

        Returns:
            dict: Elasticsearch 连接参数字典

        Example:
            >>> config = ElasticsearchConfig(hosts=["http://localhost:9200"])
            >>> kwargs = config.get_connection_kwargs()
            >>> from elasticsearch import Elasticsearch
            >>> client = Elasticsearch(**kwargs)
        """
        kwargs: dict[str, Any] = {
            "hosts": self.hosts,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "sniff_on_start": self.sniff_on_start,
            "sniff_on_connection_fail": self.sniff_on_connection_fail,
            "sniffer_timeout": self.sniffer_timeout,
            "maxsize": self.maxsize,
            "verify_certs": self.verify_certs,
        }

        # 添加认证信息
        if self.username and self.password:
            kwargs["http_auth"] = (self.username, self.password)

        # 添加 CA 证书路径
        if self.ca_certs:
            kwargs["ca_certs"] = self.ca_certs

        return kwargs
