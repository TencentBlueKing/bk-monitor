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

from django.db import migrations


def add_hostname_field(apps, *args, **kwargs):
    """添加 hostname 维度"""
    # 获取 model
    ResultTableField = apps.get_model("metadata", "ResultTableField")
    # 结果表及维度名称
    table_id = "system.load"
    field_name = "hostname"

    ResultTableField.objects.create(
        table_id=table_id,
        field_name=field_name,
        field_type="string",
        description="主机名",
        tag="dimension",
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0134_bcsclusterinfo_bk_env"),
    ]

    operations = [
        migrations.RunPython(add_hostname_field),
    ]
