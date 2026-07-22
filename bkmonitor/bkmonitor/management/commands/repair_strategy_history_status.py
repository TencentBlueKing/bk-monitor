# -*- coding: utf-8 -*-  # noqa: UP009
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from bkmonitor.strategy.history import repair_legacy_bulk_strategy_history_status


class Command(BaseCommand):
    """修复存量批量更新和批量删除历史的成功状态。"""

    help = (
        "将存量 update/delete 历史中 status=False 且 message 为空的记录修复为成功。"
        "默认 dry-run；真正修复需加 --execute。"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--batch_size",
            type=int,
            default=1000,
            help="单批更新数量，默认 1000",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="真正执行状态修复；省略时仅 dry-run 统计匹配数量",
        )

    def handle(self, *_args, **options) -> None:
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("batch_size must be a positive integer")

        dry_run = not options["execute"]
        self.stdout.write(f"repair strategy history status start: batch_size={batch_size}, dry_run={dry_run}")
        repaired = repair_legacy_bulk_strategy_history_status(batch_size=batch_size, dry_run=dry_run)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"repair strategy history status dry-run done: would repair {repaired} records")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"repair strategy history status done: repaired {repaired} records"))
