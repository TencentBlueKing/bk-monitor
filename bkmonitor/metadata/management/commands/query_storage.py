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

from django.core.management.base import BaseCommand, CommandError

from metadata.service.storage_details import ResultTableAndDataSource


class Command(BaseCommand):
    def handle(self, *args, **options):
        bk_data_id = options.get("bk_data_id")
        table_id = options.get("table_id")
        bcs_cluster_id = options.get("bcs_cluster_id")
        vm_table_id = options.get("vm_table_id")
        metric_name = options.get("metric_name")
        data_label = options.get("data_label")

        if not (bk_data_id or table_id or bcs_cluster_id or vm_table_id or data_label):
            raise Exception("参数[bk_data_id或table_id或集群]不能全部为空")

        # 如果指标名不为空，则集群ID必须存在(使用场景是通过集群ID+指标确认对应的结果表)
        if metric_name and not bcs_cluster_id:
            raise CommandError("参数[metric_name]存在时，参数[bcs_cluster_id]不能为空")

        self.stdout.write(
            json.dumps(
                ResultTableAndDataSource(
                    table_id=table_id,
                    bk_data_id=bk_data_id,
                    bcs_cluster_id=bcs_cluster_id,
                    vm_table_id=vm_table_id,
                    metric_name=metric_name,
                    data_label=data_label,
                    with_gse_router=options.get("with_gse_router", False),
                ).get_detail()
            )
        )

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, default=None, help="数据源ID")
        parser.add_argument("--table_id", type=str, default=None, help="结果表ID")
        parser.add_argument("--data_label", type=str, default=None, help="结果表别名")
        parser.add_argument("--bcs_cluster_id", type=str, help="BCS Cluster ID, 如: BCS-K8S-00000")
        parser.add_argument("--vm_table_id", type=str, default=None, help="接入计算平台 VM 结果表 ID")
        parser.add_argument("--metric_name", type=str, default=None, help="指标名称")
        parser.add_argument("--with_gse_router", action="store_true", help="是否返回 GSE 路由信息")
