import json

from django.core.management.base import BaseCommand

from bk_monitor_base.metadata import models


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--domains", type=str, help="集群的域名或ip，多个以半角逗号分隔")

    def handle(self, *args, **options):
        domains = options.get("domains")
        if not domains:
            self.stdout.write("please input domains")
            return

        # 转换为数据
        domain_list = domains.split(",")
        data = list(models.ClusterInfo.objects.filter(domain_name__in=domain_list).values())
        self.stdout.write(json.dumps(data))
