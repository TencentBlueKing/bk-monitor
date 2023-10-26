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


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0025_merge"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dashboardmenu",
            name="create_user",
            field=models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="dashboardmenu",
            name="update_user",
            field=models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="dashboardmenulocation",
            name="create_user",
            field=models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="dashboardmenulocation",
            name="update_user",
            field=models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="dashboardview",
            name="create_user",
            field=models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="dashboardview",
            name="update_user",
            field=models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="metricmonitor",
            name="create_user",
            field=models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
        ),
        migrations.AlterField(
            model_name="metricmonitor",
            name="update_user",
            field=models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True),
        ),
    ]
