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
        ("monitor", "0022_metricconf_metricmonitor"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardMenu",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("name", models.CharField(default=b"", max_length=32, verbose_name="\u4eea\u8868\u76d8\u540d\u79f0")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DashboardMenuLocation",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("menu_id", models.IntegerField(verbose_name="\u4eea\u8868\u76d8\u83dc\u5355id")),
                ("view_id", models.IntegerField(verbose_name="\u4eea\u8868\u76d8\u89c6\u56feid")),
                ("view_index", models.IntegerField(default=999, verbose_name="\u89c6\u56fe\u5c55\u793a\u987a\u5e8f")),
                ("view_size", models.IntegerField(default=12, verbose_name="\u89c6\u56fe\u5927\u5c0f")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DashboardView",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("name", models.CharField(default=b"", max_length=32, verbose_name="\u89c6\u56fe\u540d\u79f0")),
                (
                    "graph_type",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u56fe\u8868\u7c7b\u578b",
                        choices=[
                            (b"time", "\u65f6\u95f4\u5e8f\u5217"),
                            (b"top", "TOP\u6392\u884c"),
                            (b"status", "\u72b6\u6001\u503c"),
                        ],
                    ),
                ),
                ("metrics", models.TextField(verbose_name="\u6307\u6807\u9879")),
                ("symbols", models.TextField(verbose_name="\u6807\u8bb0")),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
