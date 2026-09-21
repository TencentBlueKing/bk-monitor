from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from bk_monitor_base.metadata import config
from bk_monitor_base.metadata.task.bcs import update_bcs_cluster_cloud_id_config


class Command(BaseCommand):
    """
    根据BCS集群的云区域ID
    """

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        update_bcs_cluster_cloud_id_config()
