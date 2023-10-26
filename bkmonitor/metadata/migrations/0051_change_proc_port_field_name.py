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


from django.db import migrations, models


def change_label_and_field_name(apps, schema_editor):
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    ResultTableField.objects.filter(
        table_id="system.proc_port",
        field_name="listen",
    ).update(description="监听中的端口")

    ResultTableField.objects.filter(
        table_id="system.proc_port",
        field_name="nonlisten",
    ).update(description="未监听的端口")

    ResultTableField.objects.filter(
        table_id="system.proc_port",
        field_name="not_accurate_listen",
    ).update(description="监听IP不匹配的端口")


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0050_change_label_and_field_name"),
    ]

    operations = [migrations.RunPython(change_label_and_field_name)]
