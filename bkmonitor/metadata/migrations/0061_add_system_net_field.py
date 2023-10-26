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


def add_system_net_field(apps, schema_editor):

    ResultTableField = apps.get_model("metadata", "ResultTableField")

    ResultTableField.objects.create(
        table_id="system.net",
        field_name="speed_recv_bit",
        field_type="float",
        description="网卡入流量比特速率",
        unit="bps",
        tag="metric",
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )

    ResultTableField.objects.create(
        table_id="system.net",
        field_name="speed_sent_bit",
        field_type="float",
        description="网卡出流量比特速率",
        unit="bps",
        tag="metric",
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0060_prechange_buildin_field_unit"),
    ]

    operations = [migrations.RunPython(add_system_net_field)]
