import collections
import logging
import time
from distutils.version import LooseVersion
from typing import ClassVar

from django.db import models
from django.utils import timezone
from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Boolean, Date, Document, Integer, Keyword, MetaField, Q, Text
from elasticsearch_dsl import Object as BaseObject

from bk_monitor_base.infras.declaratives import ApiVersion, Kind, Resource, ResourceAction, ResourceEvent
from bk_monitor_base.infras.declaratives.base.constants import (
    DEFAULT_ES_ILM_POLICY_SETTINGS,
    DEFAULT_USE_ES_STORE_RESOURCE,
    es_model_conf_merge,
)
from bk_monitor_base.infras.declaratives.definitions import Annotations, EventType, ResourceEventMetadata
from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry
from bk_monitor_base.infras.threading.local import get_request_username

logger = logging.getLogger("component")


class ConfigurableConnectionMixin:
    """可配置连接的混入类"""

    _es_connection = None  # 默认为 None，使用默认连接

    @classmethod
    def _get_connection(cls, using=None):
        from elasticsearch_dsl import connections

        # 优先级：参数 using > 类属性 _es_connection > 默认连接
        connection_name = using or getattr(cls, "_es_connection", None)
        return connections.get_connection(connection_name)


class EmptySkippingObject(BaseObject):
    """
    防止部分为空的数据不能写入 ES index
    """

    def _serialize(self, data):
        if data is None:
            return None

        # somebody assigned raw dict to the field, we should tolerate that
        if isinstance(data, collections.abc.Mapping):
            return data

        return data.to_dict(skip_empty=False)


