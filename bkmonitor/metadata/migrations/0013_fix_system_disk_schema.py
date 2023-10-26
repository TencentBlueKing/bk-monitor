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


import copy
import logging

from django.db import migrations

logger = logging.getLogger("metadata")


fixed_fields_info = {"device_type": "设备类型", "mount_point": "挂载点"}


def fix_disk_schema(apps, schema_editor):
    ResultTableField = apps.get_model("metadata", "ResultTableField")
    system_disk_fields = ResultTableField.objects.filter(table_id="system.disk")
    device_name = system_disk_fields.filter(field_name="device_name")[0]
    for field_name, description in list(fixed_fields_info.items()):
        if not system_disk_fields.filter(field_name=field_name).exists():
            field_conf = copy.copy(device_name.__dict__)
            field_conf.update(
                {
                    "field_name": field_name,
                    "description": description,
                    "id": None,
                }
            )

            for prop in list(field_conf.keys()):
                if prop.startswith("_"):
                    field_conf.pop(prop)

            ResultTableField.objects.create(**field_conf)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0012_clean_description"),
    ]

    operations = [migrations.RunPython(fix_disk_schema)]
