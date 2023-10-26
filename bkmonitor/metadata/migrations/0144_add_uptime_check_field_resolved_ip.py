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

from metadata.migration_util import add_resulttablefield

logger = logging.getLogger("metadata")

models = {"ResultTableField": None, "ResultTable": None, "DataSource": None}


def add_uptime_check_field_resolved_ip(apps, schema_editor):
    """拨测结果表增加字段resolved_ip"""

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    fields = [
        {
            "field_name": "resolved_ip",
            "field_type": "string",
            "unit": "",
            "tag": "dimension",
            "description": "请求域名解析结果IP",
        }
    ]
    # 结果表id
    table_ids = [
        "uptimecheck.tcp",
        "uptimecheck.udp",
        "uptimecheck.http",
        "uptimecheck.icmp",
    ]
    # 数据库记录的操作员
    user = "system"
    for table_id in table_ids:
        for field in fields:
            qs = models["ResultTableField"].objects.filter(table_id=table_id, field_name=field["field_name"])
            if not qs.exists():
                add_resulttablefield(models, table_id, [field], user)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0143_add_apm_label_info"),
    ]

    operations = [migrations.RunPython(add_uptime_check_field_resolved_ip)]
