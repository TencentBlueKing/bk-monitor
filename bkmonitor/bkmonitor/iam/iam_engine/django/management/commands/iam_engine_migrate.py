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
#   ① plan_migration(scope="system") → apply_migration — 系统注册/更新
#   ② 迁移文件 → 未应用的按依赖序 apply_migration — 资源/操作/角色
#
# apply_migration 内部负责查远端、reconcile、执行。
# ---------------------------------------------------------------------------

from __future__ import annotations


from django.core.management.base import BaseCommand

from ....django.facade import get_framework
from ....django.migration_recorder import DjangoMigrationRecorder
from ....migration.loader import MigrationLoader
from ....migration.planner import MigrationPlanner
from ....schema.diff import MigrationPlan


class Command(BaseCommand):
    help = "应用 IAM schema 迁移：系统注册 + 迁移文件。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", default=None, help="Provider 名（如 v4）；不指定则全部执行")
        parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
        parser.add_argument("--skip-system", action="store_true", help="跳过系统迁移前置步骤")
        parser.add_argument(
            "--allow-destructive",
            action="store_true",
            help="允许破坏性变更（DELETE / 方言 id 变更重建）；默认禁止，含破坏性变更的计划会被跳过或报错",
        )
        parser.add_argument(
            "--directory",
            default=None,
            help="迁移文件目录（默认从 IAM_FRAMEWORK.MIGRATION.directory 读取）",
        )

    def handle(self, **options):
        fw = get_framework()
        provider_filter = options["provider"]
        dry_run = options["dry_run"]
        skip_system = options["skip_system"]
        allow_destructive = options["allow_destructive"]
        recorder = DjangoMigrationRecorder()

        providers = [fw.get_provider(provider_filter)] if provider_filter else list(fw.providers.values())

        for provider in providers:
            # ── ① 系统迁移 ──
            if not skip_system:
                self._migrate_system(provider, fw, dry_run, allow_destructive)

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
                    allow_destructive=allow_destructive,
                )

                if dry_run:
                    self.stdout.write(
                        f"  [{provider.name}] {migration.name}: would apply {len(report.would_apply)} change(s)"
                    )
                elif report.success:
                    recorder.record(provider.name, migration.name, changes_count=len(report.applied))
                    # skipped 按原因分组展示（remote_exists / no_platform_concept 等）
                    skipped_text = ""
                    if report.skipped:
                        reasons: dict[str, int] = {}
                        for _c, reason in report.skipped:
                            reasons[reason] = reasons.get(reason, 0) + 1
                        detail = ", ".join(f"{count} {reason}" for reason, count in sorted(reasons.items()))
                        skipped_text = f", skipped {len(report.skipped)} ({detail})"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{provider.name}] {migration.name}: "
                            f"applied {len(report.applied)} change(s){skipped_text}"
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.ERROR(
                            f"  [{provider.name}] {migration.name}: "
                            f"{len(report.failed)} failure(s), skipped={report.skipped_reason}"
                        )
                    )
                    # 逐条打印失败详情（含异常类型），便于定位平台拒绝/校验错误
                    for actual, error in report.failed:
                        self.stderr.write(
                            self.style.ERROR(
                                f"    - {actual.kind.value} {actual.change_type.value} {actual.entity_id}: {error}"
                            )
                        )
                    break

    # ------------------------------------------------------------------
    # 系统迁移
    # ------------------------------------------------------------------

    def _migrate_system(self, provider, fw, dry_run: bool, allow_destructive: bool = False) -> None:
        """系统注册/更新。

        plan_migration(scope="system") 生成系统计划（纯本地），
        apply_migration 查远端、reconcile、按需 create/update。
        """
        try:
            plan = provider.plan_migration(fw.schema, scope="system")
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"[{provider.name}] system plan failed: {e}"))
            return

        report = provider.apply_migration(plan, dry_run=dry_run, allow_destructive=allow_destructive)

        if report.success:
            if report.applied:
                self.stdout.write(
                    self.style.SUCCESS(f"[{provider.name}] system: applied {len(report.applied)} change(s).")
                )
            elif report.would_apply:
                self.stdout.write(f"[{provider.name}] system: would apply {len(report.would_apply)} change(s).")
            else:
                self.stdout.write(f"[{provider.name}] system: no changes.")
        else:
            self.stderr.write(self.style.ERROR(f"[{provider.name}] system: {len(report.failed)} failure(s)"))

    # ------------------------------------------------------------------

    @staticmethod
    def _get_directory(options: dict, provider) -> str:
        directory = options.get("directory")
        if directory:
            return directory
        from django.conf import settings

        raw = getattr(settings, "IAM_FRAMEWORK", {})
        return raw.get("MIGRATION", {}).get("directory", "")
