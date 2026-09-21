"""
Elasticsearch 配置单元测试
"""

import pytest

from bk_monitor_base.config import Config
from bk_monitor_base.config.elasticsearch import ElasticsearchConfig


class TestElasticsearchConfig:
    """测试 Elasticsearch 配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = ElasticsearchConfig()

        # 连接配置
        assert config.hosts == ["http://localhost:9200"]
        assert config.username == ""
        assert config.password == ""
        assert config.verify_certs is True
        assert config.ca_certs == ""

        # 请求配置
        assert config.timeout == 30
        assert config.max_retries == 3

        # 索引配置
        assert config.es_using == "default"
        assert config.max_offset == 50000
        assert config.max_mapping_fields == 1000
        assert config.number_of_shards == 3
        assert config.number_of_replicas == 2

        # 集群嗅探配置
        assert config.sniff_on_start is False
        assert config.sniff_on_connection_fail is False
        assert config.sniffer_timeout == 60

        # 连接池配置
        assert config.maxsize == 10

    def test_custom_config(self):
        """测试自定义配置"""
        config = ElasticsearchConfig(
            hosts=["http://es1.example.com:9200", "http://es2.example.com:9200"],
            username="test_user",
            password="test_password",
            verify_certs=False,
            ca_certs="/path/to/ca.crt",
            timeout=60,
            max_retries=5,
            es_using="custom",
            max_offset=100000,
            max_mapping_fields=2000,
            number_of_shards=5,
            number_of_replicas=1,
            sniff_on_start=True,
            sniff_on_connection_fail=True,
            sniffer_timeout=120,
            maxsize=20,
        )

        assert config.hosts == ["http://es1.example.com:9200", "http://es2.example.com:9200"]
        assert config.username == "test_user"
        assert config.password == "test_password"
        assert config.verify_certs is False
        assert config.ca_certs == "/path/to/ca.crt"
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.es_using == "custom"
        assert config.max_offset == 100000
        assert config.max_mapping_fields == 2000
        assert config.number_of_shards == 5
        assert config.number_of_replicas == 1
        assert config.sniff_on_start is True
        assert config.sniff_on_connection_fail is True
        assert config.sniffer_timeout == 120
        assert config.maxsize == 20

    def test_hosts_validator_string(self):
        """测试 hosts 验证器 - 单个字符串"""
        config = ElasticsearchConfig(hosts="http://single-host.com:9200")
        assert config.hosts == ["http://single-host.com:9200"]

    def test_hosts_validator_comma_separated(self):
        """测试 hosts 验证器 - 逗号分隔的字符串"""
        config = ElasticsearchConfig(hosts="http://host1.com:9200,http://host2.com:9200,http://host3.com:9200")
        assert config.hosts == [
            "http://host1.com:9200",
            "http://host2.com:9200",
            "http://host3.com:9200",
        ]

    def test_hosts_validator_comma_separated_with_spaces(self):
        """测试 hosts 验证器 - 带空格的逗号分隔字符串"""
        config = ElasticsearchConfig(hosts="http://host1.com:9200 , http://host2.com:9200 , http://host3.com:9200")
        assert config.hosts == [
            "http://host1.com:9200",
            "http://host2.com:9200",
            "http://host3.com:9200",
        ]

    def test_hosts_validator_list(self):
        """测试 hosts 验证器 - 列表"""
        hosts_list = ["http://host1.com:9200", "http://host2.com:9200"]
        config = ElasticsearchConfig(hosts=hosts_list)
        assert config.hosts == hosts_list

    def test_hosts_validator_invalid_type(self):
        """测试 hosts 验证器 - 无效类型"""
        with pytest.raises(ValueError, match="hosts must be a string or list"):
            ElasticsearchConfig(hosts=123)

    def test_get_connection_kwargs_basic(self):
        """测试获取基本连接参数"""
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            timeout=45,
            max_retries=2,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["hosts"] == ["http://localhost:9200"]
        assert kwargs["timeout"] == 45
        assert kwargs["max_retries"] == 2
        assert kwargs["sniff_on_start"] is False
        assert kwargs["sniff_on_connection_fail"] is False
        assert kwargs["sniffer_timeout"] == 60
        assert kwargs["maxsize"] == 10
        assert kwargs["verify_certs"] is True
        assert "http_auth" not in kwargs
        assert "ca_certs" not in kwargs

    def test_get_connection_kwargs_with_auth(self):
        """测试获取带认证的连接参数"""
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            username="admin",
            password="secret123",
        )

        kwargs = config.get_connection_kwargs()

        assert "http_auth" in kwargs
        assert kwargs["http_auth"] == ("admin", "secret123")

    def test_get_connection_kwargs_without_auth(self):
        """测试获取不带认证的连接参数"""
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            username="",
            password="",
        )

        kwargs = config.get_connection_kwargs()

        assert "http_auth" not in kwargs

    def test_get_connection_kwargs_partial_auth(self):
        """测试获取部分认证信息的连接参数"""
        # 只有用户名，没有密码
        config1 = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            username="admin",
            password="",
        )
        kwargs1 = config1.get_connection_kwargs()
        assert "http_auth" not in kwargs1

        # 只有密码，没有用户名
        config2 = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            username="",
            password="secret",
        )
        kwargs2 = config2.get_connection_kwargs()
        assert "http_auth" not in kwargs2

    def test_get_connection_kwargs_with_ca_certs(self):
        """测试获取带 CA 证书的连接参数"""
        config = ElasticsearchConfig(
            hosts=["https://secure-es.com:9200"],
            ca_certs="/path/to/ca-bundle.crt",
        )

        kwargs = config.get_connection_kwargs()

        assert "ca_certs" in kwargs
        assert kwargs["ca_certs"] == "/path/to/ca-bundle.crt"

    def test_get_connection_kwargs_without_ca_certs(self):
        """测试获取不带 CA 证书的连接参数"""
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            ca_certs="",
        )

        kwargs = config.get_connection_kwargs()

        assert "ca_certs" not in kwargs

    def test_get_connection_kwargs_full(self):
        """测试获取完整配置的连接参数"""
        config = ElasticsearchConfig(
            hosts=["http://es1.com:9200", "http://es2.com:9200"],
            username="admin",
            password="secret",
            verify_certs=False,
            ca_certs="/etc/ssl/ca.crt",
            timeout=120,
            max_retries=10,
            sniff_on_start=True,
            sniff_on_connection_fail=True,
            sniffer_timeout=180,
            maxsize=50,
        )

        kwargs = config.get_connection_kwargs()

        assert kwargs["hosts"] == ["http://es1.com:9200", "http://es2.com:9200"]
        assert kwargs["timeout"] == 120
        assert kwargs["max_retries"] == 10
        assert kwargs["sniff_on_start"] is True
        assert kwargs["sniff_on_connection_fail"] is True
        assert kwargs["sniffer_timeout"] == 180
        assert kwargs["maxsize"] == 50
        assert kwargs["verify_certs"] is False
        assert kwargs["http_auth"] == ("admin", "secret")
        assert kwargs["ca_certs"] == "/etc/ssl/ca.crt"

    def test_env_config(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量配置"""
        env_dict = {
            "ELASTICSEARCH__DEFAULT__HOSTS": "http://env-es1.com:9200,http://env-es2.com:9200",
            "ELASTICSEARCH__DEFAULT__USERNAME": "env_user",
            "ELASTICSEARCH__DEFAULT__PASSWORD": "env_pass",
            "ELASTICSEARCH__DEFAULT__TIMEOUT": "90",
            "ELASTICSEARCH__DEFAULT__NUMBER_OF_SHARDS": "5",
        }
        for key, value in env_dict.items():
            monkeypatch.setenv(name=key, value=value)

        config = Config()
        es_config = config.elasticsearch["default"]

        assert es_config.hosts == ["http://env-es1.com:9200", "http://env-es2.com:9200"]
        assert es_config.username == "env_user"
        assert es_config.password == "env_pass"
        assert es_config.timeout == 90
        assert es_config.number_of_shards == 5

    def test_field_aliases(self):
        """测试字段别名"""
        # 使用别名创建配置
        config = ElasticsearchConfig(
            HOSTS=["http://alias-test.com:9200"],
            USERNAME="alias_user",
            PASSWORD="alias_pass",
            VERIFY_CERTS=False,
            CA_CERTS="/alias/ca.crt",
            TIMEOUT=75,
            MAX_RETRIES=7,
            ES_USING="alias_connection",
            ES_MAX_OFFSET=75000,
            ES_MAX_MAPPING_FIELDS=1500,
            NUMBER_OF_SHARDS=4,
            NUMBER_OF_REPLICAS=3,
            SNIFF_ON_START=True,
            SNIFF_ON_CONNECTION_FAIL=True,
            SNIFFER_TIMEOUT=90,
            MAXSIZE=25,
        )

        assert config.hosts == ["http://alias-test.com:9200"]
        assert config.username == "alias_user"
        assert config.password == "alias_pass"
        assert config.verify_certs is False
        assert config.ca_certs == "/alias/ca.crt"
        assert config.timeout == 75
        assert config.max_retries == 7
        assert config.es_using == "alias_connection"
        assert config.max_offset == 75000
        assert config.max_mapping_fields == 1500
        assert config.number_of_shards == 4
        assert config.number_of_replicas == 3
        assert config.sniff_on_start is True
        assert config.sniff_on_connection_fail is True
        assert config.sniffer_timeout == 90
        assert config.maxsize == 25

    def test_extra_fields_ignored(self):
        """测试额外字段被忽略"""
        # BaseConfigModel 设置了 extra="ignore"，应该忽略未定义的字段
        config = ElasticsearchConfig(
            hosts=["http://localhost:9200"],
            unknown_field="should_be_ignored",
            another_unknown=123,
        )

        assert config.hosts == ["http://localhost:9200"]
        assert not hasattr(config, "unknown_field")
        assert not hasattr(config, "another_unknown")

    def test_connection_kwargs_immutability(self):
        """测试连接参数的独立性"""
        config = ElasticsearchConfig(hosts=["http://localhost:9200"])

        # 获取两次连接参数
        kwargs1 = config.get_connection_kwargs()
        kwargs2 = config.get_connection_kwargs()

        # 修改第一个不应该影响第二个
        kwargs1["timeout"] = 999

        assert kwargs2["timeout"] == 30  # 应该还是默认值
        assert kwargs1 is not kwargs2  # 应该是不同的对象
