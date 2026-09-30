import uuid
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from bk_monitor_base.infras.declaratives.constants import ES_RESOURCE_STORE
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Labels, Metadata, Resource, Spec, Status
from bk_monitor_base.infras.declaratives.definitions.enums import ResourceType

from .version import PACKAGE_VERSION


class TargetType(str, Enum):
    """cmdb 事件类型操作"""

    INST = "instance"
    TOPO = "dynamic_topo"
    GROUP = "dynamic_group"


class CMDBEventType(str, Enum):
    """cmdb 事件类型"""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class ChangeObjectType(str, Enum):
    """变更对象类型"""

    OBJECT_MODEL = "object_model"
    OBJECT_MODEL_INST = "object_model_inst"


class CMDBEventLabels(Labels):
    """Labels for a CMDBEvent"""

    bk_object_code: str = Field(default="", description="CMDB 对象标识符")
    bk_object_inst_id: int = Field(default=0, description="CMDB 对象实例 ID")
    event_type: CMDBEventType = Field(default=CMDBEventType.UPDATED, description="事件类型")


class CMDBEventMetadata(Metadata):
    """Metadata for a CMDBEvent"""

    labels: CMDBEventLabels


class CMDBEventStatus(Status):
    """Basic status"""

    pass


class ResourceAttr(BaseModel):
    """资源属性基类"""

    _resource_type: ClassVar[str] = ""

    @classmethod
    def get_resource_type(cls) -> str:
        """获取资源类型"""
        return cls._resource_type

    def __init_subclass__(cls, **kwargs):  # pyright: ignore[reportMissingParameterType]
        AttrModelFactory.register(cls)
        super().__init_subclass__(**kwargs)


class AttrModelFactory:
    """属性模型工厂"""

    _model_registry: dict[str, type[ResourceAttr]] = {}

    @classmethod
    def register(cls, model: type[ResourceAttr]):
        """注册属性模型"""
        resource_type = model.get_resource_type()
        if not resource_type:
            raise ValueError(f"模型 {model.__name__} 必须定义 _resource_type")
        cls._model_registry[resource_type] = model
        return model

    @classmethod
    def get_model(cls, resource_type: str) -> type[ResourceAttr]:
        """获取属性模型"""
        if resource_type not in cls._model_registry:
            raise ValueError(f"资源类型 {resource_type} 暂不支持，支持的类型: {list(cls._model_registry.keys())}")
        return cls._model_registry[resource_type]


class HostRelationAttr(ResourceAttr):
    """主机关系属性"""

    _resource_type: ClassVar[str] = ResourceType.HOST_RELATION.value
    bk_biz_id: int | None = Field(default=None, description="业务 ID")


class CMDBEventSpec(Spec):
    # 资源类型 如： host, host_relation, object_instance
    # 数据来源：https://bk.tencent.com/docs/markdown/ZH/CMDB/3.11/APIDocs/cc/zh-hans/resource_watch.md
    # resource_watch 返回数据中 bk_resource 字段或其他
    resource_type: str
    event_type: CMDBEventType = Field(default=CMDBEventType.UPDATED, description="事件类型")
    # 属性变更记录, source 原信息, target 当前信息
    # 属性跟 resource_type 绑定, 如host_relation  source, target 只有 bk_biz_id 属性
    source: dict[str, Any] = Field(default_factory=dict, description="变更对象原属性")
    target: dict[str, Any] = Field(default_factory=dict, description="变更对象现在属性")
    # 变更对象类型, 目前有实例及模型（CMDB）
    change_object_type: ChangeObjectType = Field(
        default=ChangeObjectType.OBJECT_MODEL_INST, description="变更对象的类型"
    )
    bk_object_code: str = Field(default="", description="CMDB 对象标识符")
    bk_object_inst_id: int = Field(default=0, description="CMDB 对象实例 ID")
    collect_config_uids: list[uuid.UUID] = Field(default_factory=list, description="与事件关联的采集配置 UID 列表")
    strategy_config_uids: list[uuid.UUID] = Field(default_factory=list, description="与事件关联的策略配置 UID 列表")

    @property
    def source_obj(self):
        model_class = AttrModelFactory.get_model(self.resource_type)
        return model_class(**self.source)

    @property
    def target_obj(self):
        model_class = AttrModelFactory.get_model(self.resource_type)
        return model_class(**self.target)


class CMDBEvent(Resource):
    """CMDB 事件定义"""

    store_class: ClassVar[str | None] = ES_RESOURCE_STORE
    kind: ClassVar[Kind] = Kind("CMDBEvent")
    api_version: ClassVar[ApiVersion] = ApiVersion(PACKAGE_VERSION)
    spec: CMDBEventSpec
    status: CMDBEventStatus = Field(default_factory=CMDBEventStatus)
    metadata: CMDBEventMetadata
