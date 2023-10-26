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

logger = logging.getLogger("metadata")

models = {
    "ClusterInfo": None,
    "DataSource": None,
    "ResultTableField": None,
    "ResultTable": None,
    "DataSourceResultTable": None,
    "KafkaTopicInfo": None,
    "InfluxDBStorage": None,
    "Label": None,
}


def init_datasource_label(apps, schema_editor):
    """增加默认的label信息"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    DataSource = models["DataSource"]

    # 现有的所有数据源，都是时序数据且是蓝鲸监控的数据
    DataSource.objects.all().update(type_label="time_series", source_label="bk_monitor")

    # 但是有几个事件的数据源，需要独立的修改类型标签
    event_datasource = DataSource.objects.get(bk_data_id=1100000)
    event_datasource.type_label = "bk_event"
    event_datasource.save()

    event_datasource = DataSource.objects.get(bk_data_id=1100001)
    event_datasource.type_label = "bk_event"
    event_datasource.save()

    event_datasource = DataSource.objects.get(bk_data_id=1100002)
    event_datasource.type_label = "bk_event"
    event_datasource.save()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0027_auto_20190904_1723"),
    ]

    operations = [
        migrations.RunPython(init_datasource_label),
    ]
