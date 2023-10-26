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

from django.core.management import BaseCommand, CommandError

from metadata import models
from metadata.service.vm_storage import disable_influxdb_router_for_vm_table


class Command(BaseCommand):

    help = "disable influxdb router for accessed vm"

    def add_arguments(self, parser):
        parser.add_argument("--switched_storage_id", type=int, required=False, help="要切换到的存储关系")
        parser.add_argument("--space_uid", type=str, required=False, help="空间 uid，格式: bkcc__xxx")
        parser.add_argument("--table_ids", type=str, required=False, help="结果表 ID, 格式: test,test1,test2")
        parser.add_argument("--can_deleted", type=bool, default=False, help="删除记录")

    def handle(self, *args, **options):
        self.stdout.write("start to disable influxdb router")

        space_uid = options.get("space_uid", "")
        table_ids = options.get("table_ids", "")
        if not (table_ids or space_uid):
            raise CommandError(f"space_uid: {space_uid} and table_ids: {table_ids} are null")

        # 如果结果表存在，则拆分为数组
        if table_ids:
            table_id_list = table_ids.split(",")
        else:
            # 如果结果表为空，则通过空间获取数据
            if "__" not in space_uid:
                raise CommandError(f"space_uid: {space_uid} must split '__'")
            space_type, space_id = space_uid.split("__")
            data_ids = set(
                models.SpaceDataSource.objects.filter(space_type_id=space_type, space_id=space_id).values_list(
                    "bk_data_id", flat=True
                )
            )
            table_ids = (
                models.DataSourceResultTable.objects.filter(bk_data_id__in=data_ids)
                .values_list("table_id", flat=True)
                .distinct()
            )
            table_id_list = list(
                models.AccessVMRecord.objects.filter(result_table_id__in=table_ids).values_list(
                    "result_table_id", flat=True
                )
            )
            # 过滤到单指标单表
            table_id_list = list(
                models.ResultTableOption.objects.filter(
                    table_id__in=table_id_list, name=models.DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT, value="true"
                ).values_list("table_id", flat=True)
            )

        # 打印出要禁用的结果表
        self.stdout.write(f"allow to disable table_id_list: {json.dumps(table_id_list)}")
        disable_influxdb_router_for_vm_table(
            table_id_list, options.get("switched_storage_id"), options.get("can_deleted")
        )

        self.stdout.write("disable influxdb router successfully")
