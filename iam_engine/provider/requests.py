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
#   - core.requests.Subject                ← 运行时值（谁在鉴权）
#   - core.requests.ResourceInstance       ← 运行时值（哪一个资源）
#   - core.requests.AuthRequest / core.types.AuthResult ← 运行时值（一次鉴权的入参/出参）
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
from typing import TYPE_CHECKING, Any
from iam_engine.core.requests import DefinitionRef, Subject, ResourceInstance

if TYPE_CHECKING:
    from ..schema.definitions import ActionDef

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


def to_action_id(action: DefinitionRef) -> str:
    """Normalize action reference to string ID."""
    if isinstance(action, str):
        return action
    if hasattr(action, "id"):
        return action.id
    raise TypeError(f"Expected ActionDef or str, got {type(action).__name__}")


def to_resource_type_id(rt: DefinitionRef) -> str:
    """Normalize resource type reference to string ID."""
    if isinstance(rt, str):
        return rt
    if hasattr(rt, "id"):
        return rt.id
    raise TypeError(f"Expected ResourceTypeDef or str, got {type(rt).__name__}")


class SubjectType(str, Enum):
    """鉴权主体类型。

    v4 平台目前只有 id 没有 type；框架层仍保留 type，
    由 v4 Provider 内部在 to_v4_subject 时丢弃，v3 Provider 保留传递。
    这样上层调用代码永远只面对一种数据结构。
    """

    USER = "user"
    DEPARTMENT = "department"


@dataclass(frozen=True)
class AuthRequest:
    """一次鉴权请求的完整入参 —— 单 action，单 resource。

    批量场景请使用 BatchByResourceRequest / BatchByActionRequest。
    """

    subject: Subject
    action_id: ActionDef | str
    resource: ResourceInstance | None = None
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


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
    action_id: ActionDef | str
    resources: tuple[ResourceInstance, ...] = ()
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class BatchByActionRequest:
    """批量鉴权（多 action、同 resource 或无 resource）请求。"""

    subject: Subject
    action_ids: tuple[ActionDef | str, ...] = ()
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


@dataclass(frozen=True)
class VisibleResult:
    """可见资源过滤结果（反向列举消费方的统一返回）。

    由 Provider.filter_visible_resources 返回；多 Provider 组合时框架负责合并。

    Args:
        all_granted: 候选所在父链下全部实例可见（如 v3 的整 space 授权）。
                     为 True 时 visible_ids 可忽略。
        visible_ids: 具体可见的实例 ID（业务命名）。
    """

    all_granted: bool = False
    visible_ids: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# 权限申请 URL 请求
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyURLRequest:
    """生成"跳转到权限申请页"的 URL 请求。

    典型场景：接口返回 403 + apply_url，前端引导用户点击去权限中心申请。
    """

    subject: Subject
    action_ids: tuple[ActionDef | str, ...] = ()
    resources: tuple[ResourceInstance, ...] = ()
