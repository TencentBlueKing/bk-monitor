"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import time

from django.core.management.base import BaseCommand

from apps.api import TransferApi
from apps.log_databus.constants import COLLECTOR_SCENARIO_TO_SCENE, build_scene_labels
from apps.log_databus.models import CollectorConfig
from apps.utils.log import logger


class Command(BaseCommand):
    help = "Refresh ResultTable.labels for all existing collector configs (scene-based search backfill)"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=50, help="Number of records per batch")
        parser.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between batches")
        parser.add_argument("--dry-run", action="store_true", help="Only print labels without calling API")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        sleep_sec = options["sleep"]
        dry_run = options["dry_run"]

        qs = CollectorConfig.objects.filter(table_id__isnull=False).exclude(table_id="")
        total = qs.count()
        self.stdout.write(f"Total collector configs with table_id: {total}")

        success, failed = 0, 0
        configs = list(qs.values_list(
            "collector_config_id", "table_id", "collector_scenario_id",
            "environment", "bcs_cluster_id", "bk_biz_id",
            named=True,
        ))

        for i in range(0, len(configs), batch_size):
            batch = configs[i : i + batch_size]
            for cfg in batch:
                labels = self._build_labels(cfg)
                if dry_run:
                    self.stdout.write(f"  [DRY-RUN] {cfg.table_id} -> {labels}")
                    success += 1
                    continue
                try:
                    TransferApi.switch_result_table({
                        "table_id": cfg.table_id,
                        "operator": "admin",
                        "labels": labels,
                    })
                    success += 1
                    logger.info("[refresh_labels] %s -> %s", cfg.table_id, labels)
                except Exception as e:
                    failed += 1
                    logger.exception("[refresh_labels] %s failed: %s", cfg.table_id, e)

            if not dry_run and i + batch_size < len(configs):
                time.sleep(sleep_sec)

        self.stdout.write(self.style.SUCCESS(f"Done. success={success}, failed={failed}, total={total}"))

    @staticmethod
    def _build_labels(cfg) -> dict:
        is_container = cfg.environment == "container"
        if is_container:
            return build_scene_labels("k8s", cluster_id=cfg.bcs_cluster_id or "")
        scene = COLLECTOR_SCENARIO_TO_SCENE.get(cfg.collector_scenario_id, "host")
        return build_scene_labels(scene)
