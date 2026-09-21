from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.task.migrate import migrate_nano_log_tables


class Command(BaseCommand):
    help = "migrate nano log"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="bk tenant id", default="system")
        parser.add_argument("--table_id", type=str, help="table id", required=True)

    def handle(self, *args, **options):
        table_id = options["table_id"]
        bk_tenant_id = options["bk_tenant_id"]

        migrate_results = migrate_nano_log_tables(bk_tenant_id=bk_tenant_id, table_ids=[table_id])

        success_table_ids = [table_id for table_id, result in migrate_results.items() if result[0]]
        failed_table_ids = [table_id for table_id, result in migrate_results.items() if not result[0]]

        self.stdout.write(self.style.SUCCESS(f"success table ids: {success_table_ids}"))
        self.stdout.write(self.style.ERROR(f"failed table ids: {failed_table_ids}"))
