"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# Safely inspect or regenerate LLM titles for explicitly selected Issues.

import json

from django.core.management.base import BaseCommand, CommandError

from alarm_backends.service.fta_action.tasks import issue_tasks


MAX_ISSUES = 20


class Command(BaseCommand):
    help = "检查或补偿指定 Issue 的 LLM 标题（显式小批量、串行执行）"

    def add_arguments(self, parser):
        parser.add_argument("--bk-biz-id", type=int, required=True, help="业务 ID")
        parser.add_argument(
            "--issue-id",
            action="append",
            required=True,
            help=f"Issue ID，可重复传入；去重后最多 {MAX_ISSUES} 个",
        )
        parser.add_argument(
            "--operator",
            required=True,
            help="发起人标识；execute 时非 system 值写入 NAME_CHANGE content 审计，dry-run 仅校验非空",
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="只检查资格，不调用 LLM、不修改标题")
        mode.add_argument("--execute", action="store_true", help="按输入顺序串行执行安全补偿")

    def handle(self, *args, **options):
        issue_ids = list(dict.fromkeys(issue_id.strip() for issue_id in options["issue_id"] if issue_id.strip()))
        if not issue_ids:
            raise CommandError("至少需要一个非空 --issue-id")
        if len(issue_ids) > MAX_ISSUES:
            raise CommandError(f"单次最多允许 {MAX_ISSUES} 个不同的 Issue")

        operator = options["operator"].strip()
        if not operator:
            raise CommandError("--operator 不能为空")

        bk_biz_id = options["bk_biz_id"]
        mode = "dry_run" if options["dry_run"] else "execute"
        safe_count = 0
        success_count = 0
        failed_count = 0
        result_counts: dict[str, int] = {}

        for issue_id in issue_ids:
            try:
                if mode == "dry_run":
                    result = issue_tasks.inspect_issue_llm_title_regeneration(issue_id, bk_biz_id)
                    safe_count += int(bool(result.get("safe_to_regenerate")))
                else:
                    result = issue_tasks.regenerate_issue_llm_title(
                        issue_id,
                        bk_biz_id,
                        operator=operator,
                    )
                    success_count += int(result.get("result") == "ok")
            except Exception as error:
                failed_count += 1
                result = {
                    "issue_id": issue_id,
                    "bk_biz_id": bk_biz_id,
                    "result": "command_error",
                    "error": str(error),
                }

            result_name = str(result.get("result") or "unknown")
            result_counts[result_name] = result_counts.get(result_name, 0) + 1
            self.stdout.write(json.dumps({"type": "result", "mode": mode, **result}, ensure_ascii=False))

        self.stdout.write(
            json.dumps(
                {
                    "type": "summary",
                    "mode": mode,
                    "requested_count": len(issue_ids),
                    "processed_count": len(issue_ids),
                    "safe_count": safe_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "result_counts": result_counts,
                },
                ensure_ascii=False,
            )
        )

        if failed_count:
            raise CommandError(f"{failed_count} 个 Issue 处理异常")
