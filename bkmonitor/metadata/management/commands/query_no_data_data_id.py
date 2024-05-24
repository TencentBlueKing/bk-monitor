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
from typing import Dict, List

import requests
from django.core.management.base import BaseCommand

from metadata import models
from metadata.models.space.constants import SpaceTypes
from metadata.service.data_source import query_biz_plugin_data_id_list


class Command(BaseCommand):
    help = "查询30天内数据流量为空的数据源"

    def add_arguments(self, parser):
        parser.add_argument(
            "--unify_query_host", default="http://bk-monitor-unify-query-http:10205", help="unify-query地址"
        )
        parser.add_argument("--platform_biz_id", default=2, help="查询指标数据所在的业务ID，默认是2")
        parser.add_argument("--space_uid", help="要查询的空间uid，如bkcc__2")
        parser.add_argument("--all", action="store_true", help="查询所有流量为空的数据源 ID, 可能需要较长时间")

    def handle(self, *args, **options):
        # 查询空间不能为空
        unify_query_host = options.get("unify_query_host")
        platform_biz_id = int(options.get("platform_biz_id"))
        space_uid = options.get("space_uid")
        is_all_space = options.get("all")
        if space_uid is None and not is_all_space:
            self.stderr.write("please input space_uid or use --all option")
            return

        # 查询指定空间的数据源ID
        if space_uid is not None:
            space_data_id_list = self._query_belong_data_id(space_uid)
            data_id_list = self._query_space_no_data_data_id_list(unify_query_host, platform_biz_id, space_data_id_list)
            self.stdout.write(json.dumps({"count": len(data_id_list), "result": data_id_list}))
            return

        # 查询所有流量为空的数据源
        data_id_list = self._query_all_no_data_data_id_list(unify_query_host, platform_biz_id)
        self.stdout.write(json.dumps({"count": len(data_id_list), "result": data_id_list}))

    def _query_belong_data_id(self, space_uid: str) -> List:
        """获取归属空间的数据源ID

        - 业务空间类型，需要查询插件相关的data__id
        """
        # 通过uid获取业务ID
        space_type, space_id = space_uid.split("__")
        biz_id = models.Space.objects.get_biz_id_by_space(space_type, space_id)
        rts = models.ResultTable.objects.filter(bk_biz_id=biz_id).values_list("table_id", flat=True)

        # 通过结果表过滤数据源ID
        bk_data_ids = set(
            models.DataSourceResultTable.objects.filter(table_id__in=rts).values_list("bk_data_id", flat=True)
        )

        # 如果是业务类型，再去获取插件对应的数据源ID
        biz_id_list = []
        if space_uid.startswith(SpaceTypes.BKCC.value):
            biz_id_list.append(int(space_id))
        # 如果业务存在，则查询插件下的数据源ID
        if biz_id_list:
            bk_data_ids.union(set(query_biz_plugin_data_id_list(biz_id_list)[int(space_id)]))

        return list(bk_data_ids)

    def _query_all_no_data_data_id_list(self, unify_query_host: str, bk_biz_id: int) -> List:
        """查询所有没有数据流量的数据源ID"""
        promql = "sum by (id) (sum_over_time(bkmonitor:transfer_pipeline_frontend_handled_total[30d]))<=0"
        return self._request_unify_query(
            unify_query_host, promql, {"X-Bk-Scope-Space-Uid": f"{SpaceTypes.BKCC.value}__{bk_biz_id}"}
        )

    def _query_space_no_data_data_id_list(self, unify_query_host: str, bk_biz_id: int, data_id_list: List) -> List:
        """查询空间没有数据流量的数据源ID"""
        data_id_str = [str(d) for d in data_id_list]
        filter_q = "|".join(data_id_str)
        promql = (
            "sum by (id) (sum_over_time(bkmonitor:transfer_pipeline_frontend_handled_total{id=~\""
            + filter_q
            + "\"}[30d]))<=0"
        )
        return self._request_unify_query(
            unify_query_host, promql, {"X-Bk-Scope-Space-Uid": f"{SpaceTypes.BKCC.value}__{bk_biz_id}"}
        )

    def _request_unify_query(self, host: str, promql: str, headers: Dict) -> List:
        """请求unify-query接口"""
        url = f"{host}/query/ts/promql"
        now_sec = int(time.time())
        offset_sec = now_sec - 120
        req_params = {
            "promql": promql,
            "start": str(now_sec),
            "end": str(offset_sec),
            "step": "60s",
            "timezone": "Asia/Shanghai",
            "instant": False,
        }
        data = requests.post(url, json=req_params, headers=headers).json()
        # 判断是否为空
        if not data.get("series"):
            return []
        ret_data = set()
        # 组装数据
        for d in data["series"]:
            ret_data.add(int(d["group_values"][0]))

        return list(ret_data)
