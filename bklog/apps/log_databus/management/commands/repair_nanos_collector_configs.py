"""
修复纳秒采集项标记。

用法:
    python manage.py repair_nanos_collector_configs --dry-run
    python manage.py repair_nanos_collector_configs
"""

from django.core.management import BaseCommand

from apps.api import TransferApi
from apps.log_databus.models import CollectorConfig
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import LogIndexSet
from apps.utils.log import logger


class Command(BaseCommand):
    help = "Repair stale is_nanos flags according to the current metadata result table configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--collector-config-id",
            "--collector_config_id",
            dest="collector_config_id",
            type=int,
            help="Only repair the specified collector config",
        )
        parser.add_argument("--dry-run", action="store_true", help="Only inspect records without writing or syncing")

    def handle(self, *args, **options):
        queryset = (
            CollectorConfig.objects.filter(is_nanos=True, table_id__isnull=False)
            .exclude(table_id="")
            .order_by("collector_config_id")
        )
        if options["collector_config_id"]:
            queryset = queryset.filter(collector_config_id=options["collector_config_id"])

        dry_run = options["dry_run"]
        total = queryset.count()
        repaired = 0
        skipped = 0
        failed = 0

        self.stdout.write(f"Found {total} collector config(s) with is_nanos=True")
        for collector_config in queryset.iterator():
            try:
                result_table_config = TransferApi.get_result_table({"table_id": collector_config.table_id})
                field_list = result_table_config.get("field_list")
                if field_list is None:
                    raise ValueError("result table config has no field_list")

                has_nanos_field = any(field.get("field_name") == "dtEventTimeStampNanos" for field in field_list)
                if has_nanos_field:
                    skipped += 1
                    continue

                action = "[DRY-RUN]" if dry_run else "[REPAIR]"
                self.stdout.write(f"{action} collector_config_id={collector_config.collector_config_id}")
                if dry_run:
                    repaired += 1
                    continue

                CollectorConfig.objects.filter(collector_config_id=collector_config.collector_config_id).update(
                    is_nanos=False
                )
                if collector_config.index_set_id:
                    index_set = LogIndexSet.objects.filter(index_set_id=collector_config.index_set_id).first()
                    if index_set:
                        BaseIndexSetHandler.sync_router(index_set)
                repaired += 1
            except Exception as e:  # pylint: disable=broad-except
                failed += 1
                logger.exception(
                    "repair is_nanos for collector_config_id=%s failed: %s",
                    collector_config.collector_config_id,
                    e,
                )
                self.stderr.write(
                    self.style.ERROR(f"collector_config_id={collector_config.collector_config_id} failed: {e}")
                )

        message = f"Done. repaired={repaired}, skipped={skipped}, failed={failed}, total={total}"
        if failed:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
