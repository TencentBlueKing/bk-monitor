from django.core.management.base import BaseCommand

from bk_monitor_base.metadata import models


class Command(BaseCommand):
    help = "remove repeated target dimension"

    def handle(self, *args, **options):
        """移除操作
        包含下面两个:
            - TimeSeriesMetric
            - Event
        """
        # 去除 TimeSeriesMetric 中重复的维度
        for obj in models.TimeSeriesMetric.objects.all():
            obj.tag_list = list(set(obj.tag_list))
            obj.save(update_fields=["tag_list"])

        self.stdout.write("models: TimeSeriesMetric has removed target dimension")

        # 去除 Event 中重复维度
        for obj in models.Event.objects.all():
            obj.dimension_list = list(set(obj.dimension_list))
            obj.save(update_fields=["dimension_list"])

        self.stdout.write("models: event has removed target dimension")
