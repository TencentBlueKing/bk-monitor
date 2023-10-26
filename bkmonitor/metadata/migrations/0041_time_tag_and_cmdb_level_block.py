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
    "ResultTableFieldOption": None,
    "ResultTableField": None,
}


def add_disabled_cmdb_level_option(apps, *args, **kwargs):
    """增加默认CMDB_LEVEL不必写入的逻辑"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTableField = models["ResultTableField"]
    ResultTableFieldOption = models["ResultTableFieldOption"]

    for result_table_field in ResultTableField.objects.filter(field_name="bk_cmdb_level"):
        ResultTableFieldOption.objects.create(
            value_type="bool",
            value="true",
            creator="system",
            table_id=result_table_field.table_id,
            field_name="bk_cmdb_level",
            name="influxdb_disabled",
        )


def add_timestamp_tag(apps, *args, **kwargs):
    """增加时间字段的tag内容"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTableField = models["ResultTableField"]
    for result_table_field in ResultTableField.objects.filter(field_name="time"):

        result_table_field.tag = "timestamp"
        result_table_field.save()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0040_clusterinfo_registered_system"),
    ]

    operations = [
        migrations.RunPython(add_disabled_cmdb_level_option),
        migrations.RunPython(add_timestamp_tag),
    ]
