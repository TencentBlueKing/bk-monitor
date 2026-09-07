"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.log_databus.handlers.scene import COMPARE_MODE_LOCAL, COMPARE_MODE_REMOTE, refresh_scene_labels


class Command(BaseCommand):
    help = "Refresh ResultTable.labels for collector configs (scene-based search backfill)"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=50, help="Number of records per batch")
        parser.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between batches")
        parser.add_argument("--dry-run", action="store_true", help="Only print labels without calling API")
        parser.add_argument("--bk-biz-id", type=int, help="Only process one business")
        parser.add_argument(
            "--compare-remote",
            action="store_true",
            help="Compare ResultTable.labels before writing; intended for manual inspection or repair",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("batch-size must be greater than 0")

        result = refresh_scene_labels(
            bk_biz_id=options.get("bk_biz_id"),
            compare_mode=COMPARE_MODE_REMOTE if options["compare_remote"] else COMPARE_MODE_LOCAL,
            dry_run=options["dry_run"],
            batch_size=batch_size,
            sleep=options["sleep"],
        )
        summary = (
            f"Done. total={result['total']}, success={result['success']}, failed={result['failed']}, "
            f"skipped={result['skipped']}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
