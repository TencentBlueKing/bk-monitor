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

from bkmonitor.strategy.history import CleanStrategyHistoryParams
from bkmonitor.strategy.history import clean_strategy_history


class Command(BaseCommand):
    """清理过期的策略变更历史。"""

    help = "清理指定天数以前的策略历史，并保留最近成功快照和必要的删除记录"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            required=True,
            help="保留最近 N 天的全部策略历史",
        )
        parser.add_argument(
            "--batch_size",
            type=int,
            default=1000,
            help="单批删除数量，默认 1000",
        )
        parser.add_argument(
            "--keep_latest_snapshots",
            type=int,
            default=1,
            help="每个策略额外保留的最近成功快照数量，默认 1",
        )

    def handle(self, *_args, **options) -> None:
        try:
            params = CleanStrategyHistoryParams(
                days=options["days"],
                batch_size=options["batch_size"],
                keep_latest_snapshots=options["keep_latest_snapshots"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            "clean strategy history start: "
            f"days={params.days}, batch_size={params.batch_size}, "
            f"keep_latest_snapshots={params.keep_latest_snapshots}"
        )
        deleted = clean_strategy_history(params)
        self.stdout.write(self.style.SUCCESS(f"clean strategy history done: deleted {deleted} records"))
