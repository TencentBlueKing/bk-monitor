from dataclasses import dataclass

from django.db import models

from bk_monitor_base.infras.declaratives import Resource, ResourceEvent
from bk_monitor_base.infras.declaratives.definitions import DEFAULT_NAMESPACE

model_registry: dict[type[Resource], models.Model] = {}


def register_app_model(resource_cls: type[Resource], model_cls: models.Model):
    """Register app model"""
    model_registry[resource_cls] = model_cls


@dataclass
class AppDBStore:
    """Kingeye App DB Store"""

    resource_cls: type[Resource]
    resource: Resource | None = None

    def get(self, uid: str) -> Resource:
        """Get resource"""
        raise NotImplementedError()

    def list(
        self,
        namespace: str = DEFAULT_NAMESPACE,
        page: int = 0,
        page_size: int = 10,
        common_filter: dict | None = None,
        label_filter: dict | None = None,
    ) -> list[Resource]:
        """List resources"""
        raise NotImplementedError()

    def apply(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> "ResourceEvent":
        """Apply resource"""
        raise NotImplementedError()

    def delete(self, source: str | None = None, silence: bool = False, ignore_self: bool = False) -> None:
        """Delete resource"""
        raise NotImplementedError()

    @property
    def model(self) -> models.Model:
        """Get model"""
        return model_registry[self.resource_cls]
