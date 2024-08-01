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

from metadata import models


class Command(BaseCommand):
    help = "查询使用消息队列的数据源 ID"

    def add_arguments(self, parser):
        parser.add_argument("--domain_name", type=str, help="消息队列域名")

    def handle(self, *args, **options):
        domain_name = options["domain_name"]
        obj = models.ClusterInfo.objects.filter(domain_name=domain_name).first()
        if not obj:
            raise CommandError(f"not found cluster info by domain name: {domain_name}")
        self.stdout.write(
            json.dumps(
                models.DataSource.objects.filter(mq_cluster_id=obj.cluster_id).values_list("bk_data_id", flat=True)
            )
        )
