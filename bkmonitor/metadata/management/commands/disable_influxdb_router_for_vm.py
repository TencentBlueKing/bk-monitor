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
from typing import List

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
        parser.add_argument("--check_table_ids", type=bool, default=False, help="校验要删除的结果表，设置为True，则仅输出要删的结果表")

    def handle(self, *args, **options):
        self.stdout.write("start to disable influxdb router")

        space_uid = options.get("space_uid", "")
        table_ids = options.get("table_ids", "")
        if not (table_ids or space_uid):
            raise CommandError(f"space_uid: {space_uid} and table_ids: {table_ids} are null")

        check_table_ids = options.get("check_table_ids", False)

        # 如果结果表存在，则拆分为数组
        if table_ids:
            table_id_list = table_ids.split(",")
        else:
            # 如果结果表为空，则通过空间获取数据
            if "__" not in space_uid:
                raise CommandError(f"space_uid: {space_uid} must split '__'")
            space_type, space_id = space_uid.split("__")
            # 支持 0 业务过滤
            if space_id == "0":
                table_id_list = self._get_zero_space_table_id_list()
            else:
                table_id_list = self._get_real_space_table_id_list(space_type, space_id)

        table_id_list = self._refine_table_id_list(table_id_list)

        # 过滤已经接入 vm 的结果表
        table_id_list = list(
            models.AccessVMRecord.objects.filter(result_table_id__in=table_id_list).values_list(
                "result_table_id", flat=True
            )
        )

        # 打印出要禁用的结果表
        self.stdout.write(f"allow to disable table_id_list: {json.dumps(table_id_list)}")

        # 如果没有结果表或者仅校验结果表是否正确，则直接返回
        if not table_id_list or check_table_ids:
            return

        disable_influxdb_router_for_vm_table(
            table_id_list, options.get("switched_storage_id"), options.get("can_deleted")
        )

        self.stdout.write("disable influxdb router successfully")

    def _get_zero_space_table_id_list(self) -> List:
        """获取 0 空间下的单指标单表"""
        return list(models.ResultTable.objects.filter(bk_biz_id=0).values_list("table_id", flat=True))

    def _get_real_space_table_id_list(self, space_type: str, space_id: str) -> List:
        """获取真实存在空间的结果表"""
        data_ids = set(
            models.SpaceDataSource.objects.filter(space_type_id=space_type, space_id=space_id).values_list(
                "bk_data_id", flat=True
            )
        )
        return list(
            models.DataSourceResultTable.objects.filter(bk_data_id__in=data_ids)
            .values_list("table_id", flat=True)
            .distinct()
        )

    def _refine_table_id_list(self, table_id_list: List) -> List:
        """过滤对应的结果表，排除已经切换过的结果表"""
        # 排除掉已经停用的结果表
        vm_cluster_id_list = list(
            models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM).values_list(
                "cluster_id", flat=True
            )
        )
        proxy_storage_cluster_id_list = list(
            models.InfluxDBProxyStorage.objects.filter(proxy_cluster_id__in=vm_cluster_id_list).values_list(
                "id", flat=True
            )
        )
        return list(
            models.InfluxDBStorage.objects.filter(table_id__in=table_id_list)
            .exclude(influxdb_proxy_storage_id__in=proxy_storage_cluster_id_list)
            .values_list("table_id", flat=True)
        )
