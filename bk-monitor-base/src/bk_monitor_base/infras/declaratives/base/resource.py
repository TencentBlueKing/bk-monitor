import enum
import importlib
import os
import time
import types
import uuid
from ipaddress import IPv4Address
from types import NoneType, UnionType
from typing import Any, ClassVar, Union, get_args, get_origin

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.timezone import now
from pydantic import BaseModel as PydanticBaseModel
from pydantic_core import PydanticUndefined

from bk_monitor_base.infras.db_models import BaseModel
from bk_monitor_base.infras.declaratives import Resource, ResourceAction, ResourceEvent
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.declaratives.metrics import DB_WRITE_TOTAL
from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry

from .constants import ModelFieldDefinition, ModelFieldDefinitionWithDefault


class ResourceManager(models.Manager):
    def delete_by_uid(self, uid: str) -> ResourceEvent:
        try:
            resource: ResourceModel = self.get(uid=uid)
        except ObjectDoesNotExist:
            logger.exception(f"Failed to find resource in db: {uid}")
            raise

        resource.active = False
        resource.save(update_fields=["active", "updated_at", "status"])

        return ResourceEvent(action=ResourceAction.Deleted, resource=resource.resource)

    def apply(self, resource: Resource) -> tuple[ResourceEvent, "ResourceModel"]:
        """Apply resource, create or update"""
        DB_WRITE_TOTAL.labels(model_name=resource.mark, module_name=settings.APP_CODE).inc()
        try:
            existed: ResourceModel = self.get(name=resource.metadata.name, namespace=resource.metadata.namespace)
        except ObjectDoesNotExist:
            return self._create_resource(resource)

        if not existed.active:
            existed.name = self._get_delete_name(str(existed.name))
            existed.save()
            if resource.metadata.uid == existed.uid:
                resource.metadata.uid = uuid.uuid4()
            return self._create_resource(resource)

        for k, v in resource.metadata.labels.dict().items():
            setattr(existed, k, v)
        existed.annotations = resource.metadata.annotations.dict()
        existed.spec = resource.spec.dict()
        action = ResourceAction.Updated
        existed.status = resource.status.dict()
        existed.save()
        return ResourceEvent(action=action, resource=existed.resource), existed

    def _create_resource(self, resource: Resource) -> tuple[ResourceEvent, "ResourceModel"]:
        created = self.create(
            kind=resource.kind,
            api_version=resource.api_version,
            uid=resource.metadata.uid,
            name=resource.metadata.name,
            namespace=resource.metadata.namespace,
            annotations=resource.metadata.annotations.dict(),
            spec=resource.spec.dict(),
            status=resource.status.dict(),
            **resource.metadata.labels.dict(),
        )
        return ResourceEvent(action=ResourceAction.Created, resource=created.resource), created

    def update(self, resource: Resource) -> tuple[ResourceEvent, "ResourceModel"]:
        existed: ResourceModel = self.get(name=resource.metadata.name, namespace=resource.metadata.namespace)
        for k, v in resource.metadata.labels.dict().items():
            setattr(existed, k, v)
        existed.annotations = resource.metadata.annotations.dict()
        existed.spec = resource.spec.dict()
        existed.status = resource.status.dict()
        action = ResourceAction.Updated
        if not existed.active:
            existed.name = self._get_delete_name(str(existed.name))
        existed.save()
        DB_WRITE_TOTAL.labels(model_name=resource.mark, module_name=settings.APP_CODE).inc()
        return ResourceEvent(action=action, resource=existed.resource), existed

    @classmethod
    def _get_delete_name(cls, name: str) -> str:
        """获取删除后的资源名称，防止重名冲突"""
        if not name.endswith("-deleted"):
            return f"{name}-{round(time.time() * 1000)}-deleted"[-128:]
        return name


