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
from django.core.management.base import BaseCommand, CommandError

from metadata import models


class Command(BaseCommand):
    help = "refresh time series metric"

    def add_arguments(self, parser):
        parser.add_argument("--data_id", type=int, required=True, help="data source id")

    def handle(self, *args, **options):
        data_id = options.get("data_id")
        # 获取ts group
        try:
            ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=data_id)
        except models.TimeSeriesGroup.DoesNotExist:
            raise CommandError("data id not found from TimeSeriesGroup")
        # 从redis中同步数据到metadata
        ts_group.update_time_series_metrics()
        # TODO: 更新上游缓存或上游DB

        print("update time series metric successfully")
