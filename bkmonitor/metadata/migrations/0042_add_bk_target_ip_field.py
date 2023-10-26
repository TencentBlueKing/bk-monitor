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

models = {"ResultTableField": None, "ResultTable": None}


def add_bk_target_ip_field(apps, *args, **kwargs):
    """为system等内置的结果表增加bk_target_ip字段"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTableField = models["ResultTableField"]
    ResultTable = models["ResultTable"]

    for result_table in ResultTable.objects.filter(table_id__startswith="system."):
        ResultTableField.objects.create(
            table_id=result_table.table_id,
            field_name="bk_target_ip",
            field_type="string",
            description="目标IP",
            tag="dimension",
            is_config_by_user=True,
            creator="system",
            last_modify_user="system",
            # 字段别名，默认为空，以支持部分keyword
            alias_name="ip",
        )

        ResultTableField.objects.create(
            table_id=result_table.table_id,
            field_name="bk_target_cloud_id",
            field_type="string",
            description="目标机器云区域ID",
            tag="dimension",
            is_config_by_user=True,
            creator="system",
            last_modify_user="system",
            # 字段别名，默认为空，以支持部分keyword
            alias_name="cloud_id",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0041_time_tag_and_cmdb_level_block"),
    ]

    operations = [
        migrations.RunPython(add_bk_target_ip_field),
    ]
