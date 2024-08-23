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
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "refresh time series metric"

    def add_arguments(self, parser):
        parser.add_argument("--data_id", type=int, required=False, help="data source id or table_id")
        parser.add_argument("--table_id", type=str, required=False, help="table id")
        parser.add_argument("--force", action="store_true", help="force refresh")

    def handle(self, *args, **options):
        data_id = options.get("data_id")
        table_id = options.get("table_id")
        force = options.get("force")
        client = SpaceTableIDRedis()
        if data_id:
            try:
                self.stdout.write("data id: %s start to refresh metric router" % data_id)
                ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=data_id)
                ts_group.update_time_series_metrics()
                self.stdout.write("data id: %s start to push redis data" % data_id)
                client.push_table_id_detail(table_id_list=[ts_group.table_id], is_publish=True)
                self.stdout.write("data id: %s refresh metric router successfully" % data_id)
                return
            except models.TimeSeriesGroup.DoesNotExist:
                raise CommandError("data id not found from TimeSeriesGroup")

        if table_id:
            try:
                self.stdout.write("table id: %s start to refresh metric router" % table_id)
                ts_group = models.TimeSeriesGroup.objects.get(table_id=table_id)
                ts_group.update_time_series_metrics()
                self.stdout.write("table id: %s start to push redis data" % table_id)
                client.push_table_id_detail(table_id_list=[ts_group.table_id], is_publish=True)
                self.stdout.write("table id: %s refresh metric router successfully" % table_id)
                return
            except models.TimeSeriesGroup.DoesNotExist:
                raise CommandError("table id not found from TimeSeriesGroup")

        if force:
            self.stdout.write("start to force refresh metric router")
            tid_list = []
            for ts_group in models.TimeSeriesGroup.objects.all():
                try:
                    ts_group.update_time_series_metrics()
                    tid_list.append(ts_group.table_id)
                except models.TimeSeriesGroup.DoesNotExist:
                    self.stdout.write("table id: %s refresh metric router failed" % ts_group.table_id)
                    continue

            client.push_table_id_detail(table_id_list=tid_list, is_publish=True)

        self.stdout.write("update time series metric successfully")
