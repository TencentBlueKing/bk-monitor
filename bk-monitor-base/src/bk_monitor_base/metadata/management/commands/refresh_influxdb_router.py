from typing import Any

from django.core.management.base import BaseCommand

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.utils import consul_tools


class Command(BaseCommand):
    help = "refresh influxdb router command"

    def handle(self, *args: Any, **options: Any) -> None:
        """当有变动时，更新 influxdb 对应的路由，以使立即生效"""
        self.stdout.write("start to refresh influxdb router")
        try:
            for host_info in models.InfluxDBHostInfo.objects.all():
                host_info.refresh_consul_cluster_config()

            models.InfluxDBClusterInfo.refresh_consul_cluster_config()

            index = models.InfluxDBStorage.objects.count()
            for result_table in models.InfluxDBStorage.objects.all():
                index -= 1
                result_table.refresh_consul_cluster_config(is_publish=(index == 0))

            # 更新 vm router
            models.AccessVMRecord.refresh_vm_router()
        except Exception as e:
            self.stderr.write(f"failed to refresh influxdb router info {e}")

        # 刷新tag路由
        try:
            models.InfluxDBTagInfo.refresh_consul_tag_config()
        except Exception as e:
            self.stderr.write(f"refresh consul tag error, {e}")

        # 任务完成前，更新一下version
        consul_tools.refresh_router_version()
        self.stdout.write("refresh influxdb router completely")
