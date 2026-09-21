import json
from datetime import datetime
from typing import ClassVar

from blue_krill.data_types.enum import EnumField, StructuredEnum
from django.utils.timezone import now
from pydantic import Field

from bk_monitor_base.infras.declaratives.constants import ES_RESOURCE_STORE
from bk_monitor_base.infras.declaratives.definitions.resource import ApiVersion, BaseResource, Kind, Metadata, Resource

PACKAGE_VERSION = ApiVersion("v1")
EVENT_KIND = Kind("ResourceEvent")


class EventType(str, StructuredEnum):
    """Event type"""

    Normal = EnumField("Normal", label="Normal")
    Warning = EnumField("Warning", label="Warning")


class ResourceAction(str, StructuredEnum):
    """资源操作"""

    Created = EnumField("Created", label="Created")
    Updated = EnumField("Updated", label="Updated")
    Deleted = EnumField("Deleted", label="Deleted")


class ResourceEventMetadata(Metadata):
    name: str = Field(default_factory=str)


class ResourceEvent(BaseResource):
    """Event related to resource

    资源相关的事件，当下给不出更抽象的通用事件定义
    不如聚焦在资源场景下的事件定义，后续再根据实际情况进行调整
    """

    store_class: ClassVar[str | None] = ES_RESOURCE_STORE
    api_version: ClassVar[ApiVersion] = PACKAGE_VERSION
    kind: ClassVar[Kind] = EVENT_KIND
    plural: ClassVar[str] = "events"

    metadata: ResourceEventMetadata = Field(default_factory=ResourceEventMetadata)
    # 资源操作
    action: ResourceAction
    # 关联的资源 uid
    resource: Resource | None = None
    # 事件类型，普通事件/警告事件
    type: EventType = Field(default_factory=lambda: EventType.Normal)
    # 事件来源，用来标注事件发生的组件
    # controller 发起某个资源更新后会再次从 watch 流中拿到对应事件
    # 这种情况下应该通过 source 字段，忽略由自己产生的事件
    source: str = ""
    # 仅当 ignore_self=True 且 source 相等时过滤
    ignore_self: bool = False
    # 事件发生时间，microsecond
    event_time: datetime = Field(default_factory=now)
    # 事件消息，一般用于扩展描述事件信息，比如资源更新失败的原因
    message: str = Field(default_factory=str)

    def to_json_with_resource_mark(self, *args, **kwargs) -> str:
        """序列化为json，并且在结果中包含资源的 kind 和 apiVersion"""
        data = self.dict(*args, **kwargs)

        if self.resource is not None:
            # 仅在 Event 时手动塞入 kind/api_version
            data["resource"]["kind"] = str(self.resource.kind)
            data["resource"]["api_version"] = str(self.resource.api_version)

        return json.dumps(data, **kwargs)

    def __post_model_init__(self, context):
        if self.metadata.name == "":
            self.metadata = self.metadata.copy(update={"name": str(self)})

    def __str__(self):
        if self.resource is None:
            return f"ResourceEvent({self.event_time.timestamp()}-{self.action}-{self.type}-<Missing>)"

        return f"ResourceEvent({self.event_time.timestamp()}-{self.action}-{self.type}-{self.resource.metadata.uid})"
