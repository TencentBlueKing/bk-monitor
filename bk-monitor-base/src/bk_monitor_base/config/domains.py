from pydantic import AliasChoices, Field

from .base import BaseConfigModel


class BkRepoConfig(BaseConfigModel):
    """蓝鲸仓库相关配置"""

    bucket: str = Field(default="bkmonitor", title="存储桶")
    project: str = Field(default="blueking", title="项目代码")
    url: str = Field(default="http://bkrepo.example.com/", title="仓库地址")
    username: str = Field(default="bkmonitor", title="用户名")
    password: str = Field(default="bkmonitor", title="密码")


class MetricPluginConfig(BaseConfigModel):
    """指标插件相关配置"""

    old_plugin_file_repo: BkRepoConfig | None = Field(default=None, title="旧指标插件文件仓库配置")
    translate_snmp_trap_dimensions: bool = Field(
        default=False,
        alias="TRANSLATE_SNMP_TRAP_DIMENSIONS",
        title="是否翻译SNMP TRAP的oid维度",
        description="是否翻译SNMP TRAP的oid维度",
    )


class SpaceConfig(BaseConfigModel):
    """空间相关配置"""

    use_old_model: bool = Field(
        default=True,
        title="是否使用旧模型",
        validation_alias=AliasChoices("use_old_model", "use_old_space_model"),
    )
    space_cache_size: int = Field(default=2000, title="空间缓存大小")
    global_space_id: int = Field(default=1, title="全局空间ID")


class StrategyConfig(BaseConfigModel):
    """策略相关配置"""

    use_old_model: bool = Field(
        default=True,
        title="是否使用旧模型",
        validation_alias=AliasChoices("use_old_model", "use_old_strategy_model"),
    )


class UptimeCheckConfig(BaseConfigModel):
    """拨测相关配置"""

    use_old_model: bool = Field(
        default=True,
        title="是否使用旧模型",
        validation_alias=AliasChoices("use_old_model", "use_old_uptime_check_model"),
    )
    base64_encode_trigger_chars: list[str] = Field(
        default=[],
        title="Base64编码触发字符",
    )


class DomainsConfig(BaseConfigModel):
    """各领域相关配置"""

    metric_plugin: MetricPluginConfig = Field(default_factory=MetricPluginConfig, title="指标插件配置")
    space: SpaceConfig = Field(default_factory=SpaceConfig, title="空间配置")
    strategy: StrategyConfig = Field(default_factory=StrategyConfig, title="策略配置")
    uptime_check: UptimeCheckConfig = Field(default_factory=UptimeCheckConfig, title="拨测配置")
