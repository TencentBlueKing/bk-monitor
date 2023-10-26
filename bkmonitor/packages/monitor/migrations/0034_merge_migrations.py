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
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.db import migrations, models

import bkmonitor.utils.db.fields


def set_menu_id(apps, schema_editor):
    """
    将Integerfield的id改为外键引用
    """
    # We can't import the model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    DashboardMenuLocation = apps.get_model("monitor", "DashboardMenuLocation")
    for location in DashboardMenuLocation.objects.all():
        location.menu_id = location._menu_id
        location.view_id = location._view_id
        location.save()


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0033_alter_snapshothostindex_conversion_unit"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComponentImportTask",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                (
                    "process_data",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u4efb\u52a1\u6d41\u7a0b\u4e2d\u95f4\u6570\u636e(json)", blank=True
                    ),
                ),
                (
                    "result_data",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u4efb\u52a1\u6267\u884c\u7ed3\u679c(JSON)", blank=True
                    ),
                ),
                (
                    "ex_data",
                    models.TextField(null=True, verbose_name="\u4efb\u52a1\u5f02\u5e38\u4fe1\u606f", blank=True),
                ),
                (
                    "status",
                    models.CharField(
                        default=b"CREATED",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u72b6\u6001",
                        choices=[
                            (b"CREATED", "\u4efb\u52a1\u521b\u5efa\u6210\u529f"),
                            (b"RUNNING", "\u4efb\u52a1\u6b63\u5728\u6267\u884c"),
                            (b"SUCCESS", "\u4efb\u52a1\u6267\u884c\u6210\u529f"),
                            (b"EXCEPTION", "\u4efb\u52a1\u6267\u884c\u8fc7\u7a0b\u5f02\u5e38"),
                        ],
                    ),
                ),
                (
                    "process",
                    models.CharField(
                        default=b"READY",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u5f53\u524d\u6d41\u7a0b",
                        choices=[
                            (b"READY", "\u4efb\u52a1\u5c31\u7eea"),
                            (b"UNZIP_FILE", "\u89e3\u538b\u6587\u4ef6"),
                            (b"CHECK_COMPONENT_NAME", "\u6821\u9a8c\u7ec4\u4ef6\u540d\u79f0"),
                            (b"CHECK_COMPONENT_DESC", "\u6821\u9a8c\u7ec4\u4ef6\u63cf\u8ff0"),
                            (b"CHECK_INDEX_FILE", "\u6821\u9a8c\u6307\u6807\u9879\u6587\u4ef6"),
                            (b"CHECK_CONFIG_FILE", "\u6821\u9a8c\u914d\u7f6e\u9879\u6587\u4ef6"),
                            (b"PROCESS_LOGO", "\u8bfb\u53d6\u5e76\u538b\u7f29LOGO"),
                            (b"CHECK_EXPORTER_FILE", "\u6821\u9a8c\u4e8c\u8fdb\u5236exporter"),
                            (b"SAVE_COMPONENT", "\u4fdd\u5b58\u7ec4\u4ef6\u914d\u7f6e"),
                            (b"FINISHED", "\u4efb\u52a1\u6d41\u7a0b\u5b8c\u6210"),
                        ],
                    ),
                ),
            ],
            options={
                "verbose_name": "\u7ec4\u4ef6\u5bfc\u5165\u4efb\u52a1",
                "verbose_name_plural": "\u7ec4\u4ef6\u5bfc\u5165\u4efb\u52a1",
            },
        ),
        migrations.CreateModel(
            name="ExporterComponent",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("data_id", models.IntegerField(null=True, verbose_name="\u521b\u5efa\u7684data id", blank=True)),
                (
                    "rt_id_list",
                    bkmonitor.utils.db.fields.JsonField(
                        default=[], verbose_name="\u865a\u62df\u7ed3\u679c\u8868\u540d(\u5217\u8868)"
                    ),
                ),
                (
                    "parent_rt_id",
                    models.CharField(
                        max_length=100, null=True, verbose_name="\u5b9e\u4f53\u7ed3\u679c\u8868\u540d", blank=True
                    ),
                ),
                ("component_name", models.CharField(max_length=15, verbose_name="\u7ec4\u4ef6\u540d\u79f0")),
                (
                    "component_name_display",
                    models.CharField(max_length=15, verbose_name="\u7ec4\u4ef6\u4e2d\u6587\u542b\u4e49"),
                ),
                (
                    "component_desc",
                    models.TextField(default=b"", verbose_name="\u7ec4\u4ef6\u8be6\u7ec6\u63cf\u8ff0(md)", blank=True),
                ),
                ("indices", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u6307\u6807\u9879(json)")),
                ("exporter_id", models.IntegerField(default=0, verbose_name="Exporter ID")),
                (
                    "exporter_file_info",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u4e0a\u4f20\u7684Exporter\u6587\u4ef6\u4fe1\u606f", blank=True
                    ),
                ),
                ("logo", models.TextField(default=b"", verbose_name="logo\u7684base64\u7f16\u7801", blank=True)),
                (
                    "logo_small",
                    models.TextField(default=b"", verbose_name="\u5c0flogo\u7684base64\u7f16\u7801", blank=True),
                ),
                (
                    "charset",
                    models.CharField(
                        default=b"UTF8",
                        max_length=20,
                        verbose_name="\u5b57\u7b26\u96c6",
                        choices=[(b"UTF8", b"UTF8"), (b"GBK", b"GBK")],
                    ),
                ),
                (
                    "config_schema",
                    bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u914d\u7f6e\u6a21\u578b(json)"),
                ),
                ("ip_list", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="IP\u5217\u8868(json)")),
                (
                    "scope",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u5927\u533a\u4fe1\u606f(json)", blank=True
                    ),
                ),
                (
                    "cleaned_config_data",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u53c2\u6570\u586b\u5199\u914d\u7f6e", blank=True
                    ),
                ),
                ("config", bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="\u53c2\u6570\u914d\u7f6e")),
                (
                    "config_files_info",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True,
                        verbose_name="\u4e0a\u4f20\u7684\u914d\u7f6e\u6587\u4ef6\u8be6\u60c5\u5217\u8868",
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
                (
                    "trend_data_interval",
                    models.PositiveIntegerField(
                        default=90, verbose_name="\u8d8b\u52bf\u6570\u636e\u4fdd\u5b58\u5468\u671f(\u5929)"
                    ),
                ),
                (
                    "is_internal",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u4e3a\u5185\u7f6e\u7ec4\u4ef6"),
                ),
                (
                    "version",
                    models.CharField(
                        default=b"",
                        max_length=30,
                        verbose_name="\u7ec4\u4ef6\u7248\u672c\u53f7\uff08\u4ec5\u9650\u5185\u7f6e\u7ec4\u4ef6\uff09",
                        blank=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default=b"DRAFT",
                        max_length=20,
                        verbose_name="\u5f53\u524d\u72b6\u6001",
                        choices=[(b"DRAFT", "\u672a\u4fdd\u5b58"), (b"SAVED", "\u5df2\u4fdd\u5b58")],
                    ),
                ),
            ],
            options={
                "verbose_name": "\u81ea\u5b9a\u4e49\u7ec4\u4ef6",
                "verbose_name_plural": "\u81ea\u5b9a\u4e49\u7ec4\u4ef6",
            },
        ),
        migrations.CreateModel(
            name="ExporterDepositTask",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("data_id", models.IntegerField(null=True, verbose_name="\u521b\u5efa\u7684data id", blank=True)),
                (
                    "rt_id_list",
                    bkmonitor.utils.db.fields.JsonField(
                        default=[], verbose_name="\u865a\u62df\u7ed3\u679c\u8868\u540d(\u5217\u8868)"
                    ),
                ),
                (
                    "parent_rt_id",
                    models.CharField(
                        max_length=100, null=True, verbose_name="\u5b9e\u4f53\u7ed3\u679c\u8868\u540d", blank=True
                    ),
                ),
                ("component_name", models.CharField(max_length=15, verbose_name="\u7ec4\u4ef6\u540d\u79f0")),
                (
                    "component_name_display",
                    models.CharField(max_length=15, verbose_name="\u7ec4\u4ef6\u4e2d\u6587\u542b\u4e49"),
                ),
                (
                    "component_desc",
                    models.TextField(default=b"", verbose_name="\u7ec4\u4ef6\u8be6\u7ec6\u63cf\u8ff0(md)", blank=True),
                ),
                ("indices", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u6307\u6807\u9879(json)")),
                ("exporter_id", models.IntegerField(default=0, verbose_name="Exporter ID")),
                (
                    "exporter_file_info",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u4e0a\u4f20\u7684Exporter\u6587\u4ef6\u4fe1\u606f", blank=True
                    ),
                ),
                ("logo", models.TextField(default=b"", verbose_name="logo\u7684base64\u7f16\u7801", blank=True)),
                (
                    "logo_small",
                    models.TextField(default=b"", verbose_name="\u5c0flogo\u7684base64\u7f16\u7801", blank=True),
                ),
                (
                    "charset",
                    models.CharField(
                        default=b"UTF8",
                        max_length=20,
                        verbose_name="\u5b57\u7b26\u96c6",
                        choices=[(b"UTF8", b"UTF8"), (b"GBK", b"GBK")],
                    ),
                ),
                (
                    "config_schema",
                    bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u914d\u7f6e\u6a21\u578b(json)"),
                ),
                ("ip_list", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="IP\u5217\u8868(json)")),
                (
                    "scope",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u5927\u533a\u4fe1\u606f(json)", blank=True
                    ),
                ),
                (
                    "cleaned_config_data",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u53c2\u6570\u586b\u5199\u914d\u7f6e", blank=True
                    ),
                ),
                ("config", bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="\u53c2\u6570\u914d\u7f6e")),
                (
                    "config_files_info",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True,
                        verbose_name="\u4e0a\u4f20\u7684\u914d\u7f6e\u6587\u4ef6\u8be6\u60c5\u5217\u8868",
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
                (
                    "trend_data_interval",
                    models.PositiveIntegerField(
                        default=90, verbose_name="\u8d8b\u52bf\u6570\u636e\u4fdd\u5b58\u5468\u671f(\u5929)"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default=b"CREATED",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u72b6\u6001",
                        choices=[
                            (b"CREATED", "\u4efb\u52a1\u521b\u5efa\u6210\u529f"),
                            (b"RUNNING", "\u4efb\u52a1\u6b63\u5728\u6267\u884c"),
                            (b"SUCCESS", "\u4efb\u52a1\u6267\u884c\u6210\u529f"),
                            (b"FAILED", "\u4efb\u52a1\u6267\u884c\u5931\u8d25"),
                            (b"EXCEPTION", "\u4efb\u52a1\u6267\u884c\u8fc7\u7a0b\u5f02\u5e38"),
                        ],
                    ),
                ),
                (
                    "process",
                    models.CharField(
                        default=b"READY",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u5f53\u524d\u6d41\u7a0b",
                        choices=[
                            (b"READY", "\u4efb\u52a1\u5c31\u7eea"),
                            (b"CREATE_RT", "\u68c0\u67e5\u5e76\u521b\u5efa\u7ed3\u679c\u8868"),
                            (b"CREATE_DATASET", "\u68c0\u67e5\u5e76\u521b\u5efaDataSet"),
                            (b"SET_ETL_TEMPLATE", "\u68c0\u67e5\u5e76\u751f\u6210\u6e05\u6d17\u914d\u7f6e"),
                            (b"DEPLOY_TSDB", "\u68c0\u67e5\u5e76\u521b\u5efaTSDB"),
                            (b"START_DISPATCH", "\u542f\u52a8\u5165\u5e93\u7a0b\u5e8f"),
                            (b"START_DEPOSIT_TASK", "\u521b\u5efa\u811a\u672c\u6258\u7ba1\u4efb\u52a1"),
                            (
                                b"WAIT_DEPOSIT_TASK",
                                "\u7b49\u5f85\u811a\u672c\u6258\u7ba1\u4efb\u52a1\u6267\u884c\u7ed3\u679c",
                            ),
                            (
                                b"STOP_OLD_DEPOSIT_TASK",
                                "\u53d6\u6d88\u8001\u7248\u672c\u914d\u7f6e\u7684IP\u6258\u7ba1",
                            ),
                            (b"FINISHED", "\u4efb\u52a1\u6d41\u7a0b\u5b8c\u6210"),
                        ],
                    ),
                ),
                (
                    "result_data",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u4efb\u52a1\u6267\u884c\u7ed3\u679c(JSON)"),
                ),
                ("ex_data", models.TextField(verbose_name="\u4efb\u52a1\u5f02\u5e38\u4fe1\u606f")),
                (
                    "component",
                    models.ForeignKey(
                        related_name="tasks",
                        verbose_name="\u6240\u5c5e\u7ec4\u4ef6",
                        to="monitor.ExporterComponent",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "get_latest_by": "update_time",
                "verbose_name": "Exporter\u6258\u7ba1\u4efb\u52a1",
            },
        ),
        migrations.CreateModel(
            name="LogCollector",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1id")),
                ("data_id", models.CharField(default=b"", max_length=100, verbose_name="\u6570\u636e\u6e90ID")),
                ("result_table_id", models.CharField(default=b"", max_length=100, verbose_name="\u7ed3\u679c\u8868ID")),
                ("data_set", models.CharField(max_length=100, verbose_name="\u6570\u636e\u6e90\u8868\u540d")),
                ("data_desc", models.CharField(max_length=100, verbose_name="\u6570\u636e\u6e90\u4e2d\u6587\u540d")),
                ("data_encode", models.CharField(max_length=30, verbose_name="\u5b57\u7b26\u7f16\u7801")),
                ("sep", models.CharField(max_length=30, verbose_name="\u6570\u636e\u5206\u9694\u7b26")),
                ("log_path", models.TextField(verbose_name="\u65e5\u5fd7\u8def\u5f84")),
                ("fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5b57\u6bb5\u914d\u7f6e")),
                ("ips", bkmonitor.utils.db.fields.JsonField(verbose_name="\u91c7\u96c6\u5bf9\u8c61ip\u5217\u8868")),
                ("conditions", bkmonitor.utils.db.fields.JsonField(verbose_name="\u91c7\u96c6\u6761\u4ef6")),
                (
                    "file_frequency",
                    models.CharField(max_length=30, verbose_name="\u65e5\u5fd7\u751f\u6210\u9891\u7387"),
                ),
            ],
            options={
                "verbose_name": "\u65e5\u5fd7\u63a5\u5165\u914d\u7f6e",
                "verbose_name_plural": "\u65e5\u5fd7\u63a5\u5165\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="LogCollectorHost",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("ip", models.CharField(max_length=20, verbose_name="\u91c7\u96c6\u5bf9\u8c61IP")),
                ("plat_id", models.IntegerField(verbose_name="\u5e73\u53f0ID")),
                (
                    "status",
                    models.CharField(
                        default=b"create",
                        max_length=20,
                        verbose_name="\u6570\u636e\u4e0a\u62a5\u72b6\u6001",
                        choices=[
                            (b"create", "\u542f\u7528\u4e2d"),
                            (b"normal", "\u6b63\u5e38"),
                            (b"stop", "\u505c\u7528\u4e2d"),
                            (b"stopped", "\u505c\u7528"),
                            (b"exception", "\u5f02\u5e38"),
                        ],
                    ),
                ),
                (
                    "log_collector",
                    models.ForeignKey(
                        related_name="hosts",
                        verbose_name="\u6240\u5c5e\u91c7\u96c6\u5668",
                        to="monitor.LogCollector",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "verbose_name": "\u65e5\u5fd7\u63a5\u5165\u4e3b\u673a\u72b6\u6001",
                "verbose_name_plural": "\u65e5\u5fd7\u63a5\u5165\u4e3b\u673a\u72b6\u6001",
            },
        ),
        migrations.CreateModel(
            name="ServiceAuthorization",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
                ("expire_time", models.DateTimeField(default=None, null=True, verbose_name="\u8fc7\u671f\u65f6\u95f4")),
                ("name", models.CharField(max_length=128, null=True, verbose_name="\u540d\u79f0", blank=True)),
                ("enable", models.BooleanField(default=True, verbose_name="\u542f\u7528")),
                ("cc_biz_id", models.CharField(max_length=30, verbose_name="cc\u4e1a\u52a1id")),
                (
                    "service_type",
                    models.CharField(
                        max_length=30, verbose_name="\u670d\u52a1\u7c7b\u578b", choices=[(b"charts", "\u56fe\u8868")]
                    ),
                ),
                ("service_id", models.CharField(max_length=30, verbose_name="\u670d\u52a1id")),
                ("domain", models.TextField(null=True, verbose_name="\u547d\u540d\u7a7a\u95f4", blank=True)),
                ("access_token", models.CharField(default=None, max_length=128, verbose_name="\u6388\u6743\u7801")),
                ("extra", models.TextField(null=True, verbose_name="\u6269\u5c55\u9009\u9879", blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="ShellCollectorConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("data_id", models.IntegerField(null=True, verbose_name="\u521b\u5efa\u7684data id", blank=True)),
                (
                    "rt_id",
                    models.CharField(max_length=100, null=True, verbose_name="\u7ed3\u679c\u8868\u540d", blank=True),
                ),
                ("table_name", models.CharField(max_length=30, verbose_name="\u6570\u636e\u8868\u540d")),
                (
                    "table_desc",
                    models.CharField(max_length=15, verbose_name="\u6570\u636e\u8868\u4e2d\u6587\u542b\u4e49"),
                ),
                (
                    "charset",
                    models.CharField(
                        max_length=20, verbose_name="\u5b57\u7b26\u96c6", choices=[(b"UTF8", b"UTF8"), (b"GBK", b"GBK")]
                    ),
                ),
                ("fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5b57\u6bb5\u4fe1\u606f(json)")),
                ("shell_content", models.TextField(null=True, verbose_name="\u811a\u672c\u5185\u5bb9")),
                (
                    "ip_list",
                    bkmonitor.utils.db.fields.JsonField(null=True, verbose_name="IP\u5217\u8868(json)", blank=True),
                ),
                (
                    "scope",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u5927\u533a\u4fe1\u606f(json)", blank=True
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
                (
                    "trend_data_interval",
                    models.PositiveIntegerField(
                        default=90, verbose_name="\u8d8b\u52bf\u6570\u636e\u4fdd\u5b58\u5468\u671f(\u5929)"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default=b"new draft",
                        max_length=20,
                        verbose_name="\u5f53\u524d\u72b6\u6001",
                        choices=[
                            (b"new draft", "\u65b0\u5efa\u672a\u4fdd\u5b58"),
                            (b"edit draft", "\u7f16\u8f91\u672a\u4fdd\u5b58"),
                            (b"saved", "\u5df2\u4fdd\u5b58"),
                        ],
                    ),
                ),
                (
                    "step",
                    models.IntegerField(
                        default=2,
                        verbose_name="\u5f53\u524d\u6b65\u9aa4(1-6)",
                        choices=[
                            (1, "\u5b9a\u4e49\u8868\u7ed3\u6784"),
                            (2, "\u7f16\u5199\u91c7\u96c6\u811a\u672c"),
                            (3, "\u9009\u62e9\u670d\u52a1\u5668"),
                            (4, "\u4e0b\u53d1\u91c7\u96c6\u6d4b\u8bd5"),
                            (5, "\u8bbe\u7f6e\u91c7\u96c6\u5468\u671f"),
                            (6, "\u5b8c\u6210"),
                        ],
                    ),
                ),
            ],
            options={
                "ordering": ("-create_time",),
                "verbose_name": "\u811a\u672c\u91c7\u96c6\u914d\u7f6e",
                "verbose_name_plural": "\u811a\u672c\u91c7\u96c6\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="ShellCollectorDepositTask",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("data_id", models.IntegerField(null=True, verbose_name="\u521b\u5efa\u7684data id", blank=True)),
                (
                    "rt_id",
                    models.CharField(max_length=100, null=True, verbose_name="\u7ed3\u679c\u8868\u540d", blank=True),
                ),
                ("table_name", models.CharField(max_length=30, verbose_name="\u6570\u636e\u8868\u540d")),
                (
                    "table_desc",
                    models.CharField(max_length=15, verbose_name="\u6570\u636e\u8868\u4e2d\u6587\u542b\u4e49"),
                ),
                (
                    "charset",
                    models.CharField(
                        max_length=20, verbose_name="\u5b57\u7b26\u96c6", choices=[(b"UTF8", b"UTF8"), (b"GBK", b"GBK")]
                    ),
                ),
                ("fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5b57\u6bb5\u4fe1\u606f(json)")),
                ("shell_content", models.TextField(null=True, verbose_name="\u811a\u672c\u5185\u5bb9")),
                (
                    "ip_list",
                    bkmonitor.utils.db.fields.JsonField(null=True, verbose_name="IP\u5217\u8868(json)", blank=True),
                ),
                (
                    "scope",
                    bkmonitor.utils.db.fields.JsonField(
                        null=True, verbose_name="\u5927\u533a\u4fe1\u606f(json)", blank=True
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
                (
                    "trend_data_interval",
                    models.PositiveIntegerField(
                        default=90, verbose_name="\u8d8b\u52bf\u6570\u636e\u4fdd\u5b58\u5468\u671f(\u5929)"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default=b"created",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u72b6\u6001",
                        choices=[
                            (b"created", "\u4efb\u52a1\u521b\u5efa\u6210\u529f"),
                            (b"running", "\u4efb\u52a1\u6b63\u5728\u6267\u884c"),
                            (b"success", "\u4efb\u52a1\u6267\u884c\u6210\u529f"),
                            (b"failed", "\u4efb\u52a1\u6267\u884c\u5931\u8d25"),
                            (b"exception", "\u4efb\u52a1\u6267\u884c\u8fc7\u7a0b\u5f02\u5e38"),
                        ],
                    ),
                ),
                (
                    "process",
                    models.CharField(
                        default=b"ready",
                        max_length=50,
                        verbose_name="\u4efb\u52a1\u5f53\u524d\u6d41\u7a0b",
                        choices=[
                            (b"ready", "\u4efb\u52a1\u5c31\u7eea"),
                            (b"create rt", "\u68c0\u67e5\u5e76\u521b\u5efa\u7ed3\u679c\u8868"),
                            (b"create dataset", "\u68c0\u67e5\u5e76\u521b\u5efaDataSet"),
                            (b"set etl template", "\u68c0\u67e5\u5e76\u751f\u6210\u6e05\u6d17\u914d\u7f6e"),
                            (b"deploy_tsdb", "\u68c0\u67e5\u5e76\u521b\u5efaTSDB"),
                            (b"start dispatch", "\u542f\u52a8\u5165\u5e93\u7a0b\u5e8f"),
                            (b"start deposit task", "\u521b\u5efa\u811a\u672c\u6258\u7ba1\u4efb\u52a1"),
                            (
                                b"wait deposit task",
                                "\u7b49\u5f85\u811a\u672c\u6258\u7ba1\u4efb\u52a1\u6267\u884c\u7ed3\u679c",
                            ),
                            (
                                b"stop old deposit task",
                                "\u53d6\u6d88\u8001\u7248\u672c\u914d\u7f6e\u7684IP\u6258\u7ba1",
                            ),
                            (b"finished", "\u4efb\u52a1\u6d41\u7a0b\u5b8c\u6210"),
                        ],
                    ),
                ),
                (
                    "result_data",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u4efb\u52a1\u6267\u884c\u7ed3\u679c(JSON)"),
                ),
                ("ex_data", models.TextField(verbose_name="\u4efb\u52a1\u5f02\u5e38\u4fe1\u606f")),
                (
                    "config",
                    models.ForeignKey(
                        related_name="tasks",
                        verbose_name="\u6240\u5c5e\u914d\u7f6e",
                        to="monitor.ShellCollectorConfig",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "get_latest_by": "update_time",
                "verbose_name": "\u811a\u672c\u91c7\u96c6\u6258\u7ba1\u4efb\u52a1",
            },
        ),
        migrations.DeleteModel(
            name="CallMethodRecord",
        ),
        migrations.RenameField(
            model_name="dashboardmenulocation",
            old_name="menu_id",
            new_name="_menu_id",
        ),
        migrations.RenameField(
            model_name="dashboardmenulocation",
            old_name="view_id",
            new_name="_view_id",
        ),
        migrations.AddField(
            model_name="dashboardmenulocation",
            name="menu",
            field=models.ForeignKey(
                default=1,
                verbose_name="\u4eea\u8868\u76d8\u83dc\u5355",
                to="monitor.DashboardMenu",
                on_delete=models.CASCADE,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dashboardmenulocation",
            name="view",
            field=models.ForeignKey(
                related_name="locations",
                default=1,
                verbose_name="\u4eea\u8868\u76d8\u89c6\u56fe",
                to="monitor.DashboardView",
                on_delete=models.CASCADE,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(set_menu_id),
        migrations.RemoveField(
            model_name="dashboardmenulocation",
            name="_menu_id",
        ),
        migrations.RemoveField(
            model_name="dashboardmenulocation",
            name="_view_id",
        ),
        migrations.AlterField(
            model_name="datacollector",
            name="data_set",
            field=models.CharField(max_length=225, verbose_name="db_name+table_name"),
        ),
        migrations.AlterField(
            model_name="scenariomenu",
            name="system_menu",
            field=models.CharField(
                default=b"",
                max_length=32,
                verbose_name="\u7cfb\u7edf\u83dc\u5355\u680f",
                blank=True,
                choices=[
                    ("", "\u7528\u6237\u81ea\u5b9a\u4e49"),
                    ("favorite", "\u5173\u6ce8"),
                    ("default", "\u9ed8\u8ba4\u5206\u7ec4"),
                ],
            ),
        ),
        migrations.AlterUniqueTogether(
            name="logcollector",
            unique_together={("biz_id", "data_set")},
        ),
        migrations.AlterUniqueTogether(
            name="logcollectorhost",
            unique_together={("log_collector", "ip", "plat_id")},
        ),
    ]
