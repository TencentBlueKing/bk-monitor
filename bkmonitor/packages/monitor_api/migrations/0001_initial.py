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

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AlarmCollectDef",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("title", models.CharField(max_length=256, verbose_name="\u540d\u79f0")),
                ("description", models.TextField(default="", null=True, verbose_name="\u5907\u6ce8", blank=True)),
                ("config", models.TextField(default="", null=True, verbose_name="\u914d\u7f6e", blank=True)),
            ],
            options={
                "db_table": "ja_alarm_converge_def",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="AlarmSource",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("title", models.CharField(max_length=256, verbose_name="\u544a\u8b66\u540d\u79f0")),
                ("description", models.TextField(default="", verbose_name="\u5907\u6ce8", blank=True)),
                (
                    "src_type",
                    models.CharField(
                        default="JA", max_length=64, verbose_name="\u544a\u8b66\u6e90\u5206\u7c7b", blank=True
                    ),
                ),
                (
                    "alarm_type",
                    models.CharField(
                        default="Custom", max_length=64, verbose_name="\u544a\u8b66\u5206\u7c7b", blank=True
                    ),
                ),
                (
                    "scenario",
                    models.CharField(
                        default="custom", max_length=64, verbose_name="\u76d1\u63a7\u573a\u666f", blank=True
                    ),
                ),
                (
                    "monitor_target",
                    models.CharField(default="", max_length=64, verbose_name="\u76d1\u63a7\u5bf9\u8c61", blank=True),
                ),
                (
                    "source_info",
                    models.TextField(default="", verbose_name="\u544a\u8b66\u6765\u6e90\u4fe1\u606f", blank=True),
                ),
                ("condition", models.TextField(default="", verbose_name="\u544a\u8b66\u8303\u56f4", blank=True)),
                ("timeout", models.IntegerField(default=40, verbose_name="\u8d85\u65f6\u65f6\u95f4", blank=True)),
                (
                    "alarm_attr_id",
                    models.CharField(
                        default="",
                        max_length=128,
                        verbose_name="\u76d1\u63a7\u7cfb\u7edf\u5185\u7684\u76d1\u63a7ID",
                        blank=True,
                    ),
                ),
                ("monitor_level", models.IntegerField(default=3, verbose_name="\u76d1\u63a7\u7b49\u7ea7", blank=True)),
                (
                    "alarm_cleaning_id",
                    models.IntegerField(default=0, verbose_name="\u6e05\u6d17\u7b56\u7565ID", blank=True),
                ),
                (
                    "alarm_collect_id",
                    models.IntegerField(default=0, verbose_name="\u6c47\u603b\u7b56\u7565ID", blank=True),
                ),
                (
                    "alarm_solution_id",
                    models.IntegerField(default=0, verbose_name="\u5904\u7406\u7b56\u7565ID", blank=True),
                ),
                (
                    "alarm_notice_id",
                    models.IntegerField(default=0, verbose_name="\u901a\u77e5\u7b56\u7565ID", blank=True),
                ),
            ],
            options={
                "db_table": "ja_alarm_source",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ConvergeConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("config", models.TextField(default="", null=True, verbose_name="\u914d\u7f6e", blank=True)),
                ("alarm_source_id", models.IntegerField(default=0, verbose_name="\u544a\u8b66\u6e90id", blank=True)),
                ("converge_id", models.IntegerField(default=0, verbose_name="\u6536\u655bid", blank=True)),
            ],
            options={
                "db_table": "ja_alarm_converge_config",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="DetectAlgorithmConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("config", models.TextField(default="", verbose_name="\u7b97\u6cd5\u914d\u7f6e", blank=True)),
                ("algorithm_id", models.IntegerField(default=0, verbose_name="\u7b97\u6cd5ID", blank=True)),
                ("monitor_item_id", models.IntegerField(default=0, verbose_name="\u76d1\u63a7\u9879ID", blank=True)),
            ],
            options={
                "db_table": "ja_detect_algorithm_config",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="MonitorItem",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("title", models.CharField(max_length=256, verbose_name="\u76d1\u63a7\u9879\u540d\u79f0")),
                ("description", models.TextField(default="", verbose_name="\u5907\u6ce8", blank=True)),
                ("condition", models.TextField(default="", verbose_name="\u76d1\u63a7\u8303\u56f4", blank=True)),
                ("monitor_level", models.IntegerField(default=3, verbose_name="\u76d1\u63a7\u7b49\u7ea7", blank=True)),
                (
                    "is_none",
                    models.IntegerField(
                        default=0, verbose_name="\u65e0\u6570\u636e\u544a\u8b66\u5f00\u5173", blank=True
                    ),
                ),
                (
                    "is_none_option",
                    models.TextField(default="", verbose_name="\u65e0\u6570\u636e\u914d\u7f6e", blank=True),
                ),
                (
                    "is_recovery",
                    models.BooleanField(default=False, verbose_name="\u6062\u590d\u544a\u8b66\u5f00\u5173"),
                ),
                (
                    "is_classify_notice",
                    models.BooleanField(default=False, verbose_name="\u5206\u7ea7\u544a\u8b66\u5f00\u5173"),
                ),
                ("monitor_id", models.IntegerField(default=0, verbose_name="\u76d1\u63a7\u6e90ID", blank=True)),
                ("alarm_def_id", models.IntegerField(default=0, verbose_name="\u544a\u8b66\u6e90ID", blank=True)),
            ],
            options={
                "db_table": "ja_monitor_item",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="MonitorItemGroup",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("monitor_id", models.IntegerField(default=0, verbose_name="\u76d1\u63a7\u6e90ID", blank=True)),
                ("monitor_level", models.IntegerField(default=3, verbose_name="\u76d1\u63a7\u7b49\u7ea7", blank=True)),
                ("monitor_item_id", models.IntegerField(verbose_name="\u544a\u8b66\u7b56\u7565ID")),
                ("monitor_group_id", models.IntegerField(verbose_name="\u544a\u8b66\u7b56\u7565\u7ec4ID")),
            ],
            options={
                "db_table": "ja_monitor_item_group",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="MonitorSource",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("title", models.CharField(max_length=256, verbose_name="\u76d1\u63a7\u6e90\u540d\u79f0")),
                ("description", models.TextField(default="", null=True, verbose_name="\u5907\u6ce8", blank=True)),
                (
                    "src_type",
                    models.CharField(
                        default="JA", max_length=64, verbose_name="\u76d1\u63a7\u6e90\u5206\u7c7b", blank=True
                    ),
                ),
                (
                    "scenario",
                    models.CharField(
                        default="custom", max_length=64, verbose_name="\u76d1\u63a7\u573a\u666f", blank=True
                    ),
                ),
                (
                    "monitor_type",
                    models.CharField(
                        default="online", max_length=64, verbose_name="\u76d1\u63a7\u5206\u7c7b", blank=True
                    ),
                ),
                (
                    "monitor_target",
                    models.CharField(
                        default="custom", max_length=50, verbose_name="\u76d1\u63a7\u6307\u6807", blank=True
                    ),
                ),
                (
                    "stat_source_type",
                    models.CharField(
                        default="BKDATA", max_length=64, verbose_name="\u7edf\u8ba1\u6e90\u5206\u7c7b", blank=True
                    ),
                ),
                (
                    "stat_source_info",
                    models.TextField(
                        default="", verbose_name="\u7edf\u8ba1\u6e90\u4fe1\u606f\uff08JSON\uff09", blank=True
                    ),
                ),
            ],
            options={
                "db_table": "ja_monitor",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="NoticeConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("title", models.CharField(max_length=256, verbose_name="\u540d\u79f0")),
                (
                    "description",
                    models.CharField(default="", max_length=256, null=True, verbose_name="\u5907\u6ce8", blank=True),
                ),
                ("notify_config", models.TextField(default="{}", verbose_name="\u914d\u7f6e", blank=True)),
                ("alarm_start_time", models.TimeField(max_length=32, verbose_name="\u5f00\u59cb\u65f6\u95f4")),
                ("alarm_end_time", models.TimeField(max_length=32, verbose_name="\u7ed3\u675f\u65f6\u95f4")),
                ("alarm_source_id", models.IntegerField(default=0, verbose_name="\u544a\u8b66\u6e90id", blank=True)),
            ],
            options={
                "db_table": "ja_alarm_notice_config",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="NoticeGroup",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("title", models.CharField(max_length=256, verbose_name="\u540d\u79f0")),
                ("description", models.CharField(default="", max_length=256, verbose_name="\u5907\u6ce8", blank=True)),
                ("biz_id", models.IntegerField(default=0, verbose_name="\u4e1a\u52a1", blank=True)),
                (
                    "group_type",
                    models.IntegerField(default=0, verbose_name="\u901a\u77e5\u7ec4\u7c7b\u578b", blank=True),
                ),
                (
                    "group_receiver",
                    models.TextField(default="", verbose_name="\u901a\u77e5\u7ec4\u6536\u4ef6\u4eba", blank=True),
                ),
            ],
            options={
                "db_table": "ja_alarm_notice_group",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="SolutionConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("title", models.CharField(default="", max_length=256, verbose_name="\u540d\u79f0", blank=True)),
                ("description", models.TextField(default="", null=True, verbose_name="\u5907\u6ce8", blank=True)),
                ("config", models.TextField(default="", null=True, verbose_name="\u914d\u7f6e", blank=True)),
                ("alarm_source_id", models.IntegerField(default=0, verbose_name="\u544a\u8b66\u6e90id", blank=True)),
                ("solution_id", models.IntegerField(default=0, verbose_name="\u5904\u7406id", blank=True)),
                ("solution_type", models.CharField(max_length=128, verbose_name="\u5904\u7406\u7c7b\u578b")),
                ("biz_id", models.IntegerField(default=0, verbose_name="\u4e1a\u52a1ID", blank=True)),
                ("creator", models.CharField(max_length=255, verbose_name="\u4f5c\u4e1a\u521b\u5efa\u8005")),
            ],
            options={
                "db_table": "ja_alarm_solution_config",
                "managed": False,
            },
        ),
    ]
