import pytest

from bk_monitor_base.config import Config, get_env_config, get_yaml_config

from .contants import TEST_ENV_FILE, TEST_YAML_FILE


def test_env_config(monkeypatch: pytest.MonkeyPatch):
    """
    测试环境变量配置
    """
    monkeypatch.setenv("MEDIA_ROOT", "test_env_media")
    monkeypatch.setenv("USE_TZ", "false")
    config = Config()
    assert config.django.media_root == "test_env_media"
    assert config.django.use_tz is False


def test_dotenv_config():
    """
    测试dotenv配置
    """
    dotenv_config = get_env_config(TEST_ENV_FILE)
    dotenv_config.django.media_root = "test_dotenv_media"
    dotenv_config.django.use_tz = True


def test_yaml_config():
    """
    测试YAML配置
    """
    yaml_config = get_yaml_config(TEST_YAML_FILE)
    assert yaml_config.django.media_root == "test_media"
    assert yaml_config.django.use_tz is True


def test_use_old_model_disable_migrations_modules():
    """use_old_model=true 时，不应剔除 app，但应通过 MIGRATION_MODULES 禁用迁移。"""

    config = Config.model_validate(
        {
            "domains": {
                "space": {"use_old_model": True},
                "strategy": {"use_old_model": True},
                "uptime_check": {"use_old_model": False},
            },
            "metadata": {"use_old_model": True},
        }
    )

    # INSTALLED_APPS 不应被修改（否则 ORM 无法正常注册 app）
    assert "bk_monitor_base.domains.space" in config.django.installed_apps
    assert "bk_monitor_base.domains.strategy" in config.django.installed_apps

    # 通过 MIGRATION_MODULES 禁用迁移（key 是 app_label）
    assert config.django.migration_modules["space"] is None
    assert config.django.migration_modules["strategy"] is None
    assert config.django.migration_modules["old_metadata"] is None
    assert "uptime_check" not in config.django.migration_modules
