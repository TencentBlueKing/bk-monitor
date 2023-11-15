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

from metadata.service.storage_details import ResultTableAndDataSource


class Command(BaseCommand):
    def handle(self, *args, **options):
        bk_data_id = options.get("bk_data_id")
        table_id = options.get("table_id")
        bcs_cluster_id = options.get("bcs_cluster_id")
        if not (bk_data_id or table_id or bcs_cluster_id):
            raise Exception("参数[bk_data_id或table_id或集群]不能全部为空")
        self.stdout.write(json.dumps(ResultTableAndDataSource(table_id, bk_data_id, bcs_cluster_id).get_detail()))

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, default=None, help="数据源ID")
        parser.add_argument("--table_id", type=str, default=None, help="结果表ID")
        parser.add_argument("--bcs_cluster_id", type=str, help="BCS Cluster ID, 如: BCS-K8S-00000")
