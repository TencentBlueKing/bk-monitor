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

import logging

from django.db import migrations

from metadata.models import InfluxDBStorage

logger = logging.getLogger("metadata")


def change_custom_report_aggregation_datasource(apps, *args, **kwargs):

    # 实际influxdb对应的数据库名
    database = "datalink_stats"
    # 结果表id
    table_id = f"{database}.__default__"

    InfluxDBStorage.objects.filter(table_id=table_id).update(
        database=database,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0130_add_system_mem_shared"),
    ]

    operations = [
        migrations.RunPython(change_custom_report_aggregation_datasource, reverse_code=migrations.RunPython.noop),
    ]
