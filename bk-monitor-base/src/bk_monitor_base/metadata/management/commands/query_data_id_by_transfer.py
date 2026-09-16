import json
import textwrap
from argparse import RawTextHelpFormatter

from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.service.data_source import (
    filter_data_id_and_transfer,
    get_transfer_cluster,
)


class Command(BaseCommand):
    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            "--filter",
            required=True,
            type=str,
            help=textwrap.dedent(
                """
            include as follow
            - all: all data_id, format: {transfer_cluster_id: [data_id]}
            - bk-null: transfer cluster is bk-null or other
            - not_exist: transfer cluster not exist"""
            ),
        )

    def handle(self, *args, **options):
        filter = options.get("filter")
        transfer_id_list = get_transfer_cluster()
        transfer_data_id_map = filter_data_id_and_transfer()
        if filter == "all":
            self.stdout.write(json.dumps(transfer_data_id_map))
            return
        elif filter == "not_exist":
            transfer_id_list.append("bk-null")
            diff = set(transfer_data_id_map.keys()) - set(transfer_id_list)
            ret_data = {}
            for d in diff:
                ret_data[d] = transfer_data_id_map[d]
            self.stdout.write(json.dumps(ret_data))
            return

        self.stdout.write(json.dumps(transfer_data_id_map.get(filter, [])))
