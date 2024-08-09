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
from django.db.models import Q

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem


class Command(BaseCommand):
    help = "查询使用消息队列的数据源 ID"

    def add_arguments(self, parser):
        parser.add_argument("--domain_name", type=str, help="消息队列域名")

    def handle(self, *args, **options):
        domain_name = options["domain_name"]
        obj = models.ClusterInfo.objects.filter(domain_name=domain_name).first()
        if not obj:
            raise CommandError(f"not found cluster info by domain name: {domain_name}")

        # 筛选出需要删除Consul配置的数据源(已停用/已迁移)
        data_sources_to_delete = models.DataSource.objects.filter(
            Q(mq_cluster_id=obj.cluster_id)
            & (Q(is_enable=False) | Q(created_from=DataIdCreatedFromSystem.BKDATA.value))
        )

        # 执行Consul删除操作
        for data_source in data_sources_to_delete:
            data_source.delete_consul_config()

        # 筛选出剩余有效的数据源
        remaining_data_sources = models.DataSource.objects.filter(mq_cluster_id=obj.cluster_id).exclude(
            Q(is_enable=False) | Q(created_from=DataIdCreatedFromSystem.BKDATA.value)
        )

        # 获取剩余数据源的ID列表
        remaining_data_source_ids = remaining_data_sources.values_list("bk_data_id", flat=True)

        # 返回剩余的数据源ID列表
        self.stdout.write(json.dumps(list(remaining_data_source_ids)))
