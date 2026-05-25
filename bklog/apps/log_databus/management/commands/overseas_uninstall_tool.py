"""
根据传入的业务ID，批量停用（stop）所有采集项。

使用方式（在目标 Pod 中执行）:
  python manage.py overseas_uninstall_tool --bk-biz-ids 19078,20 [--dry-run]
"""

from django.core.management import BaseCommand, CommandError

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.utils.local import activate_request
from apps.utils.thread import generate_request


def _parse_biz_ids(value: str) -> list[int]:
    if not value:
        raise CommandError("--bk-biz-ids is required")
    try:
        ids = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as e:
        raise CommandError(f"invalid --bk-biz-ids: {value!r}") from e
    if not ids:
        raise CommandError("--bk-biz-ids must contain at least one positive integer")
    return ids


class Command(BaseCommand):
    help = "Disable (stop) all collectors for specified business IDs"

    def add_arguments(self, parser):
        parser.add_argument("--bk-biz-ids", required=True, help="Comma-separated bk_biz_id list")
        parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")

    def handle(self, *args, **options):
        biz_ids = _parse_biz_ids(options["bk_biz_ids"])
        dry_run = options["dry_run"]

        activate_request(generate_request("admin"))

        self.disable_collectors(biz_ids, dry_run=dry_run)

    def disable_collectors(self, biz_ids: list[int], dry_run: bool = False):
        """批量停用指定业务下的所有采集项。"""
        self._info(f"disable_collectors: biz_ids={biz_ids}, dry_run={dry_run}")

        total = 0
        success = 0
        skipped = 0
        failed = 0

        for biz_id in biz_ids:
            collectors = CollectorConfig.objects.filter(bk_biz_id=biz_id, is_active=True, is_deleted=False)
            count = collectors.count()
            self._info(f"biz {biz_id}: found {count} active collector(s)")

            if count == 0:
                continue

            for collector in collectors:
                cid = collector.collector_config_id
                cname = collector.collector_config_name
                total += 1

                if dry_run:
                    self._info(f"  [dry-run] would stop collector [{cid}] {cname}")
                    skipped += 1
                    continue

                try:
                    handler = CollectorHandler.get_instance(cid)
                    handler.stop()
                    self._info(f"  [OK] stopped collector [{cid}] {cname}")
                    success += 1
                except Exception as e:
                    self._err(f"  [FAIL] collector [{cid}] {cname}: {e}")
                    failed += 1

        self._info(f"done. total={total}, success={success}, skipped={skipped}, failed={failed}")

    def _info(self, msg):
        self.stdout.write(self.style.SUCCESS(f"[uninstall] {msg}"))

    def _err(self, msg):
        self.stdout.write(self.style.ERROR(f"[uninstall] {msg}"))
