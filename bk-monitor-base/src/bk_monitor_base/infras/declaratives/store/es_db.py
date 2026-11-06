import builtins
from dataclasses import dataclass
from uuid import UUID

from django.db import models
from elasticsearch_dsl import Q

from bk_monitor_base.infras.declaratives import Resource, ResourceEvent
from bk_monitor_base.infras.declaratives.base import CommonDocument, DocumentController
from bk_monitor_base.infras.declaratives.constants import ES_QUERY_MAX_VALUE, ThreadLocalKey
from bk_monitor_base.infras.declaratives.definitions import DEFAULT_NAMESPACE, EVENT_KIND
from bk_monitor_base.infras.declaratives.store import BaseStore
from bk_monitor_base.infras.threading.local import get_local_param


@dataclass
class ESStore(BaseStore):
    """ES DB Store"""

    DEFAULT_QUERY_FIELD = [
        "kind",
        "api_version",
        "uid",
        "name",
        "namespace",
        "active",
        "resource_mark",
        "resource_uid",
        "action",
        "type",
        "source",
    ]

    def _get_target_es_model(self) -> type[CommonDocument]:
        """Get target es model"""
        return DocumentController.get_document(kind=self.resource_cls.kind, api_version=self.resource_cls.api_version)

    def get(self, uid: UUID) -> Resource:
        """Get resource"""
        es_model_cls = self._get_target_es_model()
        if isinstance(uid, UUID):
            uid = uid.hex
        return es_model_cls.get(id=uid).resource

    def list(
        self,
        page: int = 0,
        page_size: int = 10,
        namespace: str = DEFAULT_NAMESPACE,
        common_filter: dict | None = None,
        label_filter: dict | None = None,
        status_filter: dict | None = None,
    ) -> list[Resource]:
        """List resources"""
        condition = Q("term", namespace=namespace) & Q("term", active=True)
        allowed_operators = {"in", "exact"}

        if common_filter:
            common_filter.pop("labels", None)
            condition = self._apply_filters(
                condition=condition,
                filters=common_filter,
                allowed_operators=allowed_operators,
                query_field=self.DEFAULT_QUERY_FIELD,
            )

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
        es_model = self._get_target_es_model()
        response = es_model.search().filter(condition).extra(size=ES_QUERY_MAX_VALUE).execute()
        objs = []
        for hit in response:
            doc_data = hit.to_dict()
            doc_data["meta"] = {"id": hit.meta.id}
            objs.append(es_model(**doc_data))

        return [x.resource for x in objs]

    def apply(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> "ResourceEvent":
        """Apply resource"""
        if source is None:
            source = get_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, "")

        if self.resource is None:
            raise ValueError("Resource is None, apply should be called by resource instance")
        event, _ = self._get_target_es_model().apply(self.resource)
        # 事件本身不应该被重复记录
        if self.resource.kind == EVENT_KIND:
            return event

        event.source = source  # type: ignore
        event.ignore_self = ignore_self
        if not silence:
            self.record_event(event)
        return event

    def delete(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> None:
        """Delete resource"""
        if source is None:
            source = get_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, "")
        if self.resource is None:
            raise ValueError("Resource is None, delete should be called by resource instance")

        event = self._get_target_es_model().delete_by_uid(self.resource.metadata.uid.hex)
        # 事件本身不应该被重复记录
        if self.resource.kind == EVENT_KIND:
            return

        event.source = source  # type: ignore
        event.ignore_self = ignore_self
        if not silence:
            self.record_event(event)
        return

    @property
    def model(self) -> models.Model:
        """Get model"""
        raise NotImplementedError()

    def _apply_filters(
        self,
        condition: Q,
        filters: dict | None,
        allowed_operators: set,
        is_flattened: bool = True,
        fields_path: str = "",
        query_field: builtins.list[str] = None,
    ) -> Q:
        """Apply filters to query condition"""
        if not filters:
            return condition
        model_cls = self._get_target_es_model()

        _cls = self.resource_cls
        for attr in fields_path.split("."):
            if not attr:
                continue
            func = _cls.get_field_cls
            _cls = func.__call__(attr)
        exist_fields = _cls.__fields__

        if query_field:
            exist_fields = query_field

        for k, v in filters.items():
            parts = k.split("__")
            field = parts[0]
            op = parts[-1] if len(parts) > 1 else "exact"

            if field in exist_fields:
                raw_field = field
                if not is_flattened:
                    # 没有展平的字段取全路径，如 status.xxx
                    field = f"{fields_path}.{field}"

                if op in allowed_operators:
                    if op == "in" and not isinstance(v, list):
                        raise ValueError(f"Value for {k} must be a list")
                    if op == "in" and isinstance(v, list):
                        condition &= Q("terms", **{field: v})
                    elif op == "exact":
                        condition &= Q("term", **{field: v})
                else:
                    raise ValueError(f"Operator {op} not supported for field {raw_field}")
            else:
                raise ValueError(f"{model_cls.__name__} does not have {k} field")
        return condition
