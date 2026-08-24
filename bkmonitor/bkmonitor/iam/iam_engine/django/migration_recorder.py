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
# DjangoMigrationRecorder — 基于 Django 数据库后端的迁移状态记录器
# ---------------------------------------------------------------------------

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import re
from collections.abc import Iterator

from django.db import DatabaseError, connections, models, transaction
from django.utils import timezone
from django.utils.connection import ConnectionDoesNotExist

_APP_LABEL = __package__.rsplit(".", 1)[0].replace(".", "_")
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,47}$")


class DjangoMigrationRecorder:
    """基于数据库的迁移状态记录器。

    每个 Provider 独立追踪各自的迁移进度。
    状态表与锁表在首次访问时由 Django schema editor 创建，因此不依赖
    MySQL 专属 DDL，也可以通过 database/table_name 隔离不同 IAM 实例。
    """

    _models: dict[str, tuple[type[models.Model], type[models.Model]]] = {}
    _ensured_tables: set[tuple[str, str]] = set()

    def __init__(self, *, database: str = "default", table_name: str = "iam_migration_state") -> None:
        if not isinstance(database, str) or not database:
            raise ValueError("database must be a non-empty Django database alias")
        if not isinstance(table_name, str) or not _TABLE_NAME_RE.fullmatch(table_name):
            raise ValueError(
                "table_name must be a database identifier containing letters, digits, and underscores, "
                "starting with a letter or underscore and no longer than 48 characters"
            )
        try:
            connections[database]
        except ConnectionDoesNotExist as exc:
            raise ValueError(f"Unknown Django database alias: {database!r}") from exc

        self.database = database
        self.table_name = table_name
        self._state_model, self._lock_model = self._get_models(table_name)

    def get_applied(self, provider: str) -> list[str]:
        """查询某 provider 已应用的迁移名列表（按应用时间升序）。"""
        self._ensure_tables()
        return list(
            self._state_model.objects.using(self.database)
            .filter(provider=provider)
            .order_by("applied_at", "id")
            .values_list("migration", flat=True)
        )

    def record(self, provider: str, migration: str, changes_count: int) -> None:
        """记录一条迁移已应用；重复记录同一迁移时保持幂等。"""
        self._ensure_tables()
        self._state_model.objects.using(self.database).get_or_create(
            provider=provider,
            migration=migration,
            defaults={"changes_count": changes_count},
        )

    @contextmanager
    def lock(self, name: str = "iam_engine_migration") -> Iterator[None]:
        """在整个迁移执行期间持有数据库锁，避免多进程并发写远端模型。"""
        self._ensure_tables()
        if not name or len(name) > 128:
            raise ValueError("lock name must contain 1 to 128 characters")

        lock_objects = self._lock_model.objects.using(self.database)
        with transaction.atomic(using=self.database):
            lock_objects.get_or_create(name=name)
            # 除 select_for_update 外再执行一次写入，SQLite 等不支持行锁的后端
            # 也会在事务期间持有写锁。
            lock_objects.filter(name=name).update(touched_at=timezone.now())
            lock_objects.select_for_update().get(name=name)
            yield

    @classmethod
    def _get_models(cls, table_name: str) -> tuple[type[models.Model], type[models.Model]]:
        cached = cls._models.get(table_name)
        if cached is not None:
            return cached

        digest = hashlib.sha1(table_name.encode()).hexdigest()[:10]
        state_meta = type(
            "Meta",
            (),
            {
                "app_label": _APP_LABEL,
                "db_table": table_name,
                "managed": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("provider", "migration"),
                        name=f"iam_migration_{digest}_uniq",
                    )
                ],
            },
        )
        state_model = type(
            f"IamMigrationState_{digest}",
            (models.Model,),
            {
                "__module__": __name__,
                "id": models.BigAutoField(primary_key=True),
                "provider": models.CharField(max_length=32),
                "migration": models.CharField(max_length=128),
                "changes_count": models.IntegerField(default=0),
                "applied_at": models.DateTimeField(auto_now_add=True),
                "Meta": state_meta,
            },
        )

        lock_meta = type(
            "Meta",
            (),
            {
                "app_label": _APP_LABEL,
                "db_table": f"{table_name}_lock",
                "managed": False,
            },
        )
        lock_model = type(
            f"IamMigrationLock_{digest}",
            (models.Model,),
            {
                "__module__": __name__,
                "name": models.CharField(primary_key=True, max_length=128),
                "touched_at": models.DateTimeField(auto_now=True),
                "Meta": lock_meta,
            },
        )
        cls._models[table_name] = (state_model, lock_model)
        return state_model, lock_model

    def _ensure_tables(self) -> None:
        for model in (self._state_model, self._lock_model):
            cache_key = (self.database, model._meta.db_table)
            if cache_key in self._ensured_tables:
                continue
            self._ensure_model_table(model)
            self._ensured_tables.add(cache_key)

    def _ensure_model_table(self, model: type[models.Model]) -> None:
        connection = connections[self.database]
        table_name = model._meta.db_table
        if table_name in connection.introspection.table_names():
            return
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(model)
        except DatabaseError:
            # 并发启动时其他进程可能刚刚建好表；重新检查后仅在仍缺表时抛出。
            if table_name not in connection.introspection.table_names():
                raise
