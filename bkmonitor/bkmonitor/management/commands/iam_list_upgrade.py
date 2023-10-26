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

from bkmonitor.iam.upgrade import UpgradeManager


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "args", metavar="bk_biz_id", nargs="*", help="business to list upgrade, default for all business"
        )

    def handle(self, *bk_biz_ids, **kwargs):
        manager = UpgradeManager()

        bk_biz_ids = bk_biz_ids or sorted(list(manager.biz_info.keys()))

        for index, bk_biz_id in enumerate(bk_biz_ids, start=1):
            upgrade_info = manager.get_upgrade_info(bk_biz_id=int(bk_biz_id))
            print(f"\n##### show upgrade info: [{upgrade_info['bk_biz_id']}]({upgrade_info['bk_biz_name']}) #####")
            print(f"Write Users: {json.dumps(list(upgrade_info['users_with_write_permission']))}")
            print(f"Read Users: {json.dumps(list(upgrade_info['users_with_read_permission']))}")
