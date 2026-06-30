"""
将 metadata ResourceDefinition / RelationDefinition 同步到已有 BKBase graph relation 链路。
"""

import json

from django.core.management.base import BaseCommand, CommandError

from bkm_space.utils import bk_biz_id_to_space_uid
from metadata.models.entity_relation import NAMESPACE_ALL
from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase


class Command(BaseCommand):
    help = "Sync metadata graph definitions to existing BKBase graph relation datalinks."

    def add_arguments(self, parser):
        parser.add_argument("--namespace", default="", help="definition namespace, default is __all__")
        parser.add_argument("--bk-biz-id", type=int, default=None, help="convert bk_biz_id to definition namespace")
        parser.add_argument("--dry-run", action="store_true", help="only report matched/changed datalinks")

    def handle(self, *args, **options):
        namespace = options["namespace"] or NAMESPACE_ALL
        if options["bk_biz_id"] is not None:
            namespace = bk_biz_id_to_space_uid(options["bk_biz_id"])
            if not namespace:
                raise CommandError(f"cannot resolve namespace from bk_biz_id={options['bk_biz_id']}")

        result = sync_graph_definition_to_bkbase(
            namespace=namespace,
            action="manual",
            dry_run=options["dry_run"],
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
