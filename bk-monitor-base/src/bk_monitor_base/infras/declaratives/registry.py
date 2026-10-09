from dataclasses import dataclass, field
from typing import ClassVar

from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Resource


@dataclass
class ResourceRegistry:
    resources: dict[tuple[Kind, ApiVersion], type[Resource]] = field(default_factory=dict)  # type: ignore

    default: ClassVar["ResourceRegistry"]

    def register(self, resource: type[Resource]):
        """Register resource"""
        self.resources[(resource.kind, resource.api_version)] = resource

    def get(self, kind: Kind, api_version: ApiVersion) -> type[Resource] | None:
        """Get resource by kind and api_version"""
        return self.resources.get((kind, api_version))

    def keys(self) -> list[tuple[Kind, ApiVersion]]:
        """Get all keys"""
        return list(self.resources.keys())

    def filter_by_kinds(self, kinds: list[Kind]) -> list[type[Resource]]:
        """Filter resources by kinds"""
        return [resource for resource in self.resources.values() if resource.kind in kinds]

    def all(self) -> list[type[Resource]]:
        """Get all resources"""
        return list(self.resources.values())

    def topics(self, kinds: list[Kind]) -> list[str]:
        """Get topics by kinds"""
        if not kinds:
            return [f"{key[0]}-{key[1]}" for key in list(self.resources.keys())]
        else:
            return [f"{key[0]}-{key[1]}" for key in list(self.resources.keys()) if key[0] in kinds]

    # Implementing the magic methods
    # making class act like a dictionary
    # -------------------------------
    def __iter__(self):
        return iter(self.resources.values())

    def __len__(self):
        return len(self.resources)

    def __contains__(self, mark: tuple[Kind, ApiVersion]):
        return mark in self.resources

    def __getitem__(self, mark: tuple[Kind, ApiVersion]) -> type[Resource]:
        return self.resources[mark[0], mark[1]]

    def __setitem__(self, mark: tuple[Kind, ApiVersion], resource: type[Resource]):
        self.register(resource)

    def __delitem__(self, mark: tuple[Kind, ApiVersion]):
        del self.resources[mark]


ResourceRegistry.default = ResourceRegistry()
DefaultResourceRegistry = ResourceRegistry.default
