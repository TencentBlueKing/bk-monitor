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

# -*- coding: utf-8 -*-


from django.db import migrations, models


def update_ping_datasource_description(apps, schema_editor):
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    ResultTableField.objects.filter(
        table_id="uptimecheck.icmp",
        field_name="task_duration",
    ).update(description="响应时间")

    ResultTableField.objects.filter(
        table_id="uptimecheck.icmp",
        field_name="available",
    ).update(description="单点可用率")

    ResultTableField.objects.filter(
        table_id="uptimecheck.icmp",
        field_name="min_rtt",
    ).update(description="最小时延")

    ResultTableField.objects.filter(
        table_id="uptimecheck.icmp",
        field_name="avg_rtt",
    ).update(description="平均时延")


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0065_merge_20200617_1730"),
    ]

    operations = [migrations.RunPython(update_ping_datasource_description)]
