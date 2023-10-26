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

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0020_rolepermission"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportDetail",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("name", models.CharField(max_length=100, verbose_name="\u914d\u7f6e\u540d\u79f0")),
                (
                    "type",
                    models.CharField(
                        max_length=100,
                        verbose_name="\u914d\u7f6e\u7c7b\u578b",
                        choices=[
                            ("plugin", "\u63d2\u4ef6\u914d\u7f6e"),
                            ("collect", "\u91c7\u96c6\u914d\u7f6e"),
                            ("strategy", "\u7b56\u7565\u914d\u7f6e"),
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=100, verbose_name="\u6807\u7b7e", blank=True)),
                ("history_id", models.IntegerField(verbose_name="\u5bf9\u5e94\u7684\u5bfc\u5165\u5386\u53f2ID")),
                (
                    "config_id",
                    models.CharField(max_length=100, null=True, verbose_name="\u751f\u6210\u7684\u914d\u7f6eID"),
                ),
                (
                    "import_status",
                    models.CharField(
                        max_length=100,
                        verbose_name="\u5bfc\u5165\u72b6\u6001",
                        choices=[
                            ("importing", "\u5bfc\u5165\u4e2d"),
                            ("success", "\u5bfc\u5165\u6210\u529f"),
                            ("failed", "\u5bfc\u5165\u5931\u8d25"),
                        ],
                    ),
                ),
                (
                    "error_msg",
                    models.CharField(max_length=255, verbose_name="\u6587\u4ef6\u9519\u8bef\u4fe1\u606f", blank=True),
                ),
                ("parse_id", models.IntegerField(verbose_name="\u89e3\u6790ID")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ImportHistory",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "status",
                    models.CharField(
                        max_length=100,
                        verbose_name="\u5bfc\u5165\u72b6\u6001",
                        choices=[("imported", "\u5bfc\u5165\u5b8c\u6210"), ("importing", "\u5bfc\u5165\u4e2d")],
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ImportParse",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("name", models.CharField(max_length=100, verbose_name="\u914d\u7f6e\u540d\u79f0")),
                (
                    "type",
                    models.CharField(
                        max_length=100,
                        verbose_name="\u914d\u7f6e\u7c7b\u578b",
                        choices=[
                            ("plugin", "\u63d2\u4ef6\u914d\u7f6e"),
                            ("collect", "\u91c7\u96c6\u914d\u7f6e"),
                            ("strategy", "\u7b56\u7565\u914d\u7f6e"),
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=100, verbose_name="\u6807\u7b7e", blank=True)),
                (
                    "uuid",
                    models.CharField(
                        max_length=100, verbose_name="\u6587\u4ef6\u89e3\u6790\u5185\u5bb9\u5bf9\u5e94uuid"
                    ),
                ),
                (
                    "file_status",
                    models.CharField(
                        max_length=100,
                        verbose_name="\u662f\u5426\u4e3a\u6b63\u786e\u914d\u7f6e",
                        choices=[
                            ("success", "\u6587\u4ef6\u68c0\u6d4b\u6210\u529f"),
                            ("failed", "\u6587\u4ef6\u68c0\u6d4b\u5931\u8d25"),
                        ],
                    ),
                ),
                (
                    "error_msg",
                    models.CharField(max_length=255, verbose_name="\u6587\u4ef6\u9519\u8bef\u4fe1\u606f", blank=True),
                ),
                ("file_id", models.IntegerField(verbose_name="\u6587\u4ef6ID")),
                ("config", bkmonitor.utils.db.fields.JsonField(null=True, verbose_name="\u914d\u7f6e\u8be6\u60c5")),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
