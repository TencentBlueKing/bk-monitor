from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.task import config_refresh


class Command(BaseCommand):
    """
    根据mysql的配置，刷新数据源、influxdb-proxy 及 influxdb 相关的consul信息
    """

    def handle(self, *args, **options):
        config_refresh.refresh_datasource()
        config_refresh.refresh_influxdb_route()
        config_refresh.clean_influxdb_tag()
        config_refresh.clean_influxdb_storage()
        config_refresh.clean_influxdb_cluster()
        config_refresh.clean_influxdb_host()
