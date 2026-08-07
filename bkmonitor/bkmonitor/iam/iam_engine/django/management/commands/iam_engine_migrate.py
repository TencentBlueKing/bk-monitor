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
# iam_migrate — 系统迁移 + 文件迁移
#
# 流程（每个 provider）：
#   ① plan_migration(fw.schema) → 仅取 SYSTEM 变更 → apply — 系统信息远端 diff
#   ② 迁移文件 → 未应用的按依赖序 apply → 记录 DB — 本地文件迁移
# ---------------------------------------------------------------------------

from __future__ import annotations


from django.core.management.base import BaseCommand

from ....django.facade import get_framework
from ....django.migration_recorder import DjangoMigrationRecorder
from ....migration.loader import MigrationLoader
from ....migration.planner import MigrationPlanner
from ....schema.diff import ChangeType, EntityKind, MigrationPlan


class Command(BaseCommand):
    help = "应用 IAM schema 迁移：系统信息（远端 diff）+ 迁移文件（本地）。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", default=None, help="Provider 名（如 v4）；不指定则全部执行")
        parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
        parser.add_argument("--skip-system", action="store_true", help="跳过系统迁移前置步骤")
        parser.add_argument(
            "--directory",
            default=None,
            help="迁移文件目录（默认从 provider options.migration_directory 读取）",
        )

    def handle(self, **options):
        fw = get_framework()
        provider_filter = options["provider"]
        dry_run = options["dry_run"]
        skip_system = options["skip_system"]
        recorder = DjangoMigrationRecorder()

        providers = [fw.get_provider(provider_filter)] if provider_filter else list(fw.providers.values())

        for provider in providers:
            # ── ① 系统迁移 ──
            if not skip_system:
                self._migrate_system(provider, fw, dry_run)

            # ── ② 文件迁移 ──
            directory = self._get_directory(options, provider)
            if not directory:
                self.stdout.write(f"[{provider.name}] no migration_directory configured, skipping file migration.")
                continue

            loader = MigrationLoader(directory)
            planner = MigrationPlanner(loader, recorder, provider.name)

            try:
                pending = planner.get_pending()
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[{provider.name}] planner error: {e}"))
                continue

            if not pending:
                self.stdout.write(self.style.SUCCESS(f"[{provider.name}] all file migrations applied."))
                continue

            self.stdout.write(f"[{provider.name}] {len(pending)} file migration(s) pending:")
            for m in pending:
                self.stdout.write(f"  {m.name} ({len(m.operations)} change(s))")

            for migration in pending:
                plan = MigrationPlan(provider_name=provider.name, changes=list(migration.operations))
                report = provider.apply_migration(
                    plan,
                    dry_run=dry_run,
                    allow_destructive=False,
                )

                if dry_run:
                    self.stdout.write(
                        f"  [{provider.name}] {migration.name}: would apply {len(report.would_apply)} change(s)"
                    )
                elif report.success:
                    recorder.record(provider.name, migration.name, changes_count=len(report.applied))
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{provider.name}] {migration.name}: applied {len(report.applied)} change(s)"
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.ERROR(
                            f"  [{provider.name}] {migration.name}: "
                            f"{len(report.failed)} failure(s), skipped={report.skipped_reason}"
                        )
                    )
                    break

    # ------------------------------------------------------------------
    # 系统迁移
    # ------------------------------------------------------------------

    def _migrate_system(self, provider, fw, dry_run: bool) -> None:
        """对比远端系统信息并应用变更。

        调 provider.plan_migration()，只取其中 kind=SYSTEM 的变更来 apply。
        NOOP 时跳过，无需 DB 记录。
        """
        try:
            plan = provider.plan_migration(fw.schema)
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"[{provider.name}] system plan failed: {e}"))
            return

        system_changes = [c for c in plan.changes if c.kind == EntityKind.SYSTEM and c.change_type != ChangeType.NOOP]
        if not system_changes:
            self.stdout.write(f"[{provider.name}] system: no changes.")
            return

        self.stdout.write(f"[{provider.name}] system: {len(system_changes)} change(s)")
        for c in system_changes:
            self.stdout.write(f"  {c.change_type.value} system: {c.reason}")

        if not dry_run:
            system_plan = MigrationPlan(provider_name=provider.name, changes=system_changes)
            report = provider.apply_migration(system_plan, dry_run=False, allow_destructive=False)
            if report.success:
                self.stdout.write(self.style.SUCCESS(f"  [{provider.name}] system: applied."))
            else:
                self.stderr.write(self.style.ERROR(f"  [{provider.name}] system: {len(report.failed)} failure(s)"))

    # ------------------------------------------------------------------

    @staticmethod
    def _get_directory(options: dict, provider) -> str:
        directory = options.get("directory")
        if directory:
            return directory
        from django.conf import settings

        raw = getattr(settings, "IAM_FRAMEWORK", {})
        return raw.get("MIGRATION", {}).get("directory", "")
