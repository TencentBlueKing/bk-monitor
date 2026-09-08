from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.utils.gse import KafkaGseSyncer


class Command(BaseCommand):
    """
    同步默认的消息队列(stream_to_info)信息到zk或gse，每次部署的时候执行
    """

    def handle(self, *args, **options):
        """
        同步默认的kafka信息到zk或者gse
        """
        KafkaGseSyncer.sync_to_gse()
