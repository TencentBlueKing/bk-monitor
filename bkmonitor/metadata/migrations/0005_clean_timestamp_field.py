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


def clean_timestamp(apps, schema_editor):
    """清理初始化元数据内容中，多余时间字段"""

    # 获取所有的时间字段，只保留time字段
    result_table_field = apps.get_model("metadata", "ResultTableField")

    field_list = result_table_field.objects.filter(field_type="timestamp").exclude(field_name="time")
    logger.info("total all field_list->[%s]" % field_list.count())

    field_list.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0004_resulttablefield_description"),
    ]

    operations = [migrations.RunPython(clean_timestamp)]
