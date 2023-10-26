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
        ("monitor", "0007_callmethodrecord_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorLocation",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.CharField(max_length=100, verbose_name="\u4e1a\u52a1ID")),
                ("menu_id", models.IntegerField(verbose_name="\u83dc\u5355id")),
                ("monitor_id", models.IntegerField(verbose_name="\u76d1\u63a7id")),
                (
                    "graph_index",
                    models.IntegerField(
                        default=9999999, verbose_name="\u56fe\u8868\u6240\u5728\u680f\u76ee\u4f4d\u7f6e"
                    ),
                ),
                ("width", models.IntegerField(default=6, verbose_name="\u5bbd\u5ea6")),
            ],
            options={
                "db_table": "ja_monitor_location",
                "verbose_name": "\u76d1\u63a7\u6620\u5c04",
                "verbose_name_plural": "\u76d1\u63a7\u6620\u5c04",
            },
        ),
        migrations.CreateModel(
            name="ScenarioMenu",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "system_menu",
                    models.CharField(
                        default=b"",
                        max_length=32,
                        verbose_name="\u7cfb\u7edf\u83dc\u5355\u680f",
                        choices=[
                            ("", "\u7528\u6237\u81ea\u5b9a\u4e49"),
                            ("favorite", "\u5173\u6ce8"),
                            ("default", "\u9ed8\u8ba4\u5206\u7ec4"),
                        ],
                    ),
                ),
                ("biz_id", models.CharField(max_length=100, verbose_name="\u4e1a\u52a1ID")),
                ("menu_name", models.CharField(max_length=255, verbose_name="\u83dc\u5355\u540d")),
                ("menu_index", models.IntegerField(default=999, verbose_name="\u83dc\u5355\u987a\u5e8f")),
            ],
            options={
                "db_table": "ja_scenario_menu",
                "verbose_name": "\u5de6\u4fa7\u83dc\u5355",
                "verbose_name_plural": "\u5de6\u4fa7\u83dc\u5355",
            },
        ),
    ]
