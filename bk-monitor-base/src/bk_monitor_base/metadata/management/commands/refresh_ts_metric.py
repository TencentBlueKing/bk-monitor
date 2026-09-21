from django.core.management.base import BaseCommand, CommandError

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "refresh time series metric"

    def add_arguments(self, parser):
        parser.add_argument("--data_id", type=int, required=False, help="data source id or table_id")
        parser.add_argument("--table_id", type=str, required=False, help="table id")

    def get_data_id_by_table_id(self, table_id):
        try:
            bk_data_id = models.DataSourceResultTable.objects.get(table_id=table_id).bk_data_id
        except models.DataSourceResultTable.DoesNotExist:
            raise CommandError(f"table_id: {table_id} not found from DataSourceResultTable")
        return bk_data_id

    def handle(self, *args, **options):
        data_id = options.get("data_id")
        table_id = options.get("table_id")
        # Ensure at least one of `data_id` or `table_id` is provided
        if not data_id and not table_id:
            raise CommandError("You must provide at least one of --data_id or --table_id.")

        if not data_id:
            data_id = self.get_data_id_by_table_id(table_id)

        client = SpaceTableIDRedis()
        self.stdout.write(f"data id: {data_id} start to refresh metric router")
        try:
            ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=data_id)
        except models.TimeSeriesGroup.DoesNotExist:
            raise CommandError(f"data_id: {data_id} not found from TimeSeriesGroup")
        ts_group.update_time_series_metrics()
        self.stdout.write(f"data id: {data_id} start to push redis data")
        client.push_table_id_detail(table_id_list=[ts_group.table_id], is_publish=True)
        self.stdout.write(f"data id: {data_id} refresh metric router successfully")

        self.stdout.write("update time series metric successfully")
