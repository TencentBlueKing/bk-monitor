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

from metadata import models


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--domains", type=str, help="集群的域名或ip，多个以半角逗号分隔")

    def handle(self, *args, **options):
        domains = options.get("domains")
        if not domains:
            self.stdout.write("please input domains")
            return

        # 转换为数据
        domain_list = domains.split(",")
        data = list(models.ClusterInfo.objects.filter(domain_name__in=domain_list).values())
        self.stdout.write(json.dumps(data))
