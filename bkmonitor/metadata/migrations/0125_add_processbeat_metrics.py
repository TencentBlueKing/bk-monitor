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


def add_fieldlist(ResultTableField, table_id, fieldlist):
    for field in fieldlist:
        defaults = {
            "field_type": field["field_type"],
            "description": field["description"],
            "unit": field["unit"],
            "tag": field["tag"],
            "is_config_by_user": True,
            "creator": "system",
            "last_modify_user": "system",
        }
        ResultTableField.objects.update_or_create(table_id=table_id, field_name=field["field_name"], defaults=defaults)


def add_processbeat_metrics(apps, *args, **kwargs):
    # 获取APP models
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    additional_metrics = [
        # 3 个 CPU 指标
        {
            "field_name": "cpu_user",
            "field_type": "double",
            "description": "进程占用用户态时间",
            "tag": "metric",
            "unit": "s",
        },
        {
            "field_name": "cpu_system",
            "field_type": "double",
            "description": "进程占用系统态时间",
            "tag": "metric",
            "unit": "s",
        },
        {
            "field_name": "cpu_total_ticks",
            "field_type": "double",
            "description": "整体占用时间",
            "tag": "metric",
            "unit": "s",
        },

        # 2 个 FD 指标
        {
            "field_name": "fd_limit_soft",
            "field_type": "double",
            "description": "fd_limit_soft",
            "tag": "metric",
            "unit": "short",
        },
        {
            "field_name": "fd_limit_hard",
            "field_type": "double",
            "description": "fd_limit_hard",
            "tag": "metric",
            "unit": "short",
        },

        # 4 个 IO 指标
        {
            "field_name": "io_read_bytes",
            "field_type": "double",
            "description": "进程io累计读",
            "tag": "metric",
            "unit": "bytes",
        },
        {
            "field_name": "io_write_bytes",
            "field_type": "double",
            "description": "进程io累计写",
            "tag": "metric",
            "unit": "bytes",
        },
        {
            "field_name": "io_read_speed",
            "field_type": "double",
            "description": "进程io读速率",
            "tag": "metric",
            "unit": "Bps",
        },
        {
            "field_name": "io_write_speed",
            "field_type": "double",
            "description": "进程io写速率",
            "tag": "metric",
            "unit": "Bps",
        },
    ]

    add_fieldlist(ResultTableField, "system.proc", additional_metrics)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0124_auto_20220722_1436"),
    ]

    operations = [migrations.RunPython(add_processbeat_metrics)]
