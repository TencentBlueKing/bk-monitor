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
        ("monitor", "0005_operaterecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlarmStrategy",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("cc_biz_id", models.CharField(max_length=30, verbose_name="cc\u4e1a\u52a1id")),
                ("s_id", models.CharField(max_length=50, verbose_name="\u5173\u8054Moniter\u8868\u7684id")),
                (
                    "monitor_level",
                    models.CharField(
                        max_length=10,
                        verbose_name="\u544a\u8b66\u7ea7\u522b",
                        choices=[(b"3", "\u8f7b\u5fae"), (b"2", "\u666e\u901a"), (b"1", "\u4e25\u91cd")],
                    ),
                ),
                ("monitor_name", models.CharField(default=b"", max_length=32, verbose_name="\u76d1\u63a7\u540d\u79f0")),
                ("condition", models.TextField(null=True, verbose_name="\u7b5b\u9009\u6761\u4ef6", blank=True)),
                ("strategy_id", models.CharField(max_length=10, verbose_name="\u7b97\u6cd5id")),
                ("strategy_option", models.TextField(verbose_name="\u7b97\u6cd5\u53c2\u6570")),
                (
                    "monitor_config",
                    models.TextField(
                        help_text="\u8be5\u5b57\u6bb5\u5e9f\u5f03\uff0c\u4e0d\u518d\u4f7f\u7528",
                        verbose_name="\u901a\u77e5\u53c2\u6570",
                    ),
                ),
                ("rules", models.TextField(verbose_name="\u6536\u655b\u89c4\u5219")),
                ("display_name", models.CharField(default=b"", max_length=50, verbose_name="\u7b56\u7565\u540d\u79f0")),
                (
                    "responsible",
                    models.TextField(default=b"", null=True, verbose_name="\u989d\u5916\u901a\u77e5\u4eba", blank=True),
                ),
                (
                    "solution_id",
                    models.CharField(
                        default=b"", max_length=30, null=True, verbose_name="\u81ea\u6108\u5957\u9910id", blank=True
                    ),
                ),
                ("notify_way", models.TextField(verbose_name="\u901a\u77e5\u65b9\u5f0f")),
                ("role_list", models.TextField(verbose_name="\u901a\u77e5\u4eba\u89d2\u8272")),
                (
                    "prform_cate",
                    models.CharField(
                        default=b"",
                        max_length=30,
                        null=True,
                        verbose_name="\u57fa\u7840\u6027\u80fd\u914d\u7f6e",
                        blank=True,
                    ),
                ),
                ("ip", models.TextField(default=b"", null=True, verbose_name="IP", blank=True)),
                ("plat_id", models.TextField(default=b"", null=True, verbose_name="\u5e73\u53f0", blank=True)),
                ("cc_module", models.TextField(default=b"", null=True, verbose_name="\u6a21\u5757", blank=True)),
                ("cc_set", models.TextField(default=b"", null=True, verbose_name="SET", blank=True)),
                ("notify", models.TextField(default=b"{}", verbose_name="\u901a\u77e5\u914d\u7f6e")),
                ("creator", models.CharField(max_length=30, verbose_name="\u521b\u5efa\u8005")),
                ("updator", models.CharField(max_length=30, verbose_name="\u66f4\u65b0\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
                (
                    "nodata_alarm",
                    models.IntegerField(
                        default=0, verbose_name="\u65e0\u6570\u636e\u544a\u8b66(\u8fde\u7eed\u591a\u5c11\u5468\u671f)"
                    ),
                ),
                ("monitor_id", models.IntegerField(null=True)),
                ("condition_id", models.IntegerField(null=True)),
                ("condition_config_id", models.IntegerField(null=True)),
                ("alarm_def_id", models.IntegerField(null=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                (
                    "scenario",
                    models.CharField(default=b"custom", max_length=32, verbose_name="\u76d1\u63a7\u573a\u666f"),
                ),
            ],
            options={
                "verbose_name": "\u544a\u8b66\u7b56\u7565\u4e34\u65f6\u8868",
            },
        ),
    ]
