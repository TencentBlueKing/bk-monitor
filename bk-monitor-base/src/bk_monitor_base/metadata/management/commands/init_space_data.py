from django.core.management import call_command
from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.models import DataSource, DataSourceResultTable, ResultTable


class Command(BaseCommand):
    help = "init space data, include three sub-command"

    def add_arguments(self, parser):
        parser.add_argument("--init_type", action="store", default="True", help="init space type")
        parser.add_argument("--sync_bkcc", action="store", default="True", help="sync bkcc biz data")
        parser.add_argument("--sync_bcs", action="store", default="True", help="init bcs project data")
        parser.add_argument("--init_redis", action="store", default="True", help="push space to redis")

    def handle(self, *args, **options):
        # 修复内置dataid脏数据
        self.fix_dirty_datasource()

        if options["init_type"] in ["True", "true"]:
            call_command("init_space_type")
        if options["sync_bkcc"] in ["True", "true"]:
            call_command("sync_cmdb_space")
        if options["sync_bcs"] in ["True", "true"]:
            call_command("sync_bcs_space")
        if options["init_redis"] in ["True", "true"]:
            call_command("init_redis_data")

        print("init space data successfully")

    @staticmethod
    def fix_dirty_datasource():
        target_kwargs = {
            1100011: (
                ("DataSource:data_name", f"{settings.metadata.aggregation_biz_id}_custom_report_aggate_dataid"),
                ("ResultTable:bk_biz_id", 0),
            ),
            1100012: (
                ("DataSource:data_name", f"{settings.metadata.aggregation_biz_id}_operation_data_custom_series"),
                ("ResultTable:bk_biz_id", 0),
            ),
            1100013: (
                ("DataSource:data_name", f"{settings.metadata.aggregation_biz_id}_bkm_statistics"),
                ("ResultTable:bk_biz_id", 0),
            ),
            1100006: (
                ("DataSource:data_name", f"{settings.metadata.aggregation_biz_id}_bkunifylogbeat_common_metrics"),
            ),
            1100007: (("DataSource:data_name", f"{settings.metadata.aggregation_biz_id}_bkunifylogbeat_task_metrics"),),
        }
        record_fetcher = {
            "DataSource": lambda dataid: DataSource.objects.filter(bk_data_id=dataid),
            "ResultTable": lambda dataid: ResultTable.objects.filter(
                table_id__in=DataSourceResultTable.objects.filter(bk_data_id=dataid).values_list("table_id", flat=1)
            ),
        }
        for data_id in target_kwargs:
            for rule in target_kwargs[data_id]:
                model, attr = rule[0].split(":")
                target = rule[1]
                for r in record_fetcher[model](data_id):
                    if getattr(r, attr) != target:
                        print(f"{model}({data_id}) {attr} fix: {getattr(r, attr)} -> {target}")
                        setattr(r, attr, target)
                        r.save()
                    else:
                        print(f"{model}({data_id}) {attr} skip: {getattr(r, attr)} == {target}")
