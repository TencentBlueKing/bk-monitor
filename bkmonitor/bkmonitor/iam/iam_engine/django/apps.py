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

import logging

from django.apps import AppConfig

from ..django.conf import load_framework

logger = logging.getLogger("iam_engine.django")


class IamEngineConfig(AppConfig):
    """iam_engine Django 集成入口。

    注册到 INSTALLED_APPS：
        INSTALLED_APPS = [
            ...
            "bkmonitor.iam.iam_engine.django",
        ]

    启动流程：
        1. AppConfig.ready() 触发 load_framework()
        2. load_framework() 读 settings.IAM_FRAMEWORK → 构建 IAMFramework
        3. 根据 MIGRATION.MODE 决定是否自动执行 schema 迁移
    """

    name = "bkmonitor.iam.iam_engine.django"
    label = "iam_engine"
    verbose_name = "IAM Engine"

    _framework_loaded = False
    _migration_done = False

    def ready(self) -> None:
        if self._framework_loaded:
            return
        self._framework_loaded = True

        fw = load_framework()
        logger.info("iam_engine framework loaded: %d provider(s)", len(fw.providers))

        self._maybe_auto_migrate(fw)

    def _maybe_auto_migrate(self, fw) -> None:
        """根据 MIGRATION.MODE 决定自动迁移行为。"""
        from django.conf import settings

        raw = getattr(settings, "IAM_FRAMEWORK", {})
        migration_cfg = raw.get("MIGRATION", {})
        mode = migration_cfg.get("mode", "manual")

        if mode == "manual":
            return

        if mode in ("auto", "auto_full"):
            self._run_auto_migration(fw, migration_cfg)
        elif mode == "semi_auto":
            from django.db.models.signals import post_migrate

            post_migrate.connect(
                lambda **kw: self._run_auto_migration(fw, migration_cfg),
                sender=self,
            )

    def _run_auto_migration(self, fw, migration_cfg: dict) -> None:
        # 进程内幂等：同一进程只跑一次自动迁移（防 runserver autoreload / 测试重复触发）
        if self._migration_done:
            return
        self._migration_done = True

        # 多副本互斥：DB advisory lock 保证同一时刻只有一个 Pod/Worker 执行
        if not _acquire_migration_lock():
            logger.info("iam_engine auto migration skipped — another process is already running it")
            return

        try:
            self._do_auto_migration(fw, migration_cfg)
        finally:
            _release_migration_lock()

    def _do_auto_migration(self, fw, migration_cfg: dict) -> None:
        allow_destructive = migration_cfg.get("allow_destructive", False) or migration_cfg.get("mode") == "auto_full"

        from ..migration.loader import MigrationLoader
        from ..migration.planner import MigrationPlanner
        from ..schema.diff import MigrationPlan

        directory = migration_cfg.get("directory", "")
        recorder = None

        for provider in fw.providers.values():
            try:
                # ① 系统迁移：plan_migration(scope="system") → apply_migration
                plan = provider.plan_migration(fw.schema, scope="system")
                report = provider.apply_migration(plan, dry_run=False, allow_destructive=allow_destructive)
                if report.applied:
                    logger.info("iam_engine migration: %s system — %d applied", provider.name, len(report.applied))

                # ② 文件迁移：本地迁移文件 → apply_migration
                if not directory:
                    continue

                if recorder is None:
                    from ..django.migration_recorder import DjangoMigrationRecorder

                    recorder = DjangoMigrationRecorder()

                loader = MigrationLoader(directory)
                planner = MigrationPlanner(loader, recorder, provider.name)
                pending = planner.get_pending()

                if not pending:
                    continue

                logger.info("iam_engine migration: %s file — %d pending", provider.name, len(pending))
                for migration in pending:
                    file_plan = MigrationPlan(provider_name=provider.name, changes=list(migration.operations))
                    report = provider.apply_migration(file_plan, dry_run=False, allow_destructive=allow_destructive)
                    if report.success:
                        recorder.record(provider.name, migration.name, changes_count=len(report.applied))
                        logger.info(
                            "iam_engine migration: %s %s — %d applied",
                            provider.name,
                            migration.name,
                            len(report.applied),
                        )
                    else:
                        logger.error(
                            "iam_engine migration: %s %s — %d failed, skipped=%s",
                            provider.name,
                            migration.name,
                            len(report.failed),
                            report.skipped_reason,
                        )
                        break
            except Exception:
                logger.exception(
                    "iam_engine auto migration failed for provider=%s",
                    provider.name,
                )


# ---------------------------------------------------------------------------
# 多副本互斥：DB advisory lock
# ---------------------------------------------------------------------------

_ACQUIRE_LOCK = "SELECT GET_LOCK('iam_migrate_auto', 0)"
_RELEASE_LOCK = "SELECT RELEASE_LOCK('iam_migrate_auto')"


def _acquire_migration_lock() -> bool:
    """尝试获取迁移互斥锁。返回 True 表示获取成功。"""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(_ACQUIRE_LOCK)
        return cursor.fetchone()[0] == 1


def _release_migration_lock() -> None:
    """释放迁移互斥锁。"""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(_RELEASE_LOCK)