class ESBaseDocument(ConfigurableConnectionMixin, Document):
    """
    常规字段
    """

    created_at = Date()
    created_by = Keyword()
    updated_at = Date()
    updated_by = Keyword()

    def save(self, **kwargs):
        """保存时自动更新"""

        # 处理连接配置
        connection_name = getattr(self, "_es_connection", None)
        if connection_name:
            kwargs["using"] = connection_name

        self.updated_at = timezone.now()
        self.updated_by = get_request_username()
        write_index = self.get_write_index()
        return super().save(index=write_index, skip_empty=False, **kwargs)

    class Meta:
        dynamic = MetaField("true")
        dynamic_templates = MetaField(
            [
                {"objects": {"match_mapping_type": "object", "mapping": {"type": "object"}}},
                {
                    "all_as_keyword": {
                        "match_mapping_type": "*",
                        "mapping": {
                            "type": "keyword",
                            "norms": False,
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
                        },
                    }
                },
            ]
        )

    @classmethod
    def setup(cls, client=None):
        """
        索引初始化方法
        """

        if client is None:
            client = cls._get_connection()

        alias = cls.Index.ALIAS

        try:
            # 1. 检查/创建模块
            current_template = None
            if not client.indices.exists_template(name=cls.Index.ALIAS):
                cls._index.as_template(template_name=cls.Index.ALIAS, pattern=cls.Index.PATTERN).save()
                logger.info(f"{cls.Index.ALIAS} init index template")
            else:
                current_template = client.indices.get_template(name=alias).get(alias, {})

            # 生成新模板定义
            new_template = cls._index.as_template(template_name=alias, pattern=cls.Index.PATTERN).to_dict()

            # 检查模板是否需要更新（重点关注dynamic_templates）
            if not current_template or cls.is_template_changed(current_template, new_template):
                client.indices.put_template(name=alias, body=new_template)
                logger.info(f"Template {alias} {'created' if not current_template else 'updated'}")

            # 2. 检查/创建索引
            if not client.indices.exists_alias(name=cls.Index.ALIAS):
                initial_index = f"{alias}-000001"  # 初始索引名
                client.indices.create(
                    index=initial_index, body={"aliases": {cls.Index.ALIAS: {"is_write_index": True}}}
                )
                logger.info(f"{cls.Index.ALIAS} init index")
            else:
                # 检查现有索引的mapping是否需要更新
                alias_info = client.indices.get_alias(name=alias)
                write_index = next(
                    (idx for idx, meta in alias_info.items() if meta["aliases"][alias].get("is_write_index")), None
                )
                if write_index and cls.is_mapping_changed(client, write_index, new_template["mappings"]):
                    logger.info(f"Detected mapping changes for {write_index}")
                    try:
                        # 尝试更新现有索引的mapping
                        client.indices.put_mapping(index=write_index, body=new_template["mappings"])
                        logger.info(f"Successfully updated mapping for {write_index}")
                    except Exception as e:
                        logger.warning(f"Failed to update mapping: {str(e)}")
                        # 创建新索引并切换别名
                        new_index = f"{alias}-{int(time.time() * 1000)}"
                        client.indices.create(
                            index=new_index,
                            body={
                                "aliases": {alias: {"is_write_index": True}},
                                "settings": new_template["template"].get("settings", {}),
                            },
                        )
                        logger.info(f"Created new index {new_index} with updated mapping")

            # 3. 配置ILM策略（如果定义了lifecycle）
            if hasattr(cls.Index, "settings") and "lifecycle" in cls.Index.settings:
                policy_name = cls.Index.settings["lifecycle"]["name"]
                policy_body = DEFAULT_ES_ILM_POLICY_SETTINGS

                # 创建/更新策略
                client.ilm.put_lifecycle(policy=policy_name, body=policy_body)

                # 获取所有关联索引更新策略
                alias_info = client.indices.get_alias(name=alias)
                for index_name in alias_info.keys():
                    # 确保索引关联策略
                    current_settings = client.indices.get_settings(index=index_name)
                    current_policy = (
                        current_settings.get(index_name, {}).get("settings", {}).get("index", {}).get("lifecycle", {})
                    )

                    needs_update = current_policy.get("name") != policy_name or current_policy.get(
                        "rollover_alias"
                    ) != getattr(cls.Index, "ALIAS", "")

                    if needs_update:
                        update_body = {
                            "index": {
                                "lifecycle": {"name": policy_name, "rollover_alias": getattr(cls.Index, "ALIAS", "")}
                            }
                        }
                        client.indices.put_settings(index=index_name, body=update_body)
                        logger.info(f"Updated ILM policy binding for {index_name}")

        except Exception as e:
            logger.exception(f"Failed to complete setup for {cls.Index.ALIAS}, error: {e}")

    @classmethod
    def is_template_changed(cls, current: dict, new: dict) -> bool:
        """
        比较模板是否有实质性变更
        """
        # 重点关注mapping中dynamic_templates的变化
        if current.get("mappings", {}).get("dynamic_templates") != new.get("mappings", {}).get("dynamic_templates"):
            return True
        return False

    @classmethod
    def is_mapping_changed(cls, client, index_name: str, new_mapping: dict) -> bool:
        """
        比较当前mapping与新mapping是否有实质性变更
        """
        current_mapping = client.indices.get_mapping(index=index_name).get(index_name, {}).get("mappings", {})

        # 比较dynamic_templates
        if current_mapping.get("dynamic_templates") != new_mapping.get("dynamic_templates"):
            return True
        return False

    @classmethod
    def get_read_index(cls):
        index_names = (
            cls._get_connection().indices.get_alias(name=cls.Index.ALIAS, params={"request_timeout": 1}).keys()
        )
        sorted_index_names = sorted(index_names, key=LooseVersion, reverse=True)
        read_index = sorted_index_names[0]
        return read_index

    @classmethod
    def get_write_index(cls):
        """获取当前可写索引，不存在则自动创建"""
        try:
            # 获取别名信息
            alias_info = cls._get_connection().indices.get_alias(name=cls.Index.ALIAS, params={"request_timeout": 1})

            # 存在可写索引, 则返回
            for index, meta in alias_info.items():
                if meta["aliases"][cls.Index.ALIAS].get("is_write_index"):
                    return index

            # 有历史索引但无写入索引
            existing_indices = alias_info.keys()
            if existing_indices:
                # 获取最大序号索引（如resource_v1_general_document-000006）
                sorted_index_names = sorted(existing_indices, key=LooseVersion, reverse=True)
                new_index = sorted_index_names[0]
            else:
                # 完全无索引
                new_index = f"{cls.Index.ALIAS}-000001"

            # 创建新索引并设为写入索引
            cls._get_connection().indices.create(
                index=new_index,
                body={"aliases": {cls.Index.ALIAS: {"is_write_index": True}}, "settings": cls.Index.settings},
            )
            return new_index

        except Exception as e:
            logger.error(f"获取写入索引失败: {e}")
            return cls.Index.ALIAS

    @classmethod
    def _default_index(cls, index=None):
        """重写此方法避免使用通配符"""
        if index is None:
            try:
                return cls.get_read_index()
            except Exception:  # noqa
                return cls.Index.ALIAS
        return index


