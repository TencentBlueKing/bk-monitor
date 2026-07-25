"""已停用的旧 Graph Relation 图定义同步命令。"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Deprecated: Graph Relation DataLink is managed by ResultTable options."

    def add_arguments(self, parser):
        parser.add_argument("--namespace", default="")
        parser.add_argument("--bk-biz-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        raise CommandError(
            "legacy Graph Relation sync is disabled; configure graph_relation_v4_data_link on the ResultTable"
        )
