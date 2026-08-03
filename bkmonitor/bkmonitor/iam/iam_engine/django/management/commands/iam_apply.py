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

from django.core.management.base import BaseCommand

from ....django.facade import get_framework


class Command(BaseCommand):
    help = "应用 schema 变更到远端 IAM 平台。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", required=True, help="Provider 名称")
        parser.add_argument("--dry-run", action="store_true", default=False, help="只预演不执行")
        parser.add_argument("--allow-destructive", action="store_true", default=False, help="允许破坏性变更")

    def handle(self, **options):
        fw = get_framework()
        provider_name = options["provider"]
        dry_run = options["dry_run"]
        allow_destructive = options["allow_destructive"]

        provider = fw.providers.get(provider_name)
        if provider is None:
            self.stderr.write(f"Provider {provider_name!r} not found.")
            return

        plan = provider.plan_migration(fw.schema)
        if not plan.changes:
            self.stdout.write("No changes to apply.")
            return

        if plan.has_destructive() and not allow_destructive:
            self.stderr.write(self.style.ERROR("Destructive changes detected. Use --allow-destructive to apply."))
            return

        report = provider.apply_migration(
            plan,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )

        label = "Would apply (dry-run)" if dry_run else "Applied"
        if report.would_apply:
            self.stdout.write(f"{label}: {len(report.would_apply)} change(s)")
        if report.applied:
            self.stdout.write(f"Applied: {len(report.applied)} change(s)")
        if report.failed:
            self.stderr.write(f"Failed: {len(report.failed)} change(s)")
            for change, error in report.failed:
                self.stderr.write(f"  - {change.entity_id}: {error}")
        if report.skipped_reason:
            self.stdout.write(f"Skipped: {report.skipped_reason}")

        self.stdout.write(f"Elapsed: {report.elapsed_seconds:.1f}s")
