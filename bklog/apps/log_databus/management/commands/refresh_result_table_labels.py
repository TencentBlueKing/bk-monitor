"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import time
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.api import TransferApi
from apps.log_databus.constants import build_collector_scene_labels, detect_container_stream
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
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

        qs = (
            CollectorConfig.objects.filter(table_id__isnull=False)
            .exclude(table_id="")
            .order_by("collector_config_id")
        )
        total = qs.count()
        self.stdout.write(f"Total collector configs with table_id: {total}")

        success, failed = 0, 0
        configs = qs.values_list(
            "collector_config_id",
            "table_id",
            "collector_config_name_en",
            "collector_scenario_id",
            "custom_type",
            "environment",
            "bcs_cluster_id",
            "bk_app_code",
            named=True,
        )

        for i in range(0, total, batch_size):
            batch = list(configs[i : i + batch_size])
            container_streams = self._get_container_streams([cfg.collector_config_id for cfg in batch])
            for cfg in batch:
                labels = self._build_labels(cfg, container_streams.get(cfg.collector_config_id, ""))
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

            if not dry_run and i + batch_size < total:
                time.sleep(sleep_sec)

        self.stdout.write(self.style.SUCCESS(f"Done. success={success}, failed={failed}, total={total}"))

    @staticmethod
    def _get_container_streams(collector_config_ids: list[int]) -> dict[int, str]:
        collector_types = defaultdict(set)
        for collector_config_id, collector_type in ContainerCollectorConfig.objects.filter(
            collector_config_id__in=collector_config_ids
        ).values_list("collector_config_id", "collector_type"):
            collector_types[collector_config_id].add(collector_type)
        return {
            collector_config_id: detect_container_stream(types)
            for collector_config_id, types in collector_types.items()
        }

    @staticmethod
    def _build_labels(cfg, container_stream: str = "") -> dict:
        return build_collector_scene_labels(
            collector_scenario_id=cfg.collector_scenario_id,
            custom_type=cfg.custom_type,
            environment=cfg.environment,
            bcs_cluster_id=cfg.bcs_cluster_id,
            container_stream=container_stream,
            bk_app_code=cfg.bk_app_code,
            table_id=cfg.table_id,
            collector_config_name_en=cfg.collector_config_name_en,
        )
