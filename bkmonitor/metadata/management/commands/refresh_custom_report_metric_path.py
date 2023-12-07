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

from metadata import config, models


def update_metrics_report_path_option(data_id):
    """
    更新数据源指标上报路径
    :param data_id: 数据源ID
    """
    res = models.DataSourceOption.objects.filter(
        bk_data_id=data_id,
        name="metrics_report_path",
    ).update(value="{}/influxdb_metrics/{}/time_series_metric".format(config.CONSUL_PATH, data_id))

    if not res:
        models.DataSourceOption.objects.create(
            bk_data_id=data_id,
            name="metrics_report_path",
            value_type="string",
            value="{}/influxdb_metrics/{}/time_series_metric".format(config.CONSUL_PATH, data_id),
            creator="system",
        )


class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. 更新聚合网关report path
        update_metrics_report_path_option(1100011)

        # 2. 更新运营数据上报report path
        update_metrics_report_path_option(1100012)

        # 3. 更新新版运营数据上报report path
        update_metrics_report_path_option(1100013)

        self.stdout.write("all data_id refresh report path option done.")
