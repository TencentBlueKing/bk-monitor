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

from django.conf import settings
from django.db import migrations

from metadata.migration_util import models

logger = logging.getLogger("metadata")


def change_custom_report_aggregation_datasource(apps, *args, **kwargs):
    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    data_id = 1100014
    # 实际influxdb对应的数据库名
    database = "datalink_stats"
    # data_id对应的名称
    data_name = f"{settings.AGGREGATION_BIZ_ID}_{database}"
    # 结果表id
    old_table_id = "bkmonitorbeat_statistics.__default__"
    table_id = f"{database}.__default__"
    # 来源标签
    source_label = "datalink"

    # 修改data_name和source_label
    models["DataSource"].objects.filter(bk_data_id=data_id).update(
        data_name=data_name,
        source_label=source_label,
        data_description="init data_source for %s" % data_name,
    )
    # 修改table_id
    table_id_models = [
        "DataSourceResultTable",
        "ResultTable",
        "ResultTableField",
        "InfluxDBStorage",
        "TimeSeriesGroup",
        "ResultTableOption",
    ]
    for name in table_id_models:
        models[name].objects.filter(table_id=old_table_id).update(
            table_id=table_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0127_merge_20220901_1544"),
    ]

    operations = [
        migrations.RunPython(change_custom_report_aggregation_datasource, reverse_code=migrations.RunPython.noop),
    ]
