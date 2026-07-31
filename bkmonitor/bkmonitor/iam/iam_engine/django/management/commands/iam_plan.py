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

import json

from django.core.management.base import BaseCommand

from bkmonitor.iam.iam_engine.django.facade import get_framework


class Command(BaseCommand):
    help = "只读：打印本地 schema 与远端 IAM 平台的差异，不执行任何变更。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", default=None, help="指定 Provider 名称；不指定则输出全部")
        parser.add_argument("--output", default=None, help="输出 JSON 文件路径")

    def handle(self, **options):
        fw = get_framework()
        provider_name = options["provider"]

        providers = [fw.providers[provider_name]] if provider_name else list(fw.providers.values())

        for provider in providers:
            plan = provider.plan_migration(fw.schema)
            if not plan.changes:
                self.stdout.write(f"[{provider.name}] no changes.")
                continue

            summary = plan.summary()
            self.stdout.write(
                f"[{provider.name}] {summary['create']} to create, "
                f"{summary['update']} to update, "
                f"{summary['delete']} to delete"
            )
            for c in plan.changes:
                prefix = {"create": "+", "update": "~", "delete": "-", "noop": " "}
                self.stdout.write(f"  {prefix[c.change_type.value]} [{c.kind.value}] {c.entity_id}")
                if c.reason:
                    self.stdout.write(f"       {c.reason}")

            if plan.has_destructive():
                self.stdout.write(
                    self.style.WARNING("  ⚠ Destructive changes detected. Use --allow-destructive to apply.")
                )

        output_path = options.get("output")
        if output_path:
            plans = [p.__dict__ for p in providers]
            with open(output_path, "w") as f:
                json.dump(plans, f, indent=2, default=str)
            self.stdout.write(f"Plan written to {output_path}")
