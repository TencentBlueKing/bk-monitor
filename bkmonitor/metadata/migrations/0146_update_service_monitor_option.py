# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

from django.db import migrations


def update_service_monitor_option_value(apps, *args, **kwargs):
    ResultTableOption = apps.get_model("metadata", "ResultTableOption")

    # 更新 option 名称为 dimension_values，值为'["bk_monitor_name"]'的记录
    # 设置值类型为 list
    value = json.dumps(["bk_monitor_name"])
    ResultTableOption.objects.filter(name="dimension_values", value=value).update(value_type="list")


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0145_auto_20230301_1640"),
    ]

    operations = [
        migrations.RunPython(update_service_monitor_option_value),
    ]
