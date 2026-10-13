import logging

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.config import settings

logger = logging.getLogger("metadata")


def main():
    """批量刷新所有influxdb backend的默认RP策略"""

    for influxdb_host in models.InfluxDBHostInfo.objects.all():
        # 查询机器归属哪个influxdb集群
        clusters = [
            cluster["cluster_name"]
            for cluster in models.InfluxDBClusterInfo.objects.filter(host_name=influxdb_host.host_name).values(
                "cluster_name"
            )
        ]
        # 查询该集群下有哪些结果表是需要刷新配置的
        refresh_dbset = {
            storage["database"]
            for storage in models.InfluxDBStorage.objects.filter(
                proxy_cluster_name__in=clusters, use_default_rp=True, enable_refresh_rp=True
            ).values("database")
        }
        influxdb_host.update_default_rp(refresh_dbset)
        logger.info(
            f"influxdb->[{influxdb_host.domain_name}:{influxdb_host.port}] update default_rp->[{settings.metadata.ts_data_saved_days}] success."
        )
