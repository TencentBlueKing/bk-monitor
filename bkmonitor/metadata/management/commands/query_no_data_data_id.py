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
import time
from typing import List

from django.core.management.base import BaseCommand

from core.drf_resource import api


class Command(BaseCommand):
    help = "查询30天内数据流量为空的数据源"

    def add_arguments(self, parser):
        parser.add_argument("--bk_biz_id", type=int, help="业务ID, 以便于查询不同环境的数据源")

    def handle(self, *args, **options):
        # 查询空间不能为空
        bk_biz_id = options.get("bk_biz_id")
        if not bk_biz_id:
            self.stderr.write("please input [bk_biz_id]")
            return
        data_id_list = self._query_no_data_data_id_list(bk_biz_id)
        self.stdout.write(json.dumps({"count": len(data_id_list), "result": data_id_list}))

    def _query_no_data_data_id_list(self, bk_biz_id: int) -> List:
        """获取没有数据流量的数据源ID"""
        # 获取当前时间
        now_sec = int(time.time())
        offset_sec = now_sec - 120
        req_params = {
            "bk_biz_ids": [bk_biz_id],
            "promql": "sum by (topic) (sum_over_time(bkmonitor:jmx_kafka2:kafka_server_messages_in_per_sec_per_topic{topic=~\"^0bkmonitor_[0-9]+0$\"}[30d]))<=0",  # noqa
            "start": now_sec,
            "end": offset_sec,
            "step": "60s",
            "timezone": "Asia/Shanghai",
            "instant": False,
        }
        data = api.unify_query.query_data_by_promql(req_params)
        if not data.get("series"):
            self.stderr.write("没有查询到30天内流量为空的数据源")
            return []
        # 解析结果，获取所有的数据源ID
        data_ids = [
            int(d["group_values"][0].split("0bkmonitor_")[-1].rstrip("0"))
            for d in data["series"]
            if d.get("group_values")
        ]
        return data_ids
