import builtins
from typing import Any
from uuid import UUID

from django.db import models
from typing_extensions import Protocol

from bk_monitor_base.infras.declaratives.definitions import DEFAULT_NAMESPACE, Resource, ResourceEvent  # noqa


class ResourceStore(Protocol):
    """Resource Store Protocol"""

    def get(self, uid: UUID | str | None = None, show_inactive: bool = False, **filters: dict) -> Resource:
        """Get resource"""
        raise NotImplementedError()

    def list(
        self,
        namespace: str = DEFAULT_NAMESPACE,
        page: int = 0,
        page_size: int = 10,
        common_filter: dict | None = None,
        label_filter: dict | None = None,
        status_filter: dict | None = None,
        spec_filter: dict[str, Any] | None = None,
        #  强制关键字参数标志，后面的参数只能以关键字传参
        *,
        lazy: bool = False,
        show_deleting: bool = False,
        show_inactive: bool = False,
    ) -> list[Resource]:
        """List resources"""
        raise NotImplementedError()

    def apply(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> "ResourceEvent":
        """Apply resource"""
        raise NotImplementedError()

    def bulk_apply(
        self,
        resources: builtins.list[Resource],
        source: str | None = None,
        silence: bool = False,
        ignore_self: bool = False,
    ) -> "ResourceEvent":
        """Batch apply resource"""
        raise NotImplementedError()

    def delete(self, source: str | None = None, silence: bool = False, mode=None) -> None:
        """Delete resource"""
        raise NotImplementedError()

    def delete_by_two_phase(self):
        raise NotImplementedError()

    @property
    def model(self) -> models.Model:
        """Get model"""
        raise NotImplementedError()
