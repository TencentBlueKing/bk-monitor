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


from django.apps import apps
from django.core.management.base import BaseCommand

from bkmonitor.strategy.migrate import update_notice_template
from constants import alert as alert_constants


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk-biz_ids", nargs="*", help="business to upgrade, default for all business")

        parser.add_argument("-r", "--rollback", action="store_true", help="Rollback")

    def handle(self, *args, **kwargs):

        bk_biz_ids = kwargs.get("bk_biz_ids")
        is_rollback: bool = kwargs.get("rollback", False)

        print(f"[update_notice_template] bk_biz_ids -> {bk_biz_ids}, rollback -> {is_rollback}")

        old, new = alert_constants.OLD_DEFAULT_TEMPLATE, alert_constants.DEFAULT_TEMPLATE
        if is_rollback:
            old, new = new, old

        try:
            update_notice_template(apps, old, new, bk_biz_ids)
        except Exception as e:
            print(f"[update_notice_template] failed: error -> {e}")
        else:
            print("[update_notice_template] success")
