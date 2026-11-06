from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.task.sync_cmdb_relation import sync_relation_redis_data


class Command(BaseCommand):
    help = "Sync built-in data to Redis and update the ResultTable model"

    redis_key = settings.metadata.builtin_data_rt_redis_key

    def handle(self, *args, **options):
        """
        Sync built-in data to Redis and update ResultTable model
        """
        self.stdout.write("Start to sync built-in data to Redis and update ResultTable model")

        try:
            sync_relation_redis_data()
        except Exception as e:  # pylint: disable=broad-except
            self.stdout.write(f"Error: Failed to sync built-in data to Redis and update ResultTable model, error={e}")

        self.stdout.write("Sync built-in data to Redis and update ResultTable model successfully")
