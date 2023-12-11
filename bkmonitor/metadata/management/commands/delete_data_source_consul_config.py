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
        parser.add_argument("--data_ids", type=int, nargs="*", default=[], help="bk_data_id list")

    def handle(self, *args, **options):
        # 清除指定数据源的consul配置信息
        data_ids = options.get("data_ids")

        for ds in DataSource.objects.filter(bk_data_id__in=data_ids):
            try:
                ds.delete_consul_config()
            except Exception as e:
                self.stdout.write(f"delete {ds.bk_data_id} consul config failed, {e}")

        self.stdout.write("[delete_data_source_consul_config] DONE!")
