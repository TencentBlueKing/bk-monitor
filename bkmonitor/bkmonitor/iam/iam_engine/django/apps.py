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

from django.apps import AppConfig, apps

from ..django.conf import load_framework
from .migration_logging import summarize_system_migration

logger = logging.getLogger("iam_engine.django")


def _log_system_migration(plan, report) -> None:
    """记录已 reconcile 的系统迁移结果，供 semi_auto 路径使用。"""
    migration_log = summarize_system_migration(plan, report, dry_run=False)
    log = logger.error if migration_log.is_error else logger.info
    log("iam_engine migration: %s", migration_log.summary)
    for detail in migration_log.details:
        log("iam_engine migration: %s", detail)


class IamEngineConfig(AppConfig):
    """iam_engine Django 集成入口。

    注册到 INSTALLED_APPS 时填写本包的 Django 路径。

    启动流程：
        1. AppConfig.ready() 触发 load_framework()
        2. load_framework() 读 settings.IAM_FRAMEWORK → 构建 IAMFramework
        3. 根据 MIGRATION.MODE 决定是否自动执行 schema 迁移
    """

    name = __package__
    label = __package__.rsplit(".", 1)[0].replace(".", "_")
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
        """根据 MIGRATION.MODE 决定自动迁移行为。

        支持的模式（与老版本 _migrate_iam 钩子的模式对齐）：
          * "manual"    —— 完全手动，需要显式跑 iam_engine_migrate 命令
          * "semi_auto" —— 挂 Django post_migrate 信号，跟随 `manage.py migrate` 触发；
                           破坏性变更由 MIGRATION.allow_destructive 显式控制

        破坏性变更（DELETE / 方言 id 变更重建）统一由 MIGRATION.allow_destructive
        单一开关控制，与 CLI 的 --allow-destructive 语义完全对齐；默认 False。
        """
        from django.conf import settings

        raw = getattr(settings, "IAM_FRAMEWORK", {})
        migration_cfg = raw.get("MIGRATION", {})
        mode = migration_cfg.get("mode", "manual")

        if mode == "manual":
            return

        if mode == "semi_auto":
            from django.db.models.signals import post_migrate

            migration_database = migration_cfg.get("database", "default")

            def run_auto_migration(**kwargs) -> None:
                if kwargs.get("using", "default") != migration_database:
                    return
                self._run_auto_migration(fw, migration_cfg)

            # Django 只会为存在 models_module 的 App 发送 post_migrate。
            # iam_engine.django 自身没有 models.py，因此沿用老版迁移的可靠触发边界：
            # 监听主 bkmonitor App 的 post_migrate，再由本 App 执行新引擎迁移。
            post_migrate.connect(
                run_auto_migration,
                sender=apps.get_app_config("bkmonitor"),
                dispatch_uid="iam_engine auto migration",
                weak=False,
            )
            return

        logger.warning(
            "iam_engine: unknown MIGRATION.mode=%r, treated as manual (supported modes: manual, semi_auto)",
            mode,
        )

    def _run_auto_migration(self, fw, migration_cfg: dict) -> None:
        # 进程内幂等：同一进程只跑一次自动迁移（防 runserver autoreload / 测试重复触发）
        if self._migration_done:
            return
        self._migration_done = True

        self._do_auto_migration(fw, migration_cfg)

    def _do_auto_migration(self, fw, migration_cfg: dict) -> None:
        allow_destructive = migration_cfg.get("allow_destructive", False)

        from ..migration.loader import MigrationLoader
        from ..migration.planner import MigrationPlanner
        from ..schema.diff import MigrationPlan

        directory = migration_cfg.get("directory", "")
        from ..django.migration_recorder import DjangoMigrationRecorder

        recorder = DjangoMigrationRecorder(
            database=migration_cfg.get("database", "default"),
            table_name=migration_cfg.get("table_name", "iam_migration_state"),
        )
        with recorder.lock("iam_engine_auto_migration"):
            for provider in fw.providers.values():
                try:
                    # ① 系统迁移：plan_migration(scope="system") → apply_migration
                    plan = provider.plan_migration(fw.schema, scope="system")
                    report = provider.apply_migration(plan, dry_run=False, allow_destructive=allow_destructive)
                    _log_system_migration(plan, report)

                    # ② 文件迁移：本地迁移文件 → apply_migration
                    if not directory:
                        continue

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
