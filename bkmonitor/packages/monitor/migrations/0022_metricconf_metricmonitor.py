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
        ("monitor", "0021_componentinstance"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetricConf",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("category", models.CharField(max_length=32, verbose_name="\u6307\u6807\u5927\u7c7b")),
                ("metric", models.CharField(max_length=128, verbose_name="\u6307\u6807id")),
                ("metric_type", models.CharField(max_length=128, verbose_name="\u6307\u6807\u5206\u7c7b")),
                ("description", models.CharField(max_length=128, verbose_name="\u6307\u6807\u8bf4\u660e")),
                ("display", models.TextField(verbose_name="\u6307\u6807\u8be6\u7ec6\u5c55\u793a")),
                ("index", models.FloatField(default=0, verbose_name="\u6307\u6807\u987a\u5e8findex")),
                ("conversion", models.FloatField(default=1.0, verbose_name="\u6362\u7b97\u9664\u6570")),
                (
                    "conversion_unit",
                    models.CharField(default=b"", max_length=32, verbose_name="\u8f6c\u6362\u5355\u4f4d", blank=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MetricMonitor",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("view_id", models.IntegerField(verbose_name="\u4eea\u8868\u76d8\u89c6\u56feid")),
                ("metric_id", models.CharField(max_length=36, verbose_name="\u6307\u6807id")),
                ("monitor_id", models.IntegerField(verbose_name="\u76d1\u63a7\u9879id")),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
