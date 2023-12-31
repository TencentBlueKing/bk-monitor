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
# Generated by Django 1.11.23 on 2020-11-11 08:39


import bkmonitor.utils.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0023_auto_20201106_1443"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportItems",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("mail_title", models.CharField(max_length=512, verbose_name="邮件标题")),
                ("receivers", bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="接收者")),
                ("managers", bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="管理员")),
                ("frequency", bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="发送频率")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ReportStatus",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_item", models.IntegerField(db_index=True, verbose_name="订阅报表ID")),
                ("mail_title", models.CharField(max_length=512, verbose_name="邮件标题")),
                ("create_time", models.DateTimeField(verbose_name="发送时间")),
                ("details", bkmonitor.utils.db.fields.JsonField(verbose_name="发送详情")),
                ("is_success", models.BooleanField(default=False, verbose_name="是否成功")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.RenameModel(
            old_name="report_contents",
            new_name="ReportContents",
        ),
        migrations.DeleteModel(
            name="report_items",
        ),
        migrations.DeleteModel(
            name="report_status",
        ),
    ]
