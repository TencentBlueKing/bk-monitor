# pyright: reportUnusedParameter=false
# pyright: reportUnannotatedClassAttribute=false
import builtins
import uuid
from collections import UserString
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from django.conf import settings
from django.utils.module_loading import import_string
from pydantic import Field
from typing_extensions import Protocol

from bk_monitor_base.infras.caches.md5 import count_md5
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID

from .base import BaseModel
from .version import ApiVersion

if TYPE_CHECKING:
    from bk_monitor_base.infras.declaratives.store import (
        ResourceStore,  # pyright: ignore[reportPrivateLocalImportUsage]
    )

DEFAULT_NAMESPACE = "default"


class DetectFieldClassMixin:
    @classmethod
    def get_field_cls(cls: type["BaseModel"], field_name: str) -> type[Any]:
        fields = cls.__pydantic_fields__  # type: ignore
        if field_name not in fields:
            raise ValueError(f"field_name: {field_name} not exists.")
        field = fields[field_name]
        if field.annotation is None:
            raise ValueError(f"field_name: {field_name} not exists.")
        return field.annotation


class DeleteStatus(Enum):
    DELETING = "DELETING"
    DELETED = "DELETED"


class Kind(UserString):
    """Kind for a Resource"""


class Labels(BaseModel):
    """Labels for a Resource"""

    bk_tenant_id: str = Field(default=DEFAULT_TENANT_ID, description="租户ID")

    @classmethod
    def default(cls):
        return Labels()


class Annotations(BaseModel):
    """Annotations for a Resource"""

    @classmethod
    def default(cls):
        return Annotations()


TLabels = TypeVar("TLabels", bound=Labels)


class Metadata(BaseModel, DetectFieldClassMixin):
    """Metadata for a Resource"""

    name: str
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    namespace: str = DEFAULT_NAMESPACE

    labels: TLabels = Field(default_factory=Labels.default)
    annotations: Annotations = Field(default_factory=Annotations.default)
    created_at: datetime | None = Field(default=None, description="创建时间")
    created_by: str | None = Field(default=None, description="创建人")
    updated_at: datetime | None = Field(default=None, description="修改时间")
    updated_by: str | None = Field(default=None, description="修改人")

    # class Config:
    #     allow_mutation = False  # pydantic配置，禁止创建后修改字段


class Spec(BaseModel):
    """Spec for a Resource"""

    @property
    def spec_hash(self) -> str:
        """计算spec的校验码"""
        return count_md5(self.dict())


class Status(BaseModel):
    """Status for a Resource"""

    delete_status: DeleteStatus | None = Field(default=None, description="删除状态")


TStatus = TypeVar("TStatus", bound=Status)
TSpec = TypeVar("TSpec", bound=Spec)


class StoreAttribute:
    def __get__(self, instance: type["BaseResource"] | None, type_: type["BaseResource"]):
        if instance is None:
            return self._store(type_)
        else:
            return self._store(type_, ins=instance)

    @staticmethod
    def _store(resource_cls: type["BaseResource"], ins: type["BaseResource"] | None = None) -> "ResourceStore":
        """获取存储对象"""
        if not hasattr(resource_cls, "store_class") or resource_cls.store_class is None:
            store_cls = import_string(settings.DEFAULT_RESOURCE_STORE)
        else:
            store_cls = import_string(resource_cls.store_class)

        store_ins = store_cls(resource_cls=resource_cls, resource=ins)
        return store_ins


TMetadata = TypeVar("TMetadata", bound=Metadata)


class BaseResource(BaseModel, DetectFieldClassMixin):
    """Basic Resource"""

    kind: ClassVar[Kind]
    api_version: ClassVar[ApiVersion]
    metadata: TMetadata = Field(description="Metadata for the resource")

    store_class: ClassVar[str | None] = None
    store: ClassVar[StoreAttribute] = StoreAttribute()

    def dict(self, *args, **kwargs) -> dict[str, Any]:  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportImplicitOverride]
        # 手动将 ClassVar 包括在内
        result = super().dict(*args, **kwargs)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        result["kind"] = str(self.kind)
        result["api_version"] = str(self.api_version)
        return result

    def __str__(self):  # pyright: ignore[reportImplicitOverride]
        return f"{self.kind}<{self.metadata.namespace}/{self.metadata.name}>"

    def __repr__(self):
        return self.__str__()

    @classmethod
    def get_plural(cls):
        """Plural form of the resource
        if no override, use kind+"s" as plural
        """
        return cls.kind.lower() + "s"

    @property
    def mark(self):
        return f"{self.api_version}/{self.kind}"

    def duplicate(self, **kwargs) -> "BaseResource":
        """Return a duplicated instance of the resource without saving it.
        You can change the metadata of the new instance while duplicating.
        The uid will change automatically. However, you are HIGHLY RECOMMEND to set uid and name by yourself

        :param: kwargs:the key-value of attrs you want to change in metadata
        :return: the duplicated instance
        :rtype: same as origin

        Example::
        >>> resource = BaseResource()   # resource is what you are going to duplicate
        >>> duplicated = resource.duplicate(uid=uuid.uuid4(), name=resource.metadata.name+"_copy")
        duplicated is the copy of resource except metadata.uid and metadata.name
        >>> duplicated = resource.duplicate()  # not recommend
        duplicated is the copy of resource except metadata.uid
        """
        if not kwargs.get("uid"):
            kwargs["uid"] = uuid.uuid4()
        new_metadata = self.metadata.copy(update=kwargs, deep=True)
        return self.copy(update={"metadata": new_metadata}, deep=True)

    def save(self):
        self.store.apply(silence=True)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    @classmethod
    def validate_filters(cls, filters: builtins.dict[str, Any]) -> None:
        pass


class Resource(BaseResource):
    """Resource definition"""

    spec: TSpec
    status: TStatus = Field(default_factory=Status)

    @property
    def spec_hash(self):
        """计算 spec 字段的 hash 校验码"""
        return self.spec.spec_hash

    def is_deleting(self):
        return self.status.delete_status in [DeleteStatus.DELETING, DeleteStatus.DELETED]


class ResourceProtocol(Protocol):
    """Resource protocol"""

    kind: ClassVar[Kind]
    api_version: ClassVar[ApiVersion]
    metadata: Metadata
    spec: Spec
    status: Status

    @property
    def spec_hash(self):
        """计算 spec 字段的 hash 校验码"""
        return self.spec.spec_hash


class AppModelResource(Resource):
    """Resource with app model"""

    store_class = "bk_monitor_base.infras.declaratives.store.app_db.AppDBStore"
