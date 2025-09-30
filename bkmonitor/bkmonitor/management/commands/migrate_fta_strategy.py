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

from django.core.management.base import BaseCommand
from fta_web.handlers import migrate_fta_strategy


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "args", metavar="bk_biz_ids", nargs="*", help="business to migrate, default for all business"
        )

    def handle(self, *args, **kwargs):
        bk_biz_ids = [int(biz) for biz in args[0].split(",") if biz] if args else []
        migrate_fta_strategy(sender="shell", **{"bk_biz_ids": bk_biz_ids})
