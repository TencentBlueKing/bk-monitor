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
# 运行时值对象（Value Objects）
#
# 本模块定义"运行时数据"，与 schema/definitions 里的"元数据"区分开：
#   - schema.definitions.ActionDef      ← 类型元数据（相当于 CREATE TABLE）
#   - schema.definitions.ResourceTypeDef ← 类型元数据
#   - core.types.Subject                ← 运行时值（谁在鉴权）
#   - core.types.ResourceInstance       ← 运行时值（哪一个资源）
#   - core.types.AuthRequest / AuthResult ← 运行时值（一次鉴权的入参/出参）
#
# 规则：
#   1. 所有类都是 frozen dataclass，禁止运行时修改
#   2. Mapping 字段用 MappingProxyType 包裹，防止外部修改字典引用
#   3. 不 import django、iam SDK、任何 provider 相关模块
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


class SubjectType(str, Enum):
    """鉴权主体类型。

    v4 平台目前只有 id 没有 type；框架层仍保留 type，
    由 v4 Provider 内部在 to_v4_subject 时丢弃，v3 Provider 保留传递。
    这样上层调用代码永远只面对一种数据结构。
    """

    USER = "user"
    DEPARTMENT = "department"


@dataclass(frozen=True)
class Subject:
    """鉴权主体（谁在请求）。

    Args:
        id: 主体唯一标识（用户名、部门 ID、服务名等）
        type: 主体类型，默认 user
        tenant_id: 多租户支持，无租户场景可留空
        attributes: 扩展属性，供 ABAC / 业务自定义 Provider 使用
    """

    id: str
    type: SubjectType = SubjectType.USER
    tenant_id: str = ""
    attributes: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class ResourceInstance:
    """资源实例。

    Args:
        type: 资源类型 ID（对应 ResourceTypeDef.id）
        id: 实例 ID
        system: 该资源所属系统（v3 需要，跨系统资源；v4 不需要）
        name: 实例展示名（用于权限申请页面）
        ancestor_chain: 祖先实例链（**是实例，含 type+id**，不是类型链）
                        v3 用于拼 _bk_iam_path_ 字符串
                        v4 用于生成 apply_url 的 ancestors 数组
        attributes: 实例属性（v3 ABAC 求值用）
    """

    type: str
    id: str
    system: str = ""
    name: str = ""
    ancestor_chain: tuple[ResourceInstance, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class AuthRequest:
    """一次鉴权请求的完整入参 —— 单 action，单 resource。

    批量场景请使用 BatchByResourceRequest / BatchByActionRequest。
    """

    subject: Subject
    action_id: str
    resource: ResourceInstance | None = None
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class AuthResult:
    """一次鉴权的返回结果。

    Args:
        allowed: 是否放行
        reason: 决策原因（供审计/日志）
        provider_name: 做出该决策的 Provider 名（组合策略中区分）
        raw: Provider 原始响应，调试用；上层不应依赖其结构
    """

    allowed: bool
    reason: str = ""
    provider_name: str = ""
    raw: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)

    @classmethod
    def allow(cls, provider_name: str = "", reason: str = "") -> AuthResult:
        return cls(allowed=True, reason=reason, provider_name=provider_name)

    @classmethod
    def deny(cls, provider_name: str = "", reason: str = "") -> AuthResult:
        return cls(allowed=False, reason=reason, provider_name=provider_name)


# ---------------------------------------------------------------------------
# 批量鉴权 —— 请求 / 结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceAuthResult:
    """针对某个 (action_id, resource) 组合的鉴权结果。

    用于批量接口的行级返回：Provider 返回一批 (resource_id, allowed) 结果，
    上层可按 resource_id 匹配回原始 ResourceInstance 使用。
    """

    action_id: str
    resource_type: str
    resource_id: str
    allowed: bool


@dataclass(frozen=True)
class BatchByResourceRequest:
    """批量鉴权（同 action、多 resource）请求。

    Provider 内部完成分片（如 v4 可每批 20），调用方无感知；
    """

    subject: Subject
    action_id: str
    resources: tuple[ResourceInstance, ...] = ()
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class BatchByActionRequest:
    """批量鉴权（多 action、同 resource 或无 resource）请求。"""

    subject: Subject
    action_ids: tuple[str, ...] = ()
    resource: ResourceInstance | None = None
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class BatchAuthResult:
    """批量鉴权的整体返回。

    items 保序：与请求中的 (action_id, resource) 顺序一致，
    调用方可通过下标或 (action_id, resource_id) 匹配。
    """

    items: tuple[ResourceAuthResult, ...] = ()

    def allowed_resource_ids(self, action_id: str = "") -> list[str]:
        """便捷方法：返回 allowed=True 的 resource_id 列表。

        Args:
            action_id: 若指定，仅筛选该 action 的结果；空串表示不过滤
        """
        return [
            item.resource_id for item in self.items if item.allowed and (not action_id or item.action_id == action_id)
        ]


# ---------------------------------------------------------------------------
# 权限申请 URL 请求
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyURLRequest:
    """生成"跳转到权限申请页"的 URL 请求。

    典型场景：接口返回 403 + apply_url，前端引导用户点击去权限中心申请。
    """

    subject: Subject
    action_ids: tuple[str, ...] = ()
    resources: tuple[ResourceInstance, ...] = ()
