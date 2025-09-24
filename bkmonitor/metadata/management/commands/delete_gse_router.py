# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from bkmonitor.utils import consul
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config, models


class Command(BaseCommand):
    help = "delete gse router for data_ids"

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_ids", help="数据源ID，多个以半角逗号分隔")
        parser.add_argument("--force", action="store_true", help="强制删除路由")

    def handle(self, *args, **options):
        bk_data_ids, is_force = options["bk_data_ids"], options.get("force")
        if not bk_data_ids:
            self.stderr.write("bk_data_ids is empty")
            return
        data_id_list = [int(data_id) for data_id in bk_data_ids.split(",")]
        can_delete = self._can_delete_gse_router(data_id_list, is_force)
        if not can_delete:
            return
        self._delete_gse_router(data_id_list)

    def _can_delete_gse_router(self, data_id_list: List, is_force: bool) -> bool:
        """检查数据源可以删除路由

        - 是否强制删除，如果强制返回，则直接返回，否则检查下面两个
        - 数据源必须处于被禁用状态
        """
        if is_force:
            # 设置数据源状态为 disabled
            models.DataSource.objects.filter(bk_data_id__in=data_id_list).update(is_enable=False)
            return True

        data_ids = set(
            models.DataSource.objects.filter(
                Q(bk_data_id__in=data_id_list, is_enable=False)
                | Q(data_name__regex=r"_delete_[0-9]{14}$", bk_data_id__in=data_id_list)
            ).values_list("bk_data_id", flat=True)
        )

        # 如果存在差异，需要先检查数据源，再重试
        diff = set(data_id_list) - data_ids
        if diff:
            self.stderr.write(f"删除GSE路由失败, 数据源 {json.dumps(diff)} 处于运行状态，不能删除路由")
            return False

        return True

    def _delete_gse_router(self, data_id_list: List) -> bool:
        """删除数据源的路由"""
        is_successful, successful_data_ids_list, failed_data_ids_list = True, [], []
        for data_id in data_id_list:
            params = {
                "condition": {"channel_id": data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
                "operation": {"operator_name": settings.COMMON_USERNAME, "method": "all"},
            }
            try:
                api.gse.delete_route(params)
                successful_data_ids_list.append(data_id)
            except BKAPIError:
                failed_data_ids_list.append(data_id)
                is_successful = False

        if not is_successful:
            self.stderr.write(f"删除GSE路由失败, 失败的data_ids: {json.dumps(failed_data_ids_list)}")
            return False

        consul_client = consul.BKConsul()
        # 再删除一遍consul，避免直接更改数据库，没有删除consul的场景
        is_delete_consul_successful, failed_delete_consul_list = True, []

        for obj in models.DataSource.objects.filter(bk_data_id__in=successful_data_ids_list):
            try:
                consul_client.kv.delete(obj.consul_config_path)
            except Exception:
                failed_delete_consul_list.append(obj.bk_data_id)
                is_delete_consul_successful = False

        if not is_delete_consul_successful:
            self.stderr.write(f"删除Consul配置失败, 失败的data_ids: {json.dumps(failed_delete_consul_list)}")
            return False

        self.stdout.write("删除GSE和清理consul配置成功!")
        return True
