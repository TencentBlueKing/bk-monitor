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
# DjangoMigrationRecorder — 基于数据库的迁移状态记录器
# ---------------------------------------------------------------------------

from __future__ import annotations

from django.db import connection


class DjangoMigrationRecorder:
    """基于数据库的迁移状态记录器。

    每个 Provider 独立追踪各自的迁移进度。
    表 iam_migration_state 在首次访问时自动创建（幂等）。
    """

    _TABLE = "iam_migration_state"
    _table_checked = False

    def get_applied(self, provider: str) -> list[str]:
        """查询某 provider 已应用的迁移名列表（按应用时间升序）。"""
        self._ensure_table()
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT migration FROM {self._TABLE} WHERE provider = %s ORDER BY applied_at",
                [provider],
            )
            return [row[0] for row in cursor.fetchall()]

    def record(self, provider: str, migration: str, changes_count: int) -> None:
        """记录一条迁移已应用。"""
        self._ensure_table()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {self._TABLE} (provider, migration, changes_count) VALUES (%s, %s, %s)",
                [provider, migration, changes_count],
            )

    @classmethod
    def _ensure_table(cls) -> None:
        """首次调用时检查并创建追踪表（幂等）。"""
        if cls._table_checked:
            return
        with connection.cursor() as cursor:
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {cls._TABLE} (
                    id INTEGER AUTO_INCREMENT PRIMARY KEY,
                    provider VARCHAR(32) NOT NULL,
                    migration VARCHAR(128) NOT NULL,
                    changes_count INTEGER NOT NULL DEFAULT 0,
                    applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    UNIQUE KEY uq_provider_migration (provider, migration)
                )"""
            )
        cls._table_checked = True
