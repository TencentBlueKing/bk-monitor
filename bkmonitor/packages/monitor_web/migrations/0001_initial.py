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


import monitor_web.models.file
from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CollectorPluginConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "config_json",
                    bkmonitor.utils.db.fields.JsonField(default=None, verbose_name="\u53c2\u6570\u914d\u7f6e"),
                ),
                (
                    "collector_json",
                    bkmonitor.utils.db.fields.JsonField(default=None, verbose_name="\u91c7\u96c6\u5668\u914d\u7f6e"),
                ),
                (
                    "is_support_remote",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u652f\u6301\u8fdc\u7a0b\u91c7\u96c6"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CollectorPluginInfo",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "plugin_display_name",
                    models.CharField(default="", max_length=64, verbose_name="\u63d2\u4ef6\u522b\u540d"),
                ),
                (
                    "metric_json",
                    bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u6307\u6807\u914d\u7f6e"),
                ),
                (
                    "description_md",
                    models.TextField(default="", verbose_name="\u63d2\u4ef6\u63cf\u8ff0\uff0cmarkdown\u6587\u672c"),
                ),
                ("logo", models.ImageField(upload_to=b"", null=True, verbose_name="logo\u6587\u4ef6")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CollectorPluginMeta",
            fields=[
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "plugin_id",
                    models.CharField(max_length=64, serialize=False, verbose_name="\u63d2\u4ef6ID", primary_key=True),
                ),
                ("bk_biz_id", models.IntegerField(default=0, db_index=True, verbose_name="\u4e1a\u52a1ID", blank=True)),
                ("bk_supplier_id", models.IntegerField(default=0, verbose_name="\u5f00\u53d1\u5546ID", blank=True)),
                (
                    "plugin_type",
                    models.CharField(
                        db_index=True,
                        max_length=32,
                        verbose_name="\u63d2\u4ef6\u7c7b\u578b",
                        choices=[
                            (b"Exporter", b"Exporter"),
                            (b"Script", b"Script"),
                            (b"JMX", b"JMX"),
                            (b"DataDog", b"DataDog"),
                            (b"Pushgateway", "BK-Pull"),
                            (b"Built-In", "BK-Monitor"),
                        ],
                    ),
                ),
                ("tag", models.CharField(default="", max_length=64, verbose_name="\u63d2\u4ef6\u6807\u7b7e")),
                ("is_internal", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5185\u7f6e")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="OperatorSystem",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("os_type_id", models.CharField(max_length=10, verbose_name="\u64cd\u4f5c\u7cfb\u7edf\u7c7b\u578bID")),
                (
                    "os_type",
                    models.CharField(unique=True, max_length=16, verbose_name="\u64cd\u4f5c\u7cfb\u7edf\u7c7b\u578b"),
                ),
                ("is_enable", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
            ],
        ),
        migrations.CreateModel(
            name="PluginVersionHistory",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "stage",
                    models.CharField(
                        default="unregister",
                        max_length=30,
                        verbose_name="\u7248\u672c\u9636\u6bb5",
                        choices=[
                            ("unregister", "\u672a\u6ce8\u518c\u7248\u672c"),
                            ("debug", "\u8c03\u8bd5\u7248\u672c"),
                            ("release", "\u53d1\u5e03\u7248\u672c"),
                        ],
                    ),
                ),
                ("config_version", models.IntegerField(default=1, verbose_name="\u63d2\u4ef6\u7248\u672c")),
                ("info_version", models.IntegerField(default=1, verbose_name="\u63d2\u4ef6\u4fe1\u606f\u7248\u672c")),
                ("signature", bkmonitor.utils.db.fields.YamlField(default="", verbose_name="\u7248\u672c\u7b7e\u540d")),
                (
                    "version_log",
                    models.CharField(default="", max_length=100, verbose_name="\u7248\u672c\u4fee\u6539\u65e5\u5fd7"),
                ),
                (
                    "config",
                    models.ForeignKey(
                        related_name="version",
                        verbose_name="\u63d2\u4ef6\u529f\u80fd\u914d\u7f6e",
                        to="monitor_web.CollectorPluginConfig",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "info",
                    models.ForeignKey(
                        related_name="version",
                        verbose_name="\u63d2\u4ef6\u4fe1\u606f\u914d\u7f6e",
                        to="monitor_web.CollectorPluginInfo",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "plugin",
                    models.ForeignKey(
                        related_name="versions",
                        verbose_name="\u63d2\u4ef6\u5143\u4fe1\u606f",
                        to="monitor_web.CollectorPluginMeta",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "ordering": ["config_version", "info_version", "create_time", "update_time"],
            },
        ),
        migrations.CreateModel(
            name="UploadedFileInfo",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("original_filename", models.CharField(max_length=255, verbose_name="\u539f\u59cb\u6587\u4ef6\u540d")),
                ("actual_filename", models.CharField(max_length=255, verbose_name="\u6587\u4ef6\u540d")),
                ("relative_path", models.TextField(verbose_name="\u6587\u4ef6\u76f8\u5bf9\u8def\u5f84")),
                (
                    "file_data",
                    models.FileField(
                        upload_to=monitor_web.models.file.generate_upload_path, verbose_name="\u6587\u4ef6\u5185\u5bb9"
                    ),
                ),
                ("file_md5", models.CharField(max_length=50, verbose_name="\u6587\u4ef6\u5185\u5bb9MD5")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterUniqueTogether(
            name="pluginversionhistory",
            unique_together={("plugin", "config_version", "info_version")},
        ),
    ]
