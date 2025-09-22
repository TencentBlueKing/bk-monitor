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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config


class Command(BaseCommand):
    help = "delete spec gse router"

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, help="数据源ID")
        parser.add_argument("--router_names", help="要删除的路由名称，多个以半角逗号分隔")

    def handle(self, *args, **options):
        bk_data_id = options["bk_data_id"]
        router_names = options["router_names"]
        if not (bk_data_id and router_names):
            raise CommandError("params [bk_data_id] and [router_names] are required")
        router_name_list = router_names.split(",")
        # 处理路由名称
        params = {
            "condition": {"channel_id": bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.COMMON_USERNAME, "method": "specification"},
            "specification": {"route": router_name_list},
        }
        try:
            api.gse.delete_route(params)
        except BKAPIError as e:
            raise CommandError(f"delete spec gse router failed, params: {params}, error: {e}")

        # 返回剩余的路由
        params = {
            "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": bk_data_id},
            "operation": {"operator_name": settings.COMMON_USERNAME},
        }
        try:
            remained_router = api.gse.query_route(params)
        except BKAPIError as e:
            # 当已经不存在时，正常返回
            if "not found" in e.message or e.code in [1014505, 1014003]:
                self.stdout.write("no spec gse router remained")
                return
            raise CommandError(f"get spec gse router failed, params: {params}, error: {e}")

        self.stdout.write(self.style.SUCCESS("delete spec gse router success"))
        self.stdout.write(f"remained router: {json.dumps(remained_router)}")
