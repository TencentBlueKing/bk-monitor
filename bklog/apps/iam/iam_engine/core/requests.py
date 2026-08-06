from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol


class IdentifiedDefinition(Protocol):
    id: str


DefinitionRef = IdentifiedDefinition | str


def to_definition_id(definition: DefinitionRef) -> str:
    if isinstance(definition, str):
        return definition
    return definition.id


def _empty_mapping() -> Mapping[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Subject:
    id: str
    type: str = "user"
    tenant_id: str = ""
    attributes: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class ResourceInstance:
    type: DefinitionRef
    id: str
    system: str = ""
    name: str = ""
    ancestor_chain: tuple[ResourceInstance, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class AuthRequest:
    subject: Subject
    action_id: DefinitionRef
    resources: tuple[ResourceInstance, ...] = ()
    environment: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True, slots=True)
class BatchAuthRequest:
    subject: Subject
    action_ids: tuple[DefinitionRef, ...]
    resource_groups: tuple[tuple[ResourceInstance, ...], ...]
    environment: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        resource_groups = tuple(tuple(group) for group in self.resource_groups)
        if any(not group for group in resource_groups):
            raise ValueError("resource group must not be empty")
        object.__setattr__(self, "action_ids", tuple(self.action_ids))
        object.__setattr__(self, "resource_groups", resource_groups)
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))

    def iter_keys(self):
        for resource_group in self.resource_groups:
            resource_id = str(resource_group[0].id)
            for action_id in self.action_ids:
                yield to_definition_id(action_id), resource_id
