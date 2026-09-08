from typing import ClassVar

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import gettext_lazy as _

from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.declaratives.definitions import (
    EVENT_KIND,
    PACKAGE_VERSION,
    Annotations,
    ApiVersion,
    EventType,
    Kind,
    ResourceAction,
    ResourceEvent,
    ResourceEventMetadata,
)
from bk_monitor_base.infras.declaratives.logger import logger

from .resource import ResourceManager, ResourceModel


class EventModelManager(ResourceManager):
    def delete_by_uid(self, uid: str) -> ResourceEvent:
        try:
            resource: EventModel = self.get(uid=uid)
        except ObjectDoesNotExist:
            logger.exception(f"Failed to find resource in db: {uid}")
            raise

        resource.active = False
        resource.save(update_fields=["active", "updated_at"])

        return resource.resource

    def apply(self, event: ResourceEvent) -> tuple[ResourceEvent, "EventModel"]:
        """Apply resource, create or update"""
        if event.resource is None:
            raise ValueError("Event<%s> has no resource related", event.metadata.uid)

        try:
            db_obj = self.get(
                resource_uid=event.resource.metadata.uid, action=event.action, event_time=event.event_time
            )
        except ObjectDoesNotExist:
            db_obj = self.create(
                kind=event.kind,
                api_version=event.api_version,
                resource_uid=event.resource.metadata.uid,
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

        return event, db_obj


class EventModel(ResourceModel):
    """Event DB Model"""

    _kind_mark = Kind(EVENT_KIND)
    _api_version_mark = ApiVersion(PACKAGE_VERSION)

    bk_tenant_id = models.CharField(max_length=255, null=True, default=DEFAULT_TENANT_ID)
    resource_mark = models.CharField(max_length=128, verbose_name="资源标识")
    resource_uid = models.UUIDField(verbose_name=_("资源 UID"))
    action = models.CharField(max_length=64, choices=ResourceAction.get_choices(), db_index=True)
    type = models.CharField(max_length=64, choices=EventType.get_choices(), default=EventType.Normal, db_index=True)
    # 事件来源，用来标注事件发生的组件
    # controller 发起某个资源更新后会再次从 watch 流中拿到对应事件
    # 这种情况下应该通过 source 字段，忽略由自己产生的事件
    source = models.CharField(max_length=128, verbose_name=_("来源"), db_index=True)
    # 事件发生时间，microsecond
    event_time = models.DateTimeField(_("更新时间"), auto_now_add=True)
    # 事件消息，一般用于扩展描述事件信息，比如资源更新失败的原因
    message = models.TextField(verbose_name="描述信息")

    objects: ClassVar[EventModelManager] = EventModelManager()

    class Meta:
        unique_together = ("resource_uid", "action", "event_time")
        db_table = f"core_{PACKAGE_VERSION}_event"
        app_label = "kingeye_meta_core"

    @property
    def resource(self) -> "ResourceEvent":
        """Validate a db object

        DB object to Resource object
        """
        from bk_monitor_base.infras.declaratives.base import ResourceModelController

        resource_api_version, resource_kind = self.resource_mark.split("/")
        resource_model = ResourceModelController.get_model(
            kind=Kind(resource_kind), api_version=ApiVersion(resource_api_version)
        )
        if resource_model is None:
            logger.warning(f"Resource model not found: {self.resource_mark}")
            # 为什么能容忍 resource 为 None
            # 因为事件作为历史可能会记录一些已经被删除的资源
            resource = None
        else:
            resource_obj = resource_model.objects.get(uid=self.resource_uid)
            resource = resource_obj.resource

        return ResourceEvent(
            metadata=ResourceEventMetadata(
                name=self.name,
                uid=self.uid,
                namespace=self.namespace,
                annotations=Annotations(**self.annotations),
            ),
            resource=resource,
            action=ResourceAction(self.action),
            type=EventType(self.type),
            source=self.source,
            event_time=self.event_time,
        )
