# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

手动触发自定义指标链路巡检。

    python manage.py link_health_check                # 跟 settings.LINK_HEALTH_AUTOREMEDIATE
    python manage.py link_health_check --dry-run      # 仅检测
    python manage.py link_health_check --remediate    # 强制开启自愈
    python manage.py link_health_check --json         # JSON 输出
"""
import json

from django.core.management.base import BaseCommand

from metadata.task.diagnostics import run_health_check


class Command(BaseCommand):
    help = "运行一次链路健康巡检（transfer → metadata → BMW broker → 路由 redis → unify-query → InfluxDB）"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--dry-run", action="store_true", help="仅检测不修复")
        group.add_argument("--remediate", action="store_true", help="强制开启自愈，覆盖 settings")
        parser.add_argument("--json", action="store_true", help="以 JSON 输出报告")

    def handle(self, *args, **options):
        dry_run = None
        if options["dry_run"]:
            dry_run = True
        elif options["remediate"]:
            dry_run = False

        summary = run_health_check(dry_run=dry_run)

        if options["json"]:
            self.stdout.write(json.dumps(summary, default=str, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            "link_health: issues=%s fixed=%s failed=%s dry_run=%s elapsed=%.3fs"
            % (
                summary["issue_total"],
                summary["fix_total"],
                summary["fix_failed"],
                summary["dry_run_total"],
                summary["elapsed_seconds"],
            )
        )
        for stage, stat in summary["stage_stats"].items():
            self.stdout.write(f"  - {stage}: {stat}")
        for issue in summary["issues"]:
            self.stdout.write(f"  ! {issue['stage']}/{issue['code']} scope={issue['scope']} detail={issue['detail']}")
