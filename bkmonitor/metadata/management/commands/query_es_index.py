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
from typing import Dict, List

from django.core.management.base import BaseCommand

from metadata import models
from metadata.service.es_storage import ESIndex


class Command(BaseCommand):
    help = "Query Elasticsearch Index"

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_ids", type=str, help="数据源ID, 半角逗号分隔")

    def handle(self, *args, **options):
        bk_data_ids = options.get("bk_data_ids")
        if not bk_data_ids:
            self.stderr.write("please input [bk_data_ids]")
            return
        bk_data_id_list = [int(d) for d in bk_data_ids.split(",")]
        rt_ds = self._query_table_id(bk_data_id_list)
        if not rt_ds:
            self.stderr.write("no es data source found")
            return
        # 过滤结果表对应的索引
        tid_es = ESIndex().query_es_index(list(rt_ds.keys()))

        data = {}
        for tid, data_id in rt_ds.items():
            data.setdefault(data_id, []).append(tid_es.get(tid) or {})

        self.stdout.write(json.dumps(data))

    def _query_table_id(self, bk_data_id_list: List[int]) -> Dict:
        rt_ds = {
            ds_rt["table_id"]: ds_rt["bk_data_id"]
            for ds_rt in models.DataSourceResultTable.objects.filter(bk_data_id__in=bk_data_id_list).values(
                "bk_data_id", "table_id"
            )
        }

        data = {}
        rt_list = models.ESStorage.objects.filter(table_id__in=rt_ds.keys()).values_list("table_id", flat=True)
        for rt in rt_list:
            data[rt] = rt_ds[rt]

        return data
