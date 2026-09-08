from prometheus_client import CollectorRegistry

from .definitions.event import ResourceAction, ResourceEvent
from .definitions.resource import ApiVersion, Kind, Resource

# 指标采集注册表定义
DECLARATIVE_API_REGISTRY = CollectorRegistry()

__all__ = [
    "Resource",
    "ApiVersion",
    "Kind",
    "ResourceEvent",
    "ResourceAction",
    "DECLARATIVE_API_REGISTRY",
]
