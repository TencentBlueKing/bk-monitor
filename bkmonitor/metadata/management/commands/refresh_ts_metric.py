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

    def get_data_id_by_table_id(self, table_id):
        try:
            bk_data_id = models.DataSourceResultTable.objects.get(table_id=table_id).bk_data_id
        except models.DataSourceResultTable.DoesNotExist:
            raise CommandError("table_id: %s not found from DataSourceResultTable" % table_id)
        return bk_data_id

    def handle(self, *args, **options):
        data_id = options.get("data_id")
        table_id = options.get("table_id")
        # Ensure at least one of `data_id` or `table_id` is provided
        if not data_id and not table_id:
            raise CommandError("You must provide at least one of --data_id or --table_id.")

        if not data_id:
            data_id = self.get_data_id_by_table_id(table_id)

        client = SpaceTableIDRedis()
        self.stdout.write("data id: %s start to refresh metric router" % data_id)
        try:
            ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=data_id)
        except models.TimeSeriesGroup.DoesNotExist:
            raise CommandError("data_id: %s not found from TimeSeriesGroup" % data_id)
        ts_group.update_time_series_metrics()
        self.stdout.write("data id: %s start to push redis data" % data_id)
        client.push_table_id_detail(table_id_list=[ts_group.table_id], is_publish=True)
        self.stdout.write("data id: %s refresh metric router successfully" % data_id)

        self.stdout.write("update time series metric successfully")
