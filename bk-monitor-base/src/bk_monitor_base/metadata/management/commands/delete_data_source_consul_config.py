from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.models import DataSource


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--data_ids", type=int, nargs="*", default=[], help="bk_data_id list")

    def handle(self, *args, **options):
        # 清除指定数据源的consul配置信息
        data_ids = options.get("data_ids")

        for ds in DataSource.objects.filter(bk_data_id__in=data_ids):
            try:
                ds.delete_consul_config()
            except Exception as e:
                self.stdout.write(f"delete {ds.bk_data_id} consul config failed, {e}")

        self.stdout.write("[delete_data_source_consul_config] DONE!")