class CommonDocument(ESBaseDocument):
    """
    Resource es index
    抽象基类
    """

    _kind_mark: ClassVar[Kind | None] = None
    _api_version_mark: ClassVar[ApiVersion | None] = None

    _es_connection = "default"

    # 是否激活，用于标记资源是否被删除
    active = Boolean()
    kind = Keyword()
    api_version = Keyword()
    name = Keyword()
    namespace = Keyword()
    annotations = EmptySkippingObject()
    spec = EmptySkippingObject()
    status = EmptySkippingObject()

    def __init__(self, **kwargs):
        # 初始化部分数据
        now = timezone.now()
        username = get_request_username()
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        kwargs.setdefault("created_by", username)
        kwargs.setdefault("updated_by", username)
        kwargs.setdefault("namespace", "default")
        kwargs.setdefault("active", True)
        kwargs.setdefault("annotations", {})
        kwargs.setdefault("spec", {})
        kwargs.setdefault("status", {})
        super().__init__(**kwargs)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        DocumentController.register(Kind(cls._kind_mark), ApiVersion(cls._api_version_mark), cls)

    def __str__(self):
        return f"{self._api_version_mark}/{self.name}"

    def __getattr__(self, name):
        if name in ["resource", "labels"]:
            # 绕过ES DSL的查找机制，直接返回属性值
            return object.__getattribute__(self, name)
        return super().__getattr__(name)

    @property
    def labels(self):
        resource_cls = DefaultResourceRegistry.get(kind=Kind(self.kind), api_version=ApiVersion(self.api_version))
        if resource_cls is None:
            raise ValueError(f"resource<{self.kind}> has no Model imported")
        metadata_cls = resource_cls.get_field_cls("metadata")
        labels_cls = metadata_cls.get_field_cls("labels")
        label_data = {
            field: getattr(self, field) for field in labels_cls.__fields__.keys() if getattr(self, field, None)
        }
        return label_data

    @property
    def resource(self) -> Resource:
        """Convert es object to resource"""
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
                annotations=annotations_cls(**self.annotations.to_dict()),
                created_at=self.created_at,
                updated_at=self.updated_at,
                created_by=self.created_by,
                updated_by=self.updated_by,
            ),
            spec=spec_cls(**self.spec.to_dict()),
            status=status_cls(**self.status.to_dict()),
        )

    @classmethod
    def delete_by_uid(cls, uid: str) -> ResourceEvent:
        resource: CommonDocument = cls.get(id=uid)
        resource.active = False
        resource.save()
        return ResourceEvent(action=ResourceAction.Deleted, resource=resource.resource)

    @classmethod
    def apply(cls, resource: Resource) -> tuple[ResourceEvent, "CommonDocument"]:
        """Apply resource, create or update"""
        # todo 重试去掉
        resource_id = resource.metadata.uid.hex
        es_model = DocumentController.get_document(kind=resource.kind, api_version=resource.api_version)
        try:
            existed = es_model.get(id=resource_id)
            for k, v in resource.metadata.labels.dict().items():
                setattr(existed, k, v)
            existed.annotations = resource.metadata.annotations.dict()
            existed.spec = resource.spec.dict()
            existed.status = resource.status.dict()
            action = ResourceAction.Updated.value
            if not existed.active:
                existed.active = True
                existed.status = {}
                action = ResourceAction.Created.value
            existed.save()
            return ResourceEvent(action=action, resource=existed.resource), existed
        except NotFoundError:
            obj = es_model(
                meta={"id": resource.metadata.uid.hex},
                kind=str(resource.kind),
                api_version=str(resource.api_version),
                uid=resource.metadata.uid,
                name=resource.metadata.name,
                namespace=resource.metadata.namespace,
                active=True,
                annotations=resource.metadata.annotations.dict(),
                spec=resource.spec.dict(),
                status=resource.status.dict(),
                **resource.metadata.labels.dict(),
            )
            obj.save()
            return ResourceEvent(action=ResourceAction.Created, resource=obj.resource), obj
        except Exception as e:
            raise e


class DocumentController:
    generated_document: ClassVar[dict[tuple[Kind, ApiVersion], type[CommonDocument]]] = {}

    @classmethod
    def get_document(cls, kind: Kind, api_version: ApiVersion) -> type[CommonDocument] | None:
        return cls.generated_document.get((kind, api_version), GeneralDocument)

    @classmethod
    def register(cls, kind: Kind, api_version: ApiVersion, doc: type[CommonDocument]):
        """Register resource model"""
        cls.generated_document[(kind, api_version)] = doc


class GeneralDocument(CommonDocument):
    """
    通用 es 存储类
    当 Resource.store_class = "kingeye.meta.declarative_api.core.store.es_db.ESDBStore" 且
    Resource.kind 不在settings.ES_RESOURCE_STORE_CLASS 名单内时，数据存下通用索引中
    """

    _kind_mark = Kind("GeneralDocument")
    _api_version_mark = ApiVersion("v1")

    class Index:
        ALIAS = "resource_v1_general_document"
        PATTERN = ALIAS + "-*"
        settings = es_model_conf_merge(
            {
                "lifecycle": {
                    "name": ALIAS + "_policy",
                    "rollover_alias": ALIAS,
                }
            }
        )


