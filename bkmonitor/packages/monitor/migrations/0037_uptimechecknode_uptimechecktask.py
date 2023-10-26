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
        ("monitor", "0036_auto_20180425_2121"),
    ]

    operations = [
        migrations.CreateModel(
            name="UptimeCheckNode",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="\u4e1a\u52a1ID")),
                (
                    "is_common",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u4e3a\u901a\u7528\u8282\u70b9"),
                ),
                ("name", models.CharField(max_length=50, verbose_name="\u8282\u70b9\u540d\u79f0")),
                ("ip", models.GenericIPAddressField(verbose_name="IP\u5730\u5740")),
                ("plat_id", models.IntegerField(verbose_name="\u4e91\u533a\u57dfID")),
            ],
            options={
                "verbose_name": "\u62e8\u6d4b\u8282\u70b9",
                "verbose_name_plural": "\u62e8\u6d4b\u8282\u70b9",
            },
        ),
        migrations.CreateModel(
            name="UptimeCheckTask",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("name", models.CharField(max_length=50, verbose_name="\u4efb\u52a1\u540d\u79f0")),
                (
                    "protocol",
                    models.CharField(
                        max_length=10,
                        verbose_name="\u534f\u8bae",
                        choices=[(b"TCP", "TCP"), (b"UDP", "UDP"), (b"HTTP", "HTTP(S)")],
                    ),
                ),
                (
                    "check_interval",
                    models.PositiveIntegerField(default=5, verbose_name="\u62e8\u6d4b\u5468\u671f(\u5206\u949f)"),
                ),
                ("location", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5730\u533a")),
                (
                    "config",
                    bkmonitor.utils.db.fields.SymmetricJsonField(
                        null=True, verbose_name="\u62e8\u6d4b\u914d\u7f6e", blank=True
                    ),
                ),
                (
                    "nodes",
                    models.ManyToManyField(
                        related_name="tasks", verbose_name="\u62e8\u6d4b\u8282\u70b9", to="monitor.UptimeCheckNode"
                    ),
                ),
            ],
            options={
                "verbose_name": "\u62e8\u6d4b\u4efb\u52a1",
                "verbose_name_plural": "\u62e8\u6d4b\u4efb\u52a1",
            },
        ),
    ]