class ResourceModel(BaseModel):
    """Resource DB Model

    抽象基类，按照用户动态注册的资源类型，生成对应的数据库表
    """

    _kind_mark: ClassVar[Kind | None] = None
    _api_version_mark: ClassVar[ApiVersion | None] = None

    # 是否激活，用于标记资源是否被删除
    active = models.BooleanField(default=True)

    kind = models.CharField(max_length=64, db_index=True)
    api_version = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=128, db_index=True)
    namespace = models.CharField(max_length=128, default="default", db_index=True)
    uid = models.UUIDField(default=uuid.uuid4, primary_key=True)
    annotations = models.JSONField(default=dict)
    # spec 使用 JSONField 存储，需要考虑可能会衍生出需要通过 field 进行查询的情况
    # JSONField Search 是否能满足 ApiServer 的性能要求，需要进一步评估
    spec = models.JSONField(default=dict)
    # 与 spec 不同，status 中的字段是肯定需要被索引的，因此仿照 labels 根据不同的 model 中的 status 做字段拆分
    status = models.JSONField(default=dict)

    objects: ClassVar[ResourceManager] = ResourceManager()

    class Meta:
        unique_together = ("name", "namespace")
        abstract = True
        app_label = "kingeye_meta_core"

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        controller = ResourceModelController()
        controller.register(Kind(cls._kind_mark), ApiVersion(cls._api_version_mark), cls)

    def __str__(self) -> str:
        return f"{self.namespace}/{self.name}"

    @property
    def resource(self) -> Resource:
        """Convert db object to resource"""
        resource_cls = DefaultResourceRegistry.get(kind=Kind(self.kind), api_version=ApiVersion(self.api_version))
        if resource_cls is None:
            raise ValueError(f"resource<{self.kind}> has no Model imported")

        metadata_cls = resource_cls.get_field_cls("metadata")
        labels_cls = metadata_cls.get_field_cls("labels")
        annotations_cls = metadata_cls.get_field_cls("annotations")
        spec_cls = resource_cls.get_field_cls("spec")
        status_cls = resource_cls.get_field_cls("status")

        resource_cls.kind = Kind(self.kind)
        resource_cls.api_version = ApiVersion(self.api_version)
        return resource_cls(
            metadata=metadata_cls(
                name=self.name,
                uid=self.uid,
                namespace=self.namespace,
                labels=labels_cls(**self.labels),
                annotations=annotations_cls(**self.annotations),
                created_at=self.created_at,
                created_by=self.created_by,
                updated_at=self.updated_at,
                updated_by=self.updated_by,
            ),
            spec=spec_cls(**self.spec),
            status=status_cls(**self.status),
        )

    @property
    def labels(self) -> dict[str, Any]:
        resource_cls = DefaultResourceRegistry.get(kind=Kind(self.kind), api_version=ApiVersion(self.api_version))
        if resource_cls is None:
            raise ValueError(f"resource<{self.kind}> has no Model imported")
        metadata_cls = resource_cls.get_field_cls("metadata")
        labels_cls = metadata_cls.get_field_cls("labels")
        label_data = {field: getattr(self, field) for field in labels_cls.__fields__.keys()}
        return label_data


