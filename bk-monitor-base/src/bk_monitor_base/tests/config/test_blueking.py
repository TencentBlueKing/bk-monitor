import pytest

from bk_monitor_base.config import Config
from bk_monitor_base.config.all import get_env_config, get_yaml_config
from bk_monitor_base.config.storage import StorageName

from .contants import TEST_ENV_FILE, TEST_YAML_FILE


def test_blueking_config_default():
    """
    测试默认配置
    """
    default_config = Config()
    assert default_config.blueking.app_code == "bk_monitorv3"
    assert default_config.blueking.app_secret == ""
    assert str(default_config.blueking.api_url) == "http://bkapi.example.com/"


def test_blueking_config_env(monkeypatch: pytest.MonkeyPatch):
    """
    测试环境变量配置
    """
    env_dict = {
        "BK_APP_CODE": "test_env_code",
        "BK_APP_SECRET": "test_env_secret",
        "BK_COMPONENT_API_URL": "http://test-env-url.com/",
    }
    for key, value in env_dict.items():
        monkeypatch.setenv(name=key, value=value)
    default_config = Config()
    assert default_config.blueking.app_code == "test_env_code"
    assert default_config.blueking.app_secret == "test_env_secret"
    assert str(default_config.blueking.api_url) == "http://test-env-url.com/"


def test_blueking_config_env_file():
    """
    测试env文件配置
    """
    dotenv_config = get_env_config(TEST_ENV_FILE)
    assert dotenv_config.blueking.app_code == "test_code"
    assert dotenv_config.blueking.app_secret == "test_secret"
    assert str(dotenv_config.blueking.api_url) == "http://test-url.com/"


def test_blueking_config_yaml_file():
    """
    测试yaml文件配置
    """
    yaml_config = get_yaml_config(TEST_YAML_FILE)
    assert yaml_config.blueking.app_code == "test_code"
    assert yaml_config.blueking.app_secret == "test_secret"
    assert str(yaml_config.blueking.api_url) == "http://test-url.com/"


def test_config_extra_fields_ignored():
    """
    测试配置文件中多余字段被忽略
    确保所有配置类都支持忽略未定义的字段
    """
    from pathlib import Path

    # 创建一个包含多余字段的测试 YAML
    test_yaml_content = """
django:
  MEDIA_ROOT: test/media
  extra_django_field: should_be_ignored
  databases:
    default:
      ENGINE: django.db.backends.sqlite3
      NAME: test.db
      extra_db_field: should_be_ignored
common:
  extra_redis_field: should_be_ignored
  redis_key_prefix: test_prefix
redis:
  default:
    host: localhost
    port: 6379
  kingeye:
    host: kingeye-redis
    port: 6380
elasticsearch:
  default:
    hosts:
      - http://es-default:9200
  kingeye:
    hosts:
      - http://es-kingeye:9200
blueking:
  app_code: test_code
  extra_blueking_field: should_be_ignored
  api_configs:
    cmdb:
      mode: apigw
      extra_api_field: should_be_ignored
domains:
  metric_plugin:
    extra_domain_field: should_be_ignored
encryption:
  rsa_private_key: test_key
  extra_encryption_field: should_be_ignored
file_storages:
  default:
    type: local
    local:
      path: test/path
      extra_local_field: should_be_ignored
    extra_storage_field: should_be_ignored
"""
    # 创建临时 YAML 文件
    temp_yaml_file = Path(__file__).parent / "config.extra_fields.test.yaml"
    temp_yaml_file.write_text(test_yaml_content, encoding="utf-8")

    try:
        # 应该能够成功加载配置，多余字段被忽略
        config = get_yaml_config(temp_yaml_file)
        assert config.django.media_root == "test/media"
        assert config.common.redis_key_prefix == "test_prefix"
        assert config.blueking.app_code == "test_code"
        assert config.encryption.rsa_private_key == "test_key"
        assert config.file_storages[StorageName.DEFAULT].local.path == "test/path"
        assert config.redis["default"].host == "localhost"
        assert config.redis["kingeye"].host == "kingeye-redis"
        assert config.elasticsearch["default"].hosts == ["http://es-default:9200"]
        assert config.elasticsearch["kingeye"].hosts == ["http://es-kingeye:9200"]
    finally:
        # 清理临时文件
        if temp_yaml_file.exists():
            temp_yaml_file.unlink()
