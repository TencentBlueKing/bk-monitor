from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID


# 内置的对象模型bk_obj_id
class BuiltinObjectObjId:
    BIZ: str = "biz"
    SET: str = "set"
    MODULE: str = "module"
    HOST: str = "host"


class CmdbBaseModel(BaseModel):
    """CMDB基础模型，提供通用的字段管理功能"""

    @property
    def required_fields(self) -> list[str]:
        """自动提取必选字段，避免硬编码"""
        return self._get_required_fields()

    @classmethod
    def get_required_fields(cls) -> list[str]:
        """获取所有字段列表"""
        return cls._get_required_fields()

    @classmethod
    def _get_required_fields(cls) -> list[str]:
        """获取模型的必选字段列表"""
        required_fields: list[str] = []

        # 获取模型字段信息
        model_fields = cls.model_fields

        for field_name, field_info in model_fields.items():
            # 检查字段是否为必选（没有默认值且不是Optional）
            if field_info.is_required():
                required_fields.append(field_name)

        return required_fields

    @classmethod
    def get_optional_fields(cls) -> list[str]:
        """获取可选字段列表"""
        optional_fields: list[str] = []
        model_fields = cls.model_fields

        for field_name, field_info in model_fields.items():
            if not field_info.is_required():
                optional_fields.append(field_name)

        return optional_fields

    def to_dict(self) -> dict[str, Any]:
        """将模型实例转换为字典"""
        return self.model_dump()

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")


class ObjectModel(BaseModel):
    bk_obj_id: str
    bk_obj_name: str


class Biz(CmdbBaseModel):
    # 内置必选字段
    bk_biz_id: int
    bk_biz_name: str
    bk_obj_id: str = BuiltinObjectObjId.BIZ
    bk_tenant_id: str = DEFAULT_TENANT_ID
    time_zone: str = "Asia/Shanghai"

    @property
    def bk_inst_id(self) -> int:
        return self.bk_biz_id


class Set(CmdbBaseModel):
    # 内置必选字段
    bk_set_id: int
    bk_set_name: str
    bk_biz_id: int
    bk_obj_id: str = BuiltinObjectObjId.SET
    set_template_id: int = Field(default=0)

    @property
    def bk_inst_id(self) -> int:
        return self.bk_set_id


class Module(CmdbBaseModel):
    # 内置必选字段
    bk_biz_id: int
    bk_set_id: int
    bk_module_id: int
    bk_module_name: str
    bk_obj_id: str = BuiltinObjectObjId.MODULE
    service_template_id: int = Field(default=0)

    @property
    def bk_inst_id(self) -> int:
        return self.bk_module_id


class Host(CmdbBaseModel):
    # 内置必选字段
    bk_host_id: int
    bk_host_name: str
    bk_cloud_id: int
    bk_host_innerip: str
    bk_host_innerip_v6: str
    bk_obj_id: str = BuiltinObjectObjId.HOST
    bk_biz_id: int

    @property
    def bk_inst_id(self) -> int:
        return self.bk_host_id


class ObjectInst(CmdbBaseModel):
    # 内置必选字段
    bk_inst_id: int
    bk_inst_name: str
    bk_obj_id: str


Model = TypeVar("Model", bound=BaseModel)


class ObjectList(Generic[Model], list[Model]):
    def __init__(self, data: list[dict[str, Any]], model_class: type[Model]):
        items: list[Model] = []
        for item in data:
            if isinstance(item, model_class):
                items.append(item)
            else:
                items.append(model_class(**item))
        super().__init__(items)


class BizList(ObjectList["Biz"]):
    def __init__(self, biz_data: list[dict[str, Any]]):
        super().__init__(biz_data, Biz)


class SetList(ObjectList["Set"]):
    def __init__(self, set_data: list[dict[str, Any]]):
        super().__init__(set_data, Set)


class ModuleList(ObjectList["Module"]):
    def __init__(self, module_data: list[dict[str, Any]]):
        super().__init__(module_data, Module)


class HostList(ObjectList["Host"]):
    def __init__(self, host_data: list[dict[str, Any]]):
        super().__init__(host_data, Host)


class ObjectInstList(ObjectList["ObjectInst"]):
    def __init__(self, inst_data: list[dict[str, Any]]):
        super().__init__(inst_data, ObjectInst)


class ServiceTemplate(BaseModel):
    """服务模板模型"""

    bk_biz_id: int = Field(title="业务ID")
    id: int = Field(title="服务模板ID")
    name: str = Field(title="服务模板名称")
    service_category_id: int = Field(title="服务分类ID", default=0)


class SetTemplate(BaseModel):
    """集群模板模型"""

    bk_biz_id: int = Field(title="业务ID")
    id: int = Field(title="集群模板ID")
    name: str = Field(title="集群模板名称")


class ObjectAssociation(CmdbBaseModel):
    """对象关联关系模型"""

    id: int = Field(title="模型关联关系的身份id")
    bk_obj_asst_id: str = Field(title="模型关联关系的唯一id")
    bk_obj_asst_name: str = Field(title="关联关系的别名")
    bk_asst_id: str = Field(title="关联类型id")
    bk_obj_id: str = Field(title="源模型id")
    bk_asst_obj_id: str = Field(title="目标模型id")
    mapping: str = Field(title="源模型与目标模型关联关系实例的映射关系", default="")
    on_delete: str = Field(title="删除关联关系时的动作", default="none")
    bk_supplier_account: str = Field(title="开发商账号", default="0")
    ispre: bool | None = Field(title="是否为预置字段", default=None)


class ObjectAssociationList(ObjectList["ObjectAssociation"]):
    def __init__(self, data: list[dict[str, Any]]):
        super().__init__(data, ObjectAssociation)


class InstanceAssociation(CmdbBaseModel):
    """实例关联关系模型"""

    bk_inst_id: int = Field(title="源模型实例id")
    bk_asst_inst_id: int = Field(title="目标模型实例id")
    bk_asst_obj_id: str = Field(title="关联关系目标模型id")
    bk_asst_id: str = Field(title="关联类型id")
    bk_obj_asst_id: str = Field(title="自动生成的模型关联关系id")


class InstanceAssociationList(ObjectList["InstanceAssociation"]):
    def __init__(self, data: list[dict[str, Any]]):
        super().__init__(data, InstanceAssociation)
