import json

from django.core.management.base import BaseCommand, CommandError

from bkmonitor.nodeman_integration.readiness import build_readiness_report


class Command(BaseCommand):
    help = "检查当前部署是否满足 NodeMan V3 启用前置条件"

    def handle(self, *args, **options):
        del args, options
        report = build_readiness_report()
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if not report["ready"]:
            blocker_codes = ",".join(blocker["code"] for blocker in report["blockers"])
            raise CommandError(f"NodeMan V3 readiness failed: {blocker_codes}")