class ResourceModelController:
    generated_models: ClassVar[dict[tuple[Kind, ApiVersion], type[ResourceModel]]] = {}
    generated_path: ClassVar[str] = "kingeye/meta/declarative_api/core/models/generated"

    BASIC_TYPE_MAP: ClassVar[
        dict[type[str] | type[int] | type[float] | type[bool] | type[uuid.UUID] | type[IPv4Address], tuple[str]]
    ] = {
        str: ("CHAR_FIELD",),
        int: ("INT_FIELD",),
        float: ("FLOAT_FIELD",),
        bool: ("BOOLEAN_FIELD",),
        uuid.UUID: ("UUID_FIELD",),
        IPv4Address: ("CHAR_FIELD",),
    }

    @classmethod
    def get_db_obj(cls, resource: Resource) -> tuple[bool, ResourceModel]:
        """Get db object from resource

        if db object exists, return it,
        else create a new db object but not saving.
        """
        model_cls = cls.get_model(resource.kind, resource.api_version)
        if model_cls is None:
            raise ValueError("resource<%s> has no Model imported", resource)

        created = False
        try:
            db_obj = model_cls.objects.get(name=resource.metadata.name, namespace=resource.metadata.namespace)
        except model_cls.DoesNotExist:
            created = True
            # creating a new db obj but no saving
            db_obj = model_cls(
                kind=resource.kind,
                api_version=resource.api_version,
                uid=resource.metadata.uid,
                name=resource.metadata.name,
                namespace=resource.metadata.namespace,
                labels=resource.metadata.labels.dict(),
                annotations=resource.metadata.annotations.dict(),
                spec=resource.spec.dict(),
                status=resource.status.dict(),
            )

        return created, db_obj

    @classmethod
    def get_model(cls, kind: Kind, api_version: ApiVersion) -> type[ResourceModel] | None:
        return cls.generated_models.get((kind, api_version))

    @classmethod
    def register(cls, kind: Kind, api_version: ApiVersion, model: type[ResourceModel]):
        """Register resource model"""
        cls.generated_models[(kind, api_version)] = model

    @classmethod
    def detect(cls, kind: Kind, api_version: ApiVersion) -> bool:
        """Detect resource model exists or not"""
        if not cls.generated_models:
            return False

        if (kind, api_version) not in cls.generated_models:
            return False

        return True

    @classmethod
    def generate(cls, resource: type[Resource]) -> type[ResourceModel]:
        """Generate model from resource"""
        cls_name = f"{resource.api_version.title()}{resource.kind.title()}"

        with open(os.path.join(os.path.dirname(__file__), "generated.tmpl")) as f:
            template = f.read()
        labels_cls = resource.get_field_cls("metadata").get_field_cls("labels")
        label_fields = cls.generate_field_defines(labels_cls)
        label_fields = [f"    {line}" for line in label_fields]
        class_text = template.format(
            cls_name=cls_name,
            kind=resource.kind,
            api_version=resource.api_version,
            generated_at=now(),
            lower_kind=resource.kind.lower(),
            label_fields="\n".join(label_fields),
        )

        with open(f"{cls.generated_path}/{cls_name.lower()}.py", "w") as f:
            f.write(class_text)

        parent_module = ".".join(cls.generated_path.split("/"))
        target_module = importlib.import_module(f"{parent_module}.{cls_name.lower()}")

        target_model = getattr(target_module, cls_name)
        cls.generated_models[(resource.kind, resource.api_version)] = target_model
        return target_model

    @classmethod
    def generate_field_defines(cls, model_cls: type[PydanticBaseModel]) -> list[str]:
        field_definitions = []
        fields = model_cls.__pydantic_fields__  # type: ignore
        for field_name, model_field in fields.items():
            field_def = cls.get_field_define_by_model_field(model_field)
            field_definitions.append(f"{field_name} = {field_def}")
        return field_definitions

    @classmethod
    def get_field_define_by_model_field(cls, model_field: Any) -> str:
        """根据字段返回models字段定义"""

        field_type = cls._resolve_type(model_field.annotation)

        # 检查复杂联合类型和泛型容器类型
        if cls._is_complex_union_type(field_type):
            return cls._get_field_definition("JSON_FIELD", model_field)
        if cls._is_generic_container_type(field_type):
            return cls._get_field_definition("JSON_FIELD", model_field)

        enum_type = cls._resolve_enum_type(field_type)
        if enum_type:
            field_type = enum_type
        field_key = cls._resolve_basic_field_key(field_type)
        if not field_key:
            return cls._get_field_definition("JSON_FIELD", model_field)
        return cls._get_field_definition(field_key, model_field)

    @staticmethod
    def _resolve_type(annotation: object) -> object:
        """解析Optional类型"""
        origin = get_origin(annotation)
        if origin is UnionType or str(origin) == "typing.Union":
            args = [arg for arg in get_args(annotation) if arg is not NoneType]
            return args[0] if len(args) == 1 else annotation
        return annotation

    @staticmethod
    def _is_complex_union_type(annotation) -> bool:
        """检查是否为复杂联合类型（多个非None类型的联合）"""
        origin = get_origin(annotation)
        if origin is Union or origin is types.UnionType:
            args = get_args(annotation)
            non_none_args = [arg for arg in args if arg is not type(None)]
            return len(non_none_args) > 1
        return False

    @staticmethod
    def _is_generic_container_type(annotation) -> bool:
        """检查是否为泛型容器类型"""
        origin = get_origin(annotation)
        return origin in (list, dict, set, tuple, frozenset)

    @staticmethod
    def _resolve_enum_type(annotation: object) -> type[str] | type[int] | type[float] | None:
        """处理 Enum 类型"""
        if not isinstance(annotation, type):
            return None
        try:
            if issubclass(annotation, enum.Enum):
                if issubclass(annotation, str):
                    return str
                if issubclass(annotation, int):
                    return int
                if issubclass(annotation, float):
                    return float
        except TypeError:
            pass
        return None

    @classmethod
    def _resolve_basic_field_key(cls, annotation: object) -> str | None:
        """将 Python 类型映射到 Django 字段定义键。"""
        if annotation is str:
            return cls.BASIC_TYPE_MAP[str][0]
        if annotation is int:
            return cls.BASIC_TYPE_MAP[int][0]
        if annotation is float:
            return cls.BASIC_TYPE_MAP[float][0]
        if annotation is bool:
            return cls.BASIC_TYPE_MAP[bool][0]
        if annotation is uuid.UUID:
            return cls.BASIC_TYPE_MAP[uuid.UUID][0]
        if annotation is IPv4Address:
            return cls.BASIC_TYPE_MAP[IPv4Address][0]
        return None

    @staticmethod
    def _get_field_definition(field_key: str, model_field: Any) -> str:
        default_factory = getattr(model_field, "default_factory", None)
        has_default_factory = default_factory is not None
        has_explicit_default = model_field.default is not PydanticUndefined and model_field.default is not None
        enum_cls = (
            ModelFieldDefinitionWithDefault if (has_default_factory or has_explicit_default) else ModelFieldDefinition
        )
        return enum_cls[field_key].value
