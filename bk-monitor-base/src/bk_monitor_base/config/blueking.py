"""
蓝鲸配置
"""

from typing import ClassVar, Literal, Self

from pydantic import AliasChoices, ConfigDict, Field, HttpUrl
from pydantic.functional_validators import model_validator
from pydantic_settings import SettingsConfigDict

from .base import BaseConfigModel, BaseConfigSettings


class BkApiModuleConfig(BaseConfigModel):
    """
    蓝鲸API模块配置
    """

    custom_api_url: HttpUrl | None = Field(default=None, description="自定义API地址")
    mode: Literal["esb", "apigw"] | None = Field(default=None, description="调用模式，支持 esb 或 apigw")


class BkGseConfig(BaseConfigModel):
    """
    GSE配置
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_by_name=True, extra="ignore")

    gse_path_variable_linux: str = Field(
        description="GSE路径变量", alias="BK_GSE_PATH_VARIABLE_LINUX", default="/usr/local/gse"
    )
    gse_path_variable_windows: str = Field(
        description="GSE路径变量", alias="BK_GSE_PATH_VARIABLE_WINDOWS", default=r"C:\gse"
    )


class BkUnifyQueryRoutingRule(BaseConfigModel):
    """
    统一查询路由规则
    """

    space_type: str | list[str] | None = Field(title="空间类型", default=None)
    space_id: str | list[str | int] | int | None = Field(title="空间ID", default=None)
    space_uid: str | list[str] | None = Field(title="空间UID", default=None)
    url: HttpUrl = Field(title="URL")

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_by_name=True, extra="ignore")

    @model_validator(mode="after")
    def validate_space(self) -> Self:
        if not self.space_uid and not self.space_type and not self.space_id:
            raise ValueError("至少需要提供一个空间类型、空间ID或空间UID")
        return self


class BkUnifyQueryConfig(BaseConfigModel):
    """
    统一查询配置
    """

    default_url: HttpUrl = Field(default=HttpUrl("http://bkapi.example.com/"), title="默认URL")
    routing_rules: list[BkUnifyQueryRoutingRule] = Field(
        default_factory=list,
        title="路由规则",
        description="路由规则，用于根据空间匹配URL",
        examples=[
            {"space_type": "bkcc", "space_id": "123", "url": "http://bkapi.example.com/"},
            {"space_uid": "bkcc__123", "url": "http://bkapi.example.com/"},
        ],
    )


class BkBaseConfig(BaseConfigModel):
    """数据平台配置"""

    enabled: bool = Field(description="是否启用", default=False)
    project_id: int = Field(description="项目ID", default=0)
    intelligent_detect_plan_id: int = Field(description="智能检测流程ID", default=0)
    allow_all_cmdb_level: bool = Field(description="是否允许所有数据源配置的CMDB动态节点聚合", default=False)


class BkBcsConfig(BaseConfigModel):
    """BCS 容器服务配置"""

    api_gateway_host: str = Field(default="", title="BCS API Gateway 地址")
    api_gateway_port: int = Field(default=443, title="BCS API Gateway 端口")
    api_gateway_schema: str = Field(default="https", title="BCS API Gateway 协议")
    api_gateway_token: str = Field(default="", title="BCS API Gateway Token")
    cluster_bk_env_label: str = Field(default="", title="BCS 集群环境标签")


class BlueKingConfig(BaseConfigSettings):
    """
    蓝鲸相关配置
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(validate_by_name=True, extra="ignore")

    # 多租户模
    enable_multi_tenancy: bool = Field(
        description="是否启用多租户模式",
        default=False,
        validation_alias=AliasChoices("enable_multi_tenancy", "ENABLE_MULTI_TENANT_MODE"),
    )
    space_builtin_data_link_mode: str = Field(
        description="内置数据链路是按业务还是按租户申请，当为空时，按业务申请；当为 tenant 时，按租户申请",
        default="",
        validation_alias=AliasChoices("space_builtin_data_link_mode", "SPACE_BUILTIN_DATA_LINK_MODE"),
    )
    initialized_tenant_list: list[str] = Field(default_factory=lambda: ["system"], description="已经初始化的租户列表")

    # 应用基础配置
    app_code: str = Field(
        description="蓝鲸应用ID",
        default="bk_monitorv3",
        validation_alias=AliasChoices("bk_app_code", "BK_APP_CODE"),
    )
    app_secret: str = Field(
        description="蓝鲸应用密钥",
        default="",
        validation_alias="bk_app_secret",
    )
    environment: str = Field(default="production", description="环境类型")
    platform: str = Field(default="community", description="平台类型")
    common_username: str = Field(default="admin", description="公共用户")
    default_bk_biz_id: int = Field(default=2, description="默认业务（仅单租户或运营租户下生效）")

    # API配置
    api_url: HttpUrl = Field(
        description="蓝鲸API网关地址模板",
        validation_alias="bk_component_api_url",
        default=HttpUrl("http://bkapi.example.com/"),
    )
    api_configs: dict[str, BkApiModuleConfig] = Field(
        description="蓝鲸API模块配置",
        default_factory=lambda: {
            "nodeman": BkApiModuleConfig(mode="esb"),
        },
    )
    gse: BkGseConfig = Field(description="GSE配置", default_factory=BkGseConfig)
    bcs: BkBcsConfig = Field(description="BCS容器服务配置", default_factory=BkBcsConfig)
    unify_query: BkUnifyQueryConfig = Field(description="统一查询配置", default_factory=BkUnifyQueryConfig)
    bkbase: BkBaseConfig = Field(description="数据平台配置", default_factory=BkBaseConfig)
