from __future__ import annotations

# ---------------------------------------------------------------------------
# 引擎入参（普通话）
#
# 方言编码发生在 backends/v3|v4 的 codec，不在本模块。
# Mapping 字段用 MappingProxyType 冻住，避免请求在并发两侧被原地改属性。
# ---------------------------------------------------------------------------

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol


class IdentifiedDefinition(Protocol):
    id: str


class ResourceTypeDefinition(IdentifiedDefinition, Protocol):
    system_id: str


class ActionDefinition(IdentifiedDefinition, Protocol):
    related_resource_types: Sequence[ResourceTypeDefinition]


DefinitionRef = IdentifiedDefinition | str


def to_definition_id(definition: DefinitionRef) -> str:
    """把 ActionEnum / ResourceMeta / 字符串统一成 id，供指标 label 和 codec 使用。"""

    if isinstance(definition, str):
        return definition
    return definition.id


def _empty_mapping() -> Mapping[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Subject:
    """鉴权主体。V4 网关目前主要认 id + tenant；type 留给 V3 SDK 和未来 ABAC。"""

    id: str
    type: str = "user"
    tenant_id: str = ""
    attributes: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class ResourceInstance:
    """资源实例。type/id 用业务命名；V4 的 neg_ 编码、V3 的 _v2 后缀都在 codec 里做。"""

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
    """单次鉴权入参：一个主体 + 一个动作 + 一组关联资源。"""

    subject: Subject
    action_id: DefinitionRef
    resources: tuple[ResourceInstance, ...] = ()
    environment: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True, slots=True)
class BatchAuthRequest:
    """批量鉴权入参。每个 resource_group 非空，第一项的 id 作为结果字典的资源键。

    当前按「同一业务下的一批资源 × 一批动作」使用；ModeRouter 整批只解析一次鉴权模式。
    """

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
