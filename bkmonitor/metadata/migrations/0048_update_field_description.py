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


import json
import logging

from django.db import migrations

logger = logging.getLogger("metadata")

models = {"ResultTableField": None, "ResultTable": None, "DataSource": None}


def update_description(apps, schema_editor):

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    with open("./metadata/data/description_append.json", "r", encoding="utf-8") as unit_file:
        field_list = json.load(unit_file)

    # 遍历获取所有的字段
    for field_info in field_list:
        # 转换结果表ID
        table_id = field_info["result_table_id"]
        field_name = field_info["item"]

        # 更新field信息
        try:
            field_object = models["ResultTableField"].objects.get(table_id=table_id, field_name=field_name)
        except models["ResultTableField"].DoesNotExist:
            print("table->[{}] field->[{}] is missing".format(table_id, field_name))
            continue

        field_object.description = field_info["item_display"]
        field_object.save()

        # 更新table_name信息
        try:
            table_object = models["ResultTable"].objects.get(table_id=table_id)
        except models["ResultTable"].DoesNotExist:
            print("table->[%s] is missing" % table_id)
            continue

        table_object.table_name_zh = field_info["table_name_zh"]
        table_object.save()


def total_run(apps, schema_editor):

    update_description(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0047_auto_20191126_1135"),
    ]

    operations = [migrations.RunPython(total_run)]
