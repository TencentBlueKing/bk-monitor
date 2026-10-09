from django.core.management.base import BaseCommand

from bk_monitor_base.metadata import config, models


def update_metrics_report_path_option(data_id):
    """
    更新数据源指标上报路径
    :param data_id: 数据源ID
    """
    res = models.DataSourceOption.objects.filter(
        bk_data_id=data_id,
        name="metrics_report_path",
    ).update(value=f"{config.CONSUL_PATH}/influxdb_metrics/{data_id}/time_series_metric")

    if not res:
        models.DataSourceOption.objects.create(
            bk_data_id=data_id,
            name="metrics_report_path",
            value_type="string",
            value=f"{config.CONSUL_PATH}/influxdb_metrics/{data_id}/time_series_metric",
            creator="system",
        )


class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. 更新聚合网关report path
        update_metrics_report_path_option(1100011)

        # 2. 更新运营数据上报report path
        update_metrics_report_path_option(1100012)

        # 3. 更新新版运营数据上报report path
        update_metrics_report_path_option(1100013)

        self.stdout.write("all data_id refresh report path option done.")
