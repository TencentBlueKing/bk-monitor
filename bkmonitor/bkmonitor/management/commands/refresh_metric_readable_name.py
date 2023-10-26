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

from bkmonitor.models import MetricListCache


class Command(BaseCommand):
    """刷新当前数据库中指标缓存的 Readable name"""

    def add_arguments(self, parser):
        parser.add_argument("refresh_existed", type=bool, help="是否强制刷新已有的可读名", default=False, nargs="?")

    def handle(self, *args, **options):
        refresh_existed = options.get("refresh_existed", False)

        skipped = saved = 0
        for metric in MetricListCache.objects.all():
            if metric.readable_name:
                if not refresh_existed:
                    print(f"metric<{metric.result_table_readable_name}> readable name existed, skip")
                    skipped += 1
                    continue

            metric.readable_name = metric.get_human_readable_name()
            metric.save()
            saved += 1
            print(f"metric<{metric.result_table_readable_name}> saved, readable name: {metric.readable_name} ")

        print(f"指标缓存可读名更新: {saved} saved, {skipped} skipped.")
