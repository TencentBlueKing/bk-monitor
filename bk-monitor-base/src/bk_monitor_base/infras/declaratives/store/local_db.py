import builtins
import time
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.db.models import Model, Q, QuerySet
from django.utils import timezone

from bk_monitor_base.infras.declaratives import Resource, ResourceAction, ResourceEvent
from bk_monitor_base.infras.declaratives.base import ResourceModel, ResourceModelController
from bk_monitor_base.infras.declaratives.constants import ThreadLocalKey
from bk_monitor_base.infras.declaratives.definitions import DEFAULT_NAMESPACE, EVENT_KIND, DeleteStatus
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.declaratives.metrics import API_SERVER_APPLY_COUNT, API_SERVER_DELETE_COUNT
from bk_monitor_base.infras.declaratives.store import BaseStore, DeleteMode
from bk_monitor_base.infras.threading.local import get_local_param


@dataclass
class LocalDBStore(BaseStore):
    """Local DB Store"""

    def _get_target_model(self) -> type[ResourceModel]:
        """Get target model"""
        model = ResourceModelController.get_model(
            kind=self.resource_cls.kind, api_version=self.resource_cls.api_version
        )
        if model is None:
            raise ValueError("Model not found for resource<%s>", self.resource_cls)
        return model

    def get(self, uid: UUID | str | None = None, show_inactive: bool = False, **filters) -> Resource | None:
        """Get resource by uid or filters. Delegates filter validation to the model."""
        condition = Q()
        if not show_inactive:
            condition &= Q(active=True)

        model_cls = self._get_target_model()

        if uid is not None and "uid" not in filters:
            if not isinstance(uid, UUID | str):
                raise ValueError("Only uid in UUID or UUID.hex format are supported")
            filters["uid"] = uid

        if not filters:
            raise ValueError("At least one query condition must be provided")

        # 调用模型的校验逻辑
        if hasattr(self.resource_cls, "validate_filters"):
            self.resource_cls.validate_filters(filters)

        condition &= Q(**filters)
        return model_cls.objects.get(condition).resource

    def list(
        self,
        namespace: str = DEFAULT_NAMESPACE,
        page: int = 0,
        page_size: int = 10,
        common_filter: dict | None = None,
        label_filter: dict | None = None,
        status_filter: dict | None = None,
        spec_filter: dict | None = None,
        #  强制关键字参数标志，后面的参数只能以关键字传参
        *,
        lazy: bool = False,
        show_deleting: bool = False,
        show_inactive: bool = False,
    ) -> list[Resource] | Iterator:
        """List resources"""
        model_cls = self._get_target_model()
        condition = Q(namespace=namespace)
        allowed_operators = {"in", "exact"}

        if not show_inactive:
            condition &= Q(active=True)

        if common_filter:
            common_filter.pop("labels", None)
            condition &= Q(**common_filter)

        # Apply status and label filters
        condition = self._apply_filters(
            condition=condition,
            filters=label_filter,
            allowed_operators=allowed_operators,
            fields_path="metadata.labels",
        )

        condition = self._apply_filters(
            condition=condition,
            filters=status_filter,
            allowed_operators=allowed_operators,
            is_flattened=False,
            fields_path="status",
        )

        if not show_deleting:
            condition &= self._remove_deleting_resource_Q()

        db_objs = model_cls.objects.filter(condition)
        if lazy:
            return (obj.resource for obj in db_objs.iterator())
        else:
            return [x.resource for x in db_objs]

    def apply(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> "ResourceEvent":
        """Apply resource"""
        if source is None:
            source = get_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, "")

        if self.resource is None:
            raise ValueError("Resource is None, apply should be called by resource instance")

        event, _ = self._get_target_model().objects.apply(self.resource)
        API_SERVER_APPLY_COUNT.labels(resource_type=self.resource.kind, operation_type=event.action).inc()
        # 事件本身不应该被重复记录
        if self.resource.kind == EVENT_KIND:
            return event

        event.source = source  # pyright:ignore
        event.ignore_self = ignore_self
        if not silence:
            start_record = time.time()
            self.record_event(event)
            logger.debug(
                "event<%s> push to kafka cost: %.6f seconds", self.resource.metadata.name, time.time() - start_record
            )

        return event

    def bulk_apply(
        self,
        resources: builtins.list[Resource],
        source: str | None = None,
        silence: bool = False,
        ignore_self: bool = False,
    ) -> builtins.list[ResourceEvent]:
        """Bulk apply resources"""
        if not resources:
            return []

        if source is None:
            source = get_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, "")

        model_cls = self._get_target_model()

        with transaction.atomic():
            # 区分需要创建和更新的资源
            existing_resources = self._get_existing_resources(resources)
            to_create, to_update, to_recreate = self._categorize_resources(resources, list(existing_resources))

            logger.debug("going to create %d resources: %s", len(to_create), [str(c) for c in to_create])
            logger.debug("going to update %d resources: %s", len(to_update), [str(u) for u in to_update])
            logger.debug("going to recreate %d resources: %s", len(to_recreate), [str(u) for u in to_recreate])
            # 批量数据库操作
            created_objs = model_cls.objects.bulk_create(to_create, batch_size=100)
            self._bulk_update_resources(to_update + to_recreate)

            # 生成事件记录
            events = []

            # 处理新建资源事件
            for obj in created_objs + to_recreate:
                event = ResourceEvent(action=ResourceAction.Created, resource=obj.resource)
                if event:
                    events.append(event)

            # 处理更新资源事件
            for obj in to_update:
                event = ResourceEvent(action=ResourceAction.Updated, resource=obj.resource)
                if event:
                    events.append(event)

        start_record = time.time()
        for event in events:
            if event.resource.kind == EVENT_KIND:
                continue

            event.source = source  # type: ignore
            event.ignore_self = ignore_self
            if not silence:
                self.record_event(event)

        if not silence:
            logger.debug(
                "bulk apply %d events push to kafka cost: %.6f seconds", len(events), time.time() - start_record
            )

        return events

    def _get_existing_resources(self, resources: builtins.list["Resource"]) -> QuerySet[ResourceModel]:
        """获取已存在的资源"""
        if not resources:
            return self._get_target_model().objects.none()

        identifiers = [r.metadata.uid for r in resources if r.metadata.uid]
        names = [r.metadata.name for r in resources if r.metadata.name]
        return self._get_target_model().objects.filter(Q(uid__in=identifiers) | Q(name__in=names))

    def _categorize_resources(
        self, resources: builtins.list[Resource], existing: builtins.list[ResourceModel]
    ) -> tuple[builtins.list[ResourceModel], builtins.list[ResourceModel], builtins.list[ResourceModel]]:
        """分类资源到创建/更新列表
        返回创建资源列表、更新资源列表、重建资源列表
        1. 创建资源列表中的资源通过 create 方法落库，发送 Created 事件
        2. 更新资源列表中的资源通过 update 方法落库，发送 Updated 事件
        3. 重建资源列表中的资源通过 update 方法落库，发送 Created 事件
        """
        # 建立映射
        existing_by_uid = {r.uid: r for r in existing}
        existing_by_name = {(r.namespace, r.name): r for r in existing}

        to_create = []
        to_update = []
        to_recreate = []
        now = timezone.now()
        for resource in resources:
            resource_db = self._get_target_model()(
                kind=resource.kind,
                api_version=resource.api_version,
                uid=resource.metadata.uid,
                name=resource.metadata.name,
                namespace=resource.metadata.namespace,
                annotations=resource.metadata.annotations.dict(),
                spec=resource.spec.dict(),
                status=resource.status.dict(),
                updated_at=now,
                **resource.metadata.labels.dict(),
            )

            if resource.metadata.uid and resource.metadata.uid in existing_by_uid:
                to_update.append(resource_db)
            elif (resource.metadata.namespace, resource.metadata.name) in existing_by_name:
                # 容灾机制，如果新建了重名资源，应该走更新逻辑并且保留原有的 uid、kind 等字段
                logger.warning("[local_db] %s 在数据库中重名，我们将更新数据库", resource)
                existing_model = existing_by_name[(resource.metadata.namespace, resource.metadata.name)]
                resource_db.uid = existing_model.uid
                if existing_model.active:
                    to_update.append(resource_db)
                else:
                    to_recreate.append(resource_db)
            else:
                to_create.append(resource_db)
        return to_create, to_update, to_recreate

    def _bulk_update_resources(self, resources: builtins.list):
        if not resources:
            return None
        update_fields = ["spec", "status", "annotations", "active", "updated_at", "updated_by"]
        update_fields.extend(resources[0].labels)
        return self._get_target_model().objects.bulk_update(resources, update_fields)

    def delete_by_two_phase(self, silence: bool = False):
        """使用2阶段删除"""
        return self.delete(mode=DeleteMode.PREPARE_PHASE, silence=silence)

    def delete(
        self,
        source: str | None = None,
        silence: bool = False,
        ignore_self: bool = False,
        mode: DeleteMode = DeleteMode.DIRECT,
    ) -> None:
        """
        :param mode: 包括 DIRECT（默认）， PREPARE_PHASE 和 COMMIT_PHASE
            DIRECT： 直接删除资源， 可以选择是否发送事件，但不保证删除事件被正确处理。
            PREPARE_PHASE： 两阶段删除的准备阶段，标记资源为DELETING状态，发送删除事件
            COMMIT_PHASE： 两阶段删除的提交阶段，标记资源为DELETED状态，终止后续流程，结束资源的生命周期
        """
        if self.resource is None:
            raise ValueError("Resource is None, delete should be called by resource instance")

        if mode == DeleteMode.DIRECT:
            self.direct_delete(source, silence, ignore_self)
        elif mode == DeleteMode.PREPARE_PHASE:
            self.resource.status.delete_status = DeleteStatus.DELETING
            event, _ = self._get_target_model().objects.update(self.resource)
            if not silence:
                event.action = ResourceAction.Deleted
                self.record_event(event)
        elif mode == DeleteMode.COMMIT_PHASE:
            self.resource.status.delete_status = DeleteStatus.DELETED
            self._get_target_model().objects.update(self.resource)
            self.direct_delete(silence=True)
        else:
            raise ValueError(f"Delete mode: {mode} is illegal must be DIRECT, PREPARE_PHASE or COMMIT_PHASE")

    def direct_delete(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> None:
        """Delete resource"""
        if source is None:
            source = get_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, "")
        if self.resource is None:
            raise ValueError("Resource is None, delete should be called by resource instance")

        event = self._get_target_model().objects.delete_by_uid(self.resource.metadata.uid.hex)
        API_SERVER_DELETE_COUNT.labels(resource_type=self.resource.kind, operation_type=event.action).inc()
        # 事件本身不应该被重复记录
        if self.resource.kind == EVENT_KIND:
            return

        event.source = source  # pyright:ignore
        event.ignore_self = ignore_self
        if not silence:
            self.record_event(event)
        return

    @property
    def model(self) -> Model:
        """Get model"""
        raise NotImplementedError()

    def _apply_filters(
        self,
        condition: Q,
        filters: dict | None,
        allowed_operators: set,
        is_flattened: bool = True,
        fields_path: str = "",
    ) -> Q:
        """Apply filters to query condition"""
        if not filters:
            return condition
        model_cls = self._get_target_model()

        _cls = self.resource_cls
        for attr in fields_path.split("."):
            func = _cls.get_field_cls
            _cls = func.__call__(attr)
        exist_fields = _cls.__fields__

        for k, v in filters.items():
            parts = k.split("__")
            field = parts[0]
            op = parts[-1] if len(parts) > 1 else "exact"

            if field in exist_fields:
                raw_field = field
                if not is_flattened:
                    # 没有展平的字段取全路径，如 status.xxx
                    field = f"{fields_path}__{field}"

                if op in allowed_operators:
                    if op == "in" and not isinstance(v, list):
                        raise ValueError(f"Value for {k} must be a list")
                    condition &= Q(**{f"{field}__{op}": v})
                else:
                    raise ValueError(f"Operator {op} not supported for field {raw_field}")
            else:
                raise ValueError(f"{model_cls.__name__} does not have {k} field")
        return condition

    @classmethod
    def _remove_deleting_resource_Q(cls) -> Q:
        """排除正在两阶段删除中的结果"""
        deleting_status = Q(status__has_key="delete_status") & (
            Q(status__delete_status=DeleteStatus.DELETED.value) | Q(status__delete_status=DeleteStatus.DELETING.value)
        )
        return ~deleting_status