class ResourceEventDocument(CommonDocument):
    _kind_mark = Kind("ResourceEvent")
    _api_version_mark = ApiVersion("v1")

    bk_tenant_id = Keyword()
    resource_mark = Keyword()
    resource_uid = Keyword()
    action = Keyword()
    type = Keyword()
    source = Keyword()
    event_time = Date()
    message = Text()

    class Index:
        ALIAS = "resource_v1_resource_event"
        PATTERN = ALIAS + "-*"
        settings = es_model_conf_merge(
            {
                "lifecycle": {
                    "name": ALIAS + "_policy",
                    "rollover_alias": ALIAS,
                }
            }
        )

    @classmethod
    def delete_by_uid(cls, uid: str):
        resource: ResourceEventDocument = cls.get(id=uid)
        resource.active = False
        resource.save()
        return resource.resource

    @classmethod
    def apply(cls, event: ResourceEvent) -> tuple[ResourceEvent, "ResourceEventDocument"]:
        """Apply resource, create or update"""
        if event.resource is None:
            raise ValueError("Event<%s> has no resource related", event.metadata.uid)
        # TODO 待验证
        resource_id = event.resource.metadata.uid.hex
        response = (
            cls.search().filter(Q("term", resource_uid=resource_id) & Q("term", action=event.action.value)).execute()
        )

        if len(response):
            hit = response[-1]
            doc_data = hit.to_dict()
            doc_data["meta"] = {"id": hit.meta.id}
            obj = cls(**doc_data)
        else:
            obj = cls(
                meta={"id": event.metadata.uid.hex},
                kind=str(event.kind),
                api_version=str(event.api_version),
                active=True,
                resource_uid=event.resource.metadata.uid.hex,
                resource_mark=event.resource.mark,
                uid=event.metadata.uid,
                name=event.metadata.name,
                namespace=event.metadata.namespace,
                annotations=event.metadata.annotations.dict(),
                action=event.action.value,
                type=event.type.value,
                source=event.source,
                event_time=event.event_time,
                message=event.message,
                **event.metadata.labels.dict(),
            )
            obj.save()

        return event, obj

    @property
    def resource(self) -> "ResourceEvent":
        """
        Validate a es object
        es object to Resource object
        """
        from bk_monitor_base.infras.declaratives.base import DocumentController, ResourceModelController

        # TODO resource 数据存ES、MySQL， 故查询时要先判断。后续待优化
        resource_api_version, resource_kind = self.resource_mark.split("/")
        if resource_kind in DEFAULT_USE_ES_STORE_RESOURCE:
            resource_model = DocumentController.get_document(
                kind=Kind(resource_kind), api_version=ApiVersion(resource_api_version)
            )
        else:
            resource_model = ResourceModelController.get_model(
                kind=Kind(resource_kind), api_version=ApiVersion(resource_api_version)
            )
        if resource_model is None:
            logger.warning(f"Resource model not found: {self.resource_mark}")
            # 为什么能容忍 resource 为 None
            # 因为事件作为历史可能会记录一些已经被删除的资源
            resource = None
        else:
            try:
                if isinstance(resource_model, models.Model):
                    resource_obj = resource_model.objects.get(uid=self.resource_uid)
                    resource = resource_obj.resource
                else:
                    resource_obj = resource_model.get(id=self.resource_uid)
                    resource = resource_obj.resource
            except Exception:  # noqa
                logger.info(f"query data failed: resource_model: {resource_model.__name__}")
                resource = None

        return ResourceEvent(
            metadata=ResourceEventMetadata(
                name=self.name,
                uid=self.uid,
                namespace=self.namespace,
                annotations=Annotations(**self.annotations.to_dict()),
                created_at=self.created_at,
                created_by=self.created_by,
                updated_at=self.updated_at,
                updated_by=self.updated_by,
            ),
            resource=resource,
            action=ResourceAction(self.action),
            type=EventType(self.type),
            source=self.source,
            event_time=self.event_time,
        )


class CMDBEventDocument(CommonDocument):
    _kind_mark = Kind("CMDBEvent")
    _api_version_mark = ApiVersion("v1alpha1")

    bk_object_code = Keyword()
    bk_object_inst_id = Integer()
    event_type = Keyword()

    class Index:
        ALIAS = "resource_v1alpha1_cmdb_event"
        PATTERN = ALIAS + "-*"
        settings = es_model_conf_merge(
            {
                "lifecycle": {
                    "name": ALIAS + "_policy",
                    "rollover_alias": ALIAS,
                }
            }
        )
