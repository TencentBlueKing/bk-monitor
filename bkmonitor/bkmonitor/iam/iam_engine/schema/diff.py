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
# Migration 变更数据类型
#
# 这些类型是 Provider.plan_migration / apply_migration 契约的输入输出。
# 纯数据对象，不包含业务逻辑。遵循 core/types.py 的风格：
#   - frozen dataclass + Mapping 用 MappingProxyType 包裹
#   - 枚举用 str, Enum
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


# ---- 变更类型 ----


class ChangeType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NOOP = "noop"


class EntityKind(str, Enum):
    SYSTEM = "system"
    ACTION = "action"
    RESOURCE_TYPE = "resource_type"
    ROLE = "role"


# ---- 单条变更 ----


@dataclass(frozen=True)
class Change:
    """描述本地 schema 与远端 IAM 平台之间的一条差异。

    Attributes:
        kind: 实体类型
        change_type: 变更操作
        entity_id: 实体唯一标识
        before: 变更前状态（dict，新创建时为 None）
        after: 变更后状态（dict，删除时为 None）
        reason: 变更原因（供 review / audit）
        destructive: 是否为破坏性变更（删除、字段收窄等）
    """

    kind: EntityKind
    change_type: ChangeType
    entity_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str = ""
    destructive: bool = False


# ---- 计划与报告 ----


@dataclass
class MigrationPlan:
    """一个 Provider 的完整迁移计划。

    Provider.plan_migration(schema) 生成此对象。
    Provider.apply_migration(plan, ...) 消费此对象。

    Attributes:
        provider_name: Provider 标识
        changes: 变更列表
        metadata: Provider 私有透传数据
    """

    provider_name: str
    changes: list[Change] = field(default_factory=list)
    metadata: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)

    def summary(self) -> dict[str, int]:
        """按类型统计变更数量。"""
        counts: dict[str, int] = {"create": 0, "update": 0, "delete": 0, "noop": 0}
        for c in self.changes:
            counts[c.change_type.value] = counts.get(c.change_type.value, 0) + 1
        return counts

    def has_destructive(self) -> bool:
        """是否包含破坏性变更。apply 时若未显式 allow_destructive 会被阻断。"""
        return any(c.destructive for c in self.changes)


@dataclass
class MigrationReport:
    """迁移执行结果报告。

    Attributes:
        provider_name: Provider 标识
        started_at: 开始时间
        finished_at: 结束时间
        applied: 已成功应用的变更
        would_apply: dry-run 模式下的预执行变更
        failed: 失败的变更及错误信息
        skipped_reason: 跳过原因（如多副本锁竞争）
    """

    provider_name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    applied: list[Change] = field(default_factory=list)
    would_apply: list[Change] = field(default_factory=list)
    failed: list[tuple[Change, str]] = field(default_factory=list)
    skipped_reason: str = ""

    @property
    def success(self) -> bool:
        """全部变更成功（0 失败且非跳过）。"""
        return len(self.failed) == 0 and not self.skipped_reason

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()
