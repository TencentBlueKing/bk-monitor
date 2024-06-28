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

from django.core.management.base import BaseCommand
from django.db.models import Q

from metadata import models
from metadata.models.space.constants import SpaceTypes
from metadata.service.data_source import query_biz_plugin_data_id_list


class Command(BaseCommand):
    help = "查询已经禁用的数据源ID"
    regex = r"_delete_[0-9]{14}$"

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", help="要查询的空间uid，如bkcc__2")
        parser.add_argument("--all", action="store_true", help="查询所有流量为空的数据源 ID, 可能需要较长时间")

    def handle(self, *args, **options):
        """这里要包含两个场景
        1. is_enable 为 False
        2. data_name 以 _delete_16位数字结尾
        """
        # 过滤空间下的数据源ID
        space_uid = options.get("space_uid")
        all_space = options.get("all")
        if not all_space and space_uid is None:
            self.stderr.write("please input space_uid or use --all option")
            return
        if space_uid:
            self._query_space_data_ids(space_uid)
            return
        self._filter_all_data_ids()

    def _query_space_data_ids(self, space_uid: str):
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

        data_ids = list(
            models.DataSource.objects.filter(
                Q(bk_data_id__in=bk_data_ids, is_enable=False)
                | Q(bk_data_id__in=bk_data_ids, data_name__regex=self.regex)
            ).values_list("bk_data_id", flat=True)
        )
        self.stdout.write(json.dumps({"count": len(data_ids), "result": data_ids}))

    def _filter_all_data_ids(self):
        # 过滤出 is_enable 为 False 或者名称符合规则的数据源
        data_ids = list(
            models.DataSource.objects.filter(Q(is_enable=False) | Q(data_name__regex=self.regex)).values_list(
                "bk_data_id", flat=True
            )
        )

        self.stdout.write(json.dumps({"count": len(data_ids), "result": data_ids}))
