import re
from enum import Enum
from typing import Any

import pydantic
from pydantic import BaseModel, Field, model_validator

from bk_monitor_base.domains.object_model.errors import ErrorCodes
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.models.base_entity import BaseEntity


class ObjectModelGroup(BaseEntity):
    """
    对象模型分组
    """

    object_model_group_id: int | None = Field(description="对象模型分组主键", default=None)
    parent_object_model_group_id: int | None = Field(description="父级分组id", default=None)
    object_model_group_code: str = Field(description="分组code", min_length=1, max_length=128)
    object_model_group_name: str = Field(description="分组名称", min_length=0, max_length=255)
    object_model_group_name_i18n: dict[str, str] = Field(description="模型分组名称多语言", default_factory=dict)
    is_default: bool = Field(description="是否内置", default=False)
    bk_tenant_id: str = Field(description="租户ID", default=DEFAULT_TENANT_ID, max_length=64)

    # 附加信息
    related_obj: bool = Field(description="是否关联对象模型", default=False)
    can_delete: bool = Field(description="是否可删除", default=False)
    can_update: bool = Field(description="是否可修改", default=False)
    can_create: bool = Field(description="是否可创建子分组或对象模型", default=False)

    @model_validator(mode="after")
    def check_model_group(self):
        """
        校验对象模型分组code规则
        """
        # 内置code必须包含"-"
        rule = r"^[a-zA-Z][0-9a-zA-Z_\-]*$" if self.is_default else r"^[a-zA-Z][0-9a-zA-Z_]*$"
        if not re.match(rule, self.object_model_group_code):
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(
                f"不符合规则的object_model_group_code:{self.object_model_group_code}"
            )
        return self

    @pydantic.computed_field
    def level(self) -> int:
        return 2 if self.parent_object_model_group_id else 1


class DatasourceType(str, Enum):
    """
    对象模型数据来源
    """

    CMDB = "cmdb"  # cmdb
    CUSTOM = "custom"  # 自定义
    LEGACY = "legacy"  # 兼容旧子对象模型数据


class ObjectModelRelateType(str, Enum):
    """
    对象模型关联类型
    """

    APM = "APM"  # 提供给APM使用
    LEGACY = "LEGACY"  # 兼容旧子对象模型数据
    EMPTY = ""  # 未关联


class AttributeConfigItemOption(BaseModel):
    id: str = Field(description="选项ID")
    is_default: bool = Field(description="是否默认", default=True)
    name: str = Field(description="选项名称")
    type: str = Field(description="选项类型")


class AttributeConfigItem(BaseModel):
    """
    对象模型属性配置项
    """

    bk_property_id: str = Field(description="属性ID")
    bk_property_name: str = Field(description="属性名称")
    bk_property_type: str = Field(description="属性类型", default="")
    option: list[AttributeConfigItemOption] | None = Field(description="选项列表", default=None)


class AttributeConfig(BaseModel):
    """
    对象模型属性配置
    """

    config: list[AttributeConfigItem] = Field(description="属性配置列表", default_factory=list)
    sync_time: str = Field(description="同步时间", default="")


class ObjectModel(BaseEntity):
    """
    对象模型
    """

    object_model_id: int | None = Field(description="对象模型主键", default=None)
    object_model_code: str = Field(description="对象模型英文标识", min_length=1, max_length=128)
    object_model_name: str = Field(description="对象模型展示名称", min_length=0, max_length=255)
    object_model_name_i18n: dict[str, str] = Field(description="对象模型名称多语言", default_factory=dict)
    object_model_group_id: int = Field(description="对象模型分组id")
    is_default: bool = Field(description="是否内置", default=False)
    datasource: DatasourceType = Field(description="实例来源", min_length=1, max_length=32)
    bk_tenant_id: str = Field(description="租户ID", default=DEFAULT_TENANT_ID, max_length=64)

    # cmdb公共字段
    bk_cmdb_obj_id: str = Field(description="cmdb模型id", default="", max_length=255)
    display_fields: list[dict[str, Any]] = Field(description="标识展示字段", default_factory=list)
    inst_display_name: str = Field(description="实例展示名", default="", max_length=255)

    # DatasourceChoice.CMDB 映射字段相关
    host_related_field: str = Field(description="运行主机关联", default="", max_length=255)
    operator_fields: list[dict[str, str]] = Field(description="负责人字段", default_factory=list)
    topo_related_field: str = Field(description="IP映射字段", default="", max_length=255)
    port_field: str = Field(description="IP映射字段", default="", max_length=255)

    # DatasourceChoice.CUSTOM 关联字段相关
    custom_model_field: str = Field(description="自定义模型字段", default="", max_length=255)
    model_related_field: str = Field(description="关联模型字段", default="", max_length=255)

    related_model_type: ObjectModelRelateType = Field(
        description="关联类型",
        default=ObjectModelRelateType.EMPTY,
        max_length=8,
    )
    related_model_code: str = Field(description="关联模型标识", default=ObjectModelRelateType.EMPTY, max_length=255)
    ar_dimensionality: str = Field(description="apm唯一标识列表", default="", max_length=64)

    # 对象模型属性配置
    attribute_config: AttributeConfig = Field(description="对象模型属性配置", default_factory=AttributeConfig)

    # 附加信息
    can_update: bool = Field(description="允许更新", default=False)
    can_delete: bool = Field(description="允许删除", default=False)
    plugin_manage: bool = Field(description="允许管理关联插件", default=False)
    path: list[int] = Field(description="对象模型分组路径", default_factory=list)

    @model_validator(mode="after")
    def check_model(self):
        """
        校验对象模型code规则
        """
        # 内置code必须包含"-"
        rule = r"^[a-zA-Z][0-9a-zA-Z_\-]*$" if self.is_default else r"^[a-zA-Z][0-9a-zA-Z_]*$"
        if not re.match(rule, self.object_model_code):
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(
                f"不符合规则的object_model_code:{self.object_model_code}"
            )
        return self


class ObjectModelUsageRecord(BaseEntity):
    """
    对象模型使用记录
    """

    id: int | None = Field(description="主键", default=None)
    object_model_id: int = Field(description="对象模型ID")
    app_id: str = Field(description="关联Saas ID", min_length=1, max_length=64)
    app_name: str = Field(description="关联Saas名称", max_length=64, default="")
    module_id: str = Field(description="关联模块ID", min_length=1, max_length=255)
    module_name: str = Field(description="关联模块名称", max_length=255, default="")
    inst_id: str = Field(description="关联实例ID", min_length=1, max_length=255)
    inst_name: str = Field(description="关联实例名称", max_length=255, default="")
    bk_tenant_id: str = Field(description="租户ID", default=DEFAULT_TENANT_ID, max_length=64)
