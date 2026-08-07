"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# MigrationRecorder —— 追踪已应用迁移的抽象接口 + 内存实现（测试用）
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Protocol


class MigrationRecorder(Protocol):
    """记录/查询各 provider 迁移状态的抽象协议。

    生产实现：DjangoMigrationRecorder（Django ORM，iam_engine/django/migration_recorder.py）
    测试实现：InMemoryRecorder（本模块）
    """

    def get_applied(self, provider: str) -> list[str]:
        """查询某 provider 已应用的迁移名列表（按应用时间升序）。

        Args:
            provider: Provider 名（如 "v4"、"v3"）。

        Returns:
            list[str]: 已应用迁移名列表（如 ["0001_initial", "0002_add_incident"]）。
        """
        ...

    def record(self, provider: str, migration: str, changes_count: int) -> None:
        """记录一条迁移已应用。

        Args:
            provider: Provider 名。
            migration: 迁移名。
            changes_count: 该迁移包含的变更数。
        """
        ...


class InMemoryRecorder:
    """内存实现，用于测试。"""

    def __init__(self) -> None:
        self._applied: dict[str, list[str]] = {}

    def get_applied(self, provider: str) -> list[str]:
        return list(self._applied.get(provider, []))

    def record(self, provider: str, migration: str, changes_count: int) -> None:
        self._applied.setdefault(provider, []).append(migration)
