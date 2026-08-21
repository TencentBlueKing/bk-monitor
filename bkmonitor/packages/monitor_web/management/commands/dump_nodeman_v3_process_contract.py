import json

from django.core.management.base import BaseCommand

from bkmonitor.nodeman_integration.readiness import build_process_contract


class Command(BaseCommand):
    help = "输出当前进程的 NodeMan V3 配置合同"

    def handle(self, *args, **options):
        del args, options
        self.stdout.write(json.dumps(build_process_contract(), ensure_ascii=False, sort_keys=True))
