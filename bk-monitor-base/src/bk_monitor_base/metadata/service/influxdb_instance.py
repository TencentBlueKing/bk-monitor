import logging

from bk_monitor_base.metadata import models

logger = logging.getLogger("metadata")


class InfluxDBInstanceCluster:
    def __init__(self, cluster_name: str, hosts: list[dict], is_readable: bool | None = True):
        self.cluster_name = cluster_name
        self.hosts = hosts
        self.is_readable = is_readable
        self.default_backup_rate_limit = 0

    def add(self):
        """添加记录"""
        self._add_hosts()
        self._add_cluster()

    def _add_hosts(self):
        """添加主机信息
        NOTE: 采用更新或创建的方式，可以重复执行
        """
        for h in self.hosts:
            models.InfluxDBHostInfo.objects.update_or_create(
                host_name=h["host_name"],
                defaults={
                    "domain_name": h["domain"],
                    "port": h["port"],
                    "username": h.get("username") or "",
                    "password": h.get("password") or "",
                    "description": h.get("description") or h["host_name"],
                    "status": h.get("is_disabled") or False,
                    "backup_rate_limit": h.get("backup_rate_limit") or self.default_backup_rate_limit,
                },
            )

    def _add_cluster(self):
        """添加集群信息"""
        for h in self.hosts:
            models.InfluxDBClusterInfo.objects.update_or_create(
                cluster_name=self.cluster_name,
                defaults={"host_name": h["host_name"], "host_readable": self.is_readable},
            )
