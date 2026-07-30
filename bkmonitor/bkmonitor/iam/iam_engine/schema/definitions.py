"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema 元数据定义（Metadata Definitions）
#
# 本模块定义"权限模型元数据"，与 core.types 里的"运行时值"严格区分：
#   - ActionDef / ResourceTypeDef / RoleDef / SystemDef  ← 元数据（本模块）
#   - Subject / ResourceInstance / AuthRequest         ← 运行时值（core.types）
#
# 规则：
#   1. 所有类都是 frozen dataclass；tuple 而非 list，防止外部改引用
#   2. 只依赖标准库，不依赖 django / SDK / core.types
#   3. 业务侧可以继承这些类扩展字段（例如 v3 的 type/version），
#      但基础字段是 Provider 的最小契约
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class SystemDef:
    """接入系统的元数据（每个 Provider 各持一份）。

    不同 IAM 平台对系统的描述字段不同（v3 用 provider_config.host 存回调地址、
    v4 用顶层 callback_url），此处按"并集"设计，Provider 各取所需。

    Args:
        id: 系统唯一标识（如 "bk_monitor"）
        name: 系统展示名（中文名）
        description: 系统描述
        managers: 管理员用户名列表（v4 特有）
        clients: 允许调用该系统权限的蓝鲸应用列表（v4 特有）
        callback_url: 回调地址（v3 塞进 provider_config.host，v4 塞进 callback_url）
        extensions: 各 Provider 的私有字段（如 v3 的 provider_config 其它键）
    """

    id: str
    name: str
    description: str = ""
    managers: tuple[str, ...] = ()
    clients: tuple[str, ...] = ()
    callback_url: str = ""
    extensions: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class ResourceTypeDef:
    """资源类型元数据（"space 是什么样的一种资源"）。

    Args:
        id: 资源类型 ID（如 "space"、"apm_application"）
        name: 中文名（权限中心后台展示用）
        ancestor: 直接父级资源类型 ID；空串表示顶级资源。
                  完整祖先链由 SchemaRegistry.resolve_ancestor_types() 递归得到。
        description: 描述
        extensions: 各 Provider 私有字段（如 v3 的 selection_mode /
                    related_instance_selections）
    """

    id: str
    name: str
    ancestor: str = ""
    description: str = ""
    extensions: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class ActionDef:
    """操作元数据（"view_business 这个动作是什么"）。

    Args:
        id: 操作 ID（如 "view_business"）
        name: 中文名
        resource_type: 关联的资源类型 ID；空字符串表示无关资源类型
                       v4 只能关联一个（本字段的直接映射）
                       v3 支持关联多个 → 由业务侧继承本类扩展 related_resource_types
        description: 描述
        extensions: 各 Provider 私有字段（如 v3 的 type/version/related_actions）

    工业级规范：
        - 每个 action 只关联单一 resource_type，符合 v4 现代 RBAC 模型
        - 如需 v3 的多资源类型语义，业务侧继承 ActionDef 扩展字段，
          v3 Provider 在适配层读取该扩展字段
    """

    id: str
    name: str
    resource_type: str = ""
    description: str = ""
    extensions: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class RoleActionBinding:
    """角色与操作的绑定关系。

    v4 RBAC 模型中，action 的授权粒度（resource_type_id）在**角色层面**定义，
    称为"授权维度"。同一 action 在不同角色里可以关联不同的资源类型
    （必须是 action 自身 resource_type 或其祖先）。

    Args:
        action_id: 操作 ID
        resource_type: 授权维度；空表示无关资源类型的授权
    """

    action_id: str
    resource_type: str = ""


@dataclass(frozen=True)
class RoleDef:
    """角色元数据（v4 RBAC 独有；v3 无此概念，v3 Provider 会忽略）。

    Args:
        id: 角色 ID
        name: 中文名
        description: 描述
        actions: 该角色包含的 (action_id, resource_type) 绑定列表
        extensions: 各 Provider 私有字段
    """

    id: str
    name: str
    description: str = ""
    actions: tuple[RoleActionBinding, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)
