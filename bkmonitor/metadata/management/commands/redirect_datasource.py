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

from django.core.management.base import BaseCommand

from metadata.models import DataSource


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--data_id", type=int, nargs="*", help="dataid list to redirecrt eg: 1001 1002")
        parser.add_argument("--data_name", type=str, help="data_name to redirect eg: bklog")
        parser.add_argument("--target_type", type=str, help="target path to redirecrt eg: bk_log")

    def handle(self, *args, **options):
        data_ids = options["data_id"]
        data_name = options["data_name"]
        target_type = options["target_type"]
        # 优先使用dataid
        if len(data_ids) != 0:
            self.stdout.write(f"start redirect data_id->[{str(data_ids)}] to [{target_type}]")
            datasources = DataSource.objects.filter(bk_data_id__in=data_ids)
        else:
            self.stdout.write(f"start redirect data_name->[{str(data_name)}] to [{target_type}]")
            datasources = DataSource.objects.filter(data_name__contains=data_name)

        # 记录影响到的dataid，供日志使用
        data_id_record = []
        for datasource in datasources:
            data_id_record.append(datasource.bk_data_id)
            datasource.redirect_consul_config(target_type)
        self.stdout.write(f"redirect dataid->[{str(data_id_record)}] to [{target_type}] all done")
