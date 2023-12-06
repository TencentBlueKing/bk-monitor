# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import textwrap
from argparse import RawTextHelpFormatter

from django.core.management.base import BaseCommand

from metadata.service.data_source import (
    filter_data_id_and_transfer,
    get_transfer_cluster,
)


class Command(BaseCommand):
    def create_parser(self, *args, **kwargs):
        parser = super(Command, self).create_parser(*args, **kwargs)
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
