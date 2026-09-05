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
# Dialect* —— Provider 内部的"方言命名"运行时结构
#
# 与 core.types 里的运行时值（Subject/ResourceInstance/AuthRequest/...）严格区分：
#   - core.types.*       ← 业务规范化命名（iam_engine 及以上层可见）
#   - dialect_types.*    ← 平台方言命名（仅 Provider 内部流转，供方言方法使用）
#
# 由 PermissionProvider 基类在"公共接口方法"中，通过 NameCodec 将 core.types
# 结构逐字段 encode 为对应的 Dialect* 结构，再交给子类实现的方言方法处理。
# 子类拿到 Dialect* 就可以直接使用（.id / .type / .action_id 都是方言值），
# 不需要再感知 codec 的存在。
#
# 规则：
#   1. 所有类都是 frozen dataclass，禁止修改
#   2. 不 import django / SDK / Provider 相关模块
#   3. 字段命名与 core.types 对应结构保持一致，仅"值域"从规范化名 → 方言名
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ..core.types import Subject

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class DialectResource:
    """编码后的资源（type/id/ancestors 均为方言命名）。

    Args:
        type: 方言资源类型 ID
        id: 方言资源实例 ID
        ancestors: 方言祖先实例链
    """

    type: str
    id: str
    ancestors: tuple[DialectResource, ...] = ()


@dataclass(frozen=True)
class DialectAuthRequest:
    """编码后的单次鉴权请求。"""

    subject: Subject
    action_id: str
    resource: DialectResource | None = None
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class DialectBatchByResourceRequest:
    """编码后的批量鉴权（同 action、多 resource）请求。

    resource_type 单独提取（同一批共享），resource_ids 只承载方言 ID 列表，
    供只认裸 ID 的平台（如 v3）使用；resources 承载完整方言资源（含祖先链），
    供需要构造 _bk_iam_path_ 等完整路径的平台（如 v4）使用。
    """

    subject: Subject
    action_id: str
    resource_type: str
    resource_ids: tuple[str, ...] = ()
    resources: tuple[DialectResource, ...] = ()
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class DialectBatchByActionRequest:
    """编码后的批量鉴权（多 action、同 resource 或无 resource）请求。"""

    subject: Subject
    action_ids: tuple[str, ...] = ()
    resource: DialectResource | None = None
    environment: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class DialectApplyURLRequest:
    """编码后的申请 URL 请求。

    resources 中的 type/id/ancestors 均已按 codec 编码为方言值。
    action_ids 同样已是方言 ID。
    """

    subject: Subject
    action_ids: tuple[str, ...] = ()
    resources: tuple[DialectResource, ...] = ()


__all__ = [
    "DialectApplyURLRequest",
    "DialectAuthRequest",
    "DialectBatchByActionRequest",
    "DialectBatchByResourceRequest",
    "DialectResource",
]
