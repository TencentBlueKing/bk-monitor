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
        ("monitor", "0062_update_host_property"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScriptCollectorConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("data_id", models.IntegerField(null=True, verbose_name="\u521b\u5efa\u7684data id", blank=True)),
                ("name", models.CharField(max_length=30, verbose_name="\u6570\u636e\u8868\u540d")),
                (
                    "description",
                    models.CharField(max_length=15, verbose_name="\u6570\u636e\u8868\u4e2d\u6587\u542b\u4e49"),
                ),
                (
                    "charset",
                    models.CharField(
                        max_length=20, verbose_name="\u5b57\u7b26\u96c6", choices=[(b"UTF8", b"UTF8"), (b"GBK", b"GBK")]
                    ),
                ),
                ("fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5b57\u6bb5\u4fe1\u606f(json)")),
                (
                    "script_type",
                    models.CharField(
                        default=b"file",
                        max_length=20,
                        verbose_name="\u811a\u672c\u7c7b\u578b",
                        choices=[(b"file", "\u811a\u672c"), (b"cmd", "\u547d\u4ee4\u884c")],
                    ),
                ),
                (
                    "script_ext",
                    models.CharField(
                        default=b"shell",
                        max_length=20,
                        verbose_name="\u811a\u672c\u683c\u5f0f",
                        choices=[
                            (b"shell", b"shell"),
                            (b"bat", b"bat"),
                            (b"python", b"python"),
                            (b"perl", b"perl"),
                            (b"powershell", b"powershell"),
                            (b"vbs", b"vbs"),
                            (b"shell", b"shell"),
                            (b"custom", "\u81ea\u5b9a\u4e49"),
                        ],
                    ),
                ),
                (
                    "params_schema",
                    bkmonitor.utils.db.fields.JsonField(null=True, verbose_name="\u811a\u672c\u53c2\u6570\u6a21\u578b"),
                ),
                (
                    "script_run_cmd",
                    models.TextField(
                        null=True,
                        verbose_name="\u542f\u52a8\u547d\u4ee4\uff08\u811a\u672c\u6a21\u5f0f\uff09",
                        blank=True,
                    ),
                ),
                (
                    "script_content_base64",
                    models.TextField(null=True, verbose_name="\u811a\u672c\u5185\u5bb9", blank=True),
                ),
                (
                    "start_cmd",
                    models.TextField(
                        null=True,
                        verbose_name="\u542f\u52a8\u547d\u4ee4\uff08\u547d\u4ee4\u884c\u6a21\u5f0f\uff09",
                        blank=True,
                    ),
                ),
                (
                    "collect_interval",
                    models.PositiveIntegerField(default=1, verbose_name="\u91c7\u96c6\u5468\u671f(\u5206\u949f)"),
                ),
                (
                    "raw_data_interval",
                    models.PositiveIntegerField(
                        default=30, verbose_name="\u539f\u59cb\u6570\u636e\u4fdd\u5b58\u5468\u671f(\u5929)"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ScriptCollectorInstance",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "type",
                    models.CharField(
                        default=b"host",
                        max_length=20,
                        verbose_name="\u5b9e\u4f8b\u7c7b\u578b",
                        choices=[(b"host", "\u4e3b\u673a"), (b"topo", "\u62d3\u6251")],
                    ),
                ),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("ip", models.CharField(max_length=30, null=True, verbose_name="\u4e3b\u673aIP", blank=True)),
                ("bk_cloud_id", models.IntegerField(null=True, verbose_name="\u4e91\u533a\u57dfID", blank=True)),
                (
                    "bk_obj_id",
                    models.CharField(max_length=50, null=True, verbose_name="\u62d3\u6251\u5bf9\u8c61ID", blank=True),
                ),
                (
                    "bk_inst_id",
                    models.IntegerField(null=True, verbose_name="\u62d3\u6251\u5bf9\u8c61\u5b9e\u4f8bID", blank=True),
                ),
                ("params", bkmonitor.utils.db.fields.JsonField(verbose_name="\u811a\u672c\u6267\u884c\u53c2\u6570")),
                (
                    "config",
                    models.ForeignKey(
                        related_name="instances",
                        verbose_name="\u914d\u7f6e",
                        to="monitor.ScriptCollectorConfig",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
