from django.core.management.base import BaseCommand, CommandParser

from bk_monitor_base.metadata.task.tenant import init_tenant


class Command(BaseCommand):
    help = "init tenant"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--bk_tenant_id", type=str, required=True, help="租户ID")
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        init_tenant(bk_tenant_id)
