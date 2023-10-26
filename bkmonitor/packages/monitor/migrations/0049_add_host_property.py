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


def add_host_property(apps, schema_editor):
    HostProperty = apps.get_model("monitor", "HostProperty")
    HostProperty.objects.get_or_create(
        property="psc_mem_usage",
        defaults={
            "property_display": "物理内存使用率",
        },
    )
    HostProperty.objects.get_or_create(
        property="mem_usage",
        defaults={
            "property_display": "应用内存使用率",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0048_auto_20181011_0026"),
    ]

    operations = [migrations.RunPython(add_host_property)]
