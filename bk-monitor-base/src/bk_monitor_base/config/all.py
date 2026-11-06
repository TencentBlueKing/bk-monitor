"""
配置
"""

import os
from pathlib import Path
from typing import ClassVar

import yaml
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from typing_extensions import override

from bk_monitor_base.config.kafka import KafkaConfig

from .base import BaseConfigModel, BaseConfigSettings
from .blueking import BlueKingConfig
from .django import DjangoConfig
from .domains import DomainsConfig
from .elasticsearch import ElasticsearchConfig
from .metadata import MetadataConfig
from .redis import RedisConfig
from .storage import StorageConfig, StorageName

DEFAULT_YAML_FILE = Path(os.getenv("BK_MONITOR_BASE_CONFIG_YAML_FILE", "config.yaml")).expanduser()
DEFAULT_ENV_FILE = Path(".env")


class EncryptionConfig(BaseConfigSettings):
    """加密配置类"""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(validate_by_name=True, extra="ignore")

    rsa_private_key: str = Field(
        default="",
        description="RSA私钥，用于加密敏感参数",
        validation_alias=AliasChoices("rsa_private_key", "RSA_PRIVATE_KEY"),
    )

    aes_secret_key: str = Field(
        default="",
        description="AES加密密钥，用于加密敏感参数",
        validation_alias=AliasChoices("aes_secret_key", "AES_SECRET_KEY"),
    )


# 公共功能配置
class CommonConfig(BaseConfigModel):
    """
    公共功能配置
    """

    ipv6_support_biz_list: list[int] = Field(description="IPv6支持的业务列表", default_factory=list)
    enable_base_compatible_switch: bool = Field(
        default=False,
        description="Base 模块调用开关，True: 使用新的 Base 模块调用，False: 使用旧的方法调用",
    )
    enable_base_metadata: bool = Field(default=False, description="Base METADATA模块开关", alias="ENABLE_BASE_METADATA")
    redis_key_prefix: str = Field(default="bk_monitor_base:", description="Redis 键前缀，用于区分不同项目的 Redis 键")
    es_index_prefix: str = Field(default="bk_monitor_base_", description="Elasticsearch 索引前缀")
    default_source_system: str = Field(default="unknown", description="默认的来源系统标识")

    # 对象模型使用记录常量
    usage_record_meta_app_id: str = Field(default="meta_saas", description="元数据中心应用ID")
    usage_record_meta_app_name: str = Field(default="鲸眼元数据中心", description="元数据中心应用名称")
    usage_record_dynamic_group_module_id: str = Field(default="meta_dynamic_group", description="动态分组模块ID")
    usage_record_dynamic_group_module_name: str = Field(default="动态分组", description="动态分组模块名称")


class Config(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        validate_by_name=True,
    )
    django: DjangoConfig = Field(default_factory=DjangoConfig)
    redis: dict[str, RedisConfig] = Field(
        default_factory=lambda: {"default": RedisConfig()},
        title="Redis 配置",
        description="支持配置多个 Redis 实例，通过字典键名区分",
    )
    kafka: dict[str, KafkaConfig] = Field(
        default_factory=lambda: {"default": KafkaConfig()},
        title="Kafka 配置",
        description="支持配置多个 Kafka 集群，通过字典键名区分",
    )

    blueking: BlueKingConfig = Field(default_factory=BlueKingConfig)
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    domains: DomainsConfig = Field(default_factory=DomainsConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    file_storages: dict[StorageName, StorageConfig] = Field(
        default_factory=lambda: {StorageName.DEFAULT: StorageConfig()}, title="存储配置"
    )
    common: CommonConfig = Field(default_factory=CommonConfig)
    elasticsearch: dict[str, ElasticsearchConfig] = Field(
        default_factory=lambda: {"default": ElasticsearchConfig()},
        title="Elasticsearch 配置",
        description="支持配置多个 Elasticsearch 集群，通过字典键名区分",
    )

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _apply_domain_old_model_installed_apps(self) -> "Config":
        """根据 use_old_model 配置，自动禁用对应 app 的 migrations。

        约定：
        - 遍历 `domains` 下的所有子配置对象；
        - 若其存在 `use_old_model` 字段且为 True，则设置 `MIGRATION_MODULES[<app_label>] = None`，
          以避免执行该 app 的迁移。

        说明：
        - 该逻辑只在 Config 初始化阶段生效（Django setup 之前）。
        - 不会修改 `INSTALLED_APPS`，避免 ORM 因 app 未注册而不可用。
        """

        domains_data = self.domains.model_dump()
        migration_modules_to_disable: dict[str, None] = {}
        for domain_name, domain_config in domains_data.items():
            if isinstance(domain_config, dict) and domain_config.get("use_old_model") is True:
                # app_label 默认为最后一段：bk_monitor_base.domains.<domain_name> -> <domain_name>
                migration_modules_to_disable[str(domain_name)] = None

        if self.metadata.use_old_model:
            migration_modules_to_disable["old_metadata"] = None

        if not migration_modules_to_disable:
            return self

        # 合并到 DjangoConfig.migration_modules，其他手工配置保持不变
        merged = dict(self.django.migration_modules)
        merged.update(migration_modules_to_disable)
        self.django.migration_modules = merged

        return self


_config: Config | None = None


def get_config() -> Config:
    """
    获取配置
    """
    global _config
    if _config:
        return _config

    if DEFAULT_YAML_FILE.exists():
        _config = get_yaml_config(DEFAULT_YAML_FILE)
    elif DEFAULT_ENV_FILE.exists():
        _config = get_env_config(DEFAULT_ENV_FILE)
    else:
        # Fallback: create a Config instance that reads from environment variables.
        _config = Config()

    return _config


def set_config(config: Config) -> None:
    """
    设置配置
    """
    global _config
    _config = config


def get_yaml_config(yaml_file_path: Path | str) -> Config:
    """
    获取yaml配置
    """
    data = yaml.safe_load(Path(yaml_file_path).read_text(encoding="utf-8"))
    return Config(**data)


def get_env_config(dotenv_file_path: Path | str) -> Config:
    """
    获取dotenv配置
    """
    return Config(_env_file=dotenv_file_path)  # pyright: ignore[reportCallIssue]
