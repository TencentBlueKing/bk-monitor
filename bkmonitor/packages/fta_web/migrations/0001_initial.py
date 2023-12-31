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
# Generated by Django 1.11.23 on 2021-06-07 08:53
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AlertExperience",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("metric", models.CharField(blank=True, default="", max_length=128, verbose_name="指标ID")),
                ("alert_name", models.CharField(blank=True, default="", max_length=128, verbose_name="告警名称")),
                ("description", models.TextField(verbose_name="处理建议")),
            ],
        ),
        migrations.CreateModel(
            name="SearchFavorite",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("name", models.CharField(max_length=64, verbose_name="收藏名称")),
                (
                    "search_type",
                    models.CharField(
                        choices=[("alert", "告警"), ("event", "事件"), ("action", "处理动作")],
                        default="alert",
                        max_length=32,
                        verbose_name="检索类型",
                    ),
                ),
                ("params", bkmonitor.utils.db.fields.JsonField(verbose_name="检索条件")),
            ],
            options={
                "verbose_name": "检索收藏",
                "verbose_name_plural": "检索收藏",
                "ordering": ("-update_time",),
            },
        ),
        migrations.CreateModel(
            name="SearchHistory",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                (
                    "search_type",
                    models.CharField(
                        choices=[("alert", "告警"), ("event", "事件"), ("action", "处理动作")],
                        default="alert",
                        max_length=32,
                        verbose_name="检索类型",
                    ),
                ),
                ("params", bkmonitor.utils.db.fields.JsonField(verbose_name="检索条件")),
                ("duration", models.FloatField(null=True, verbose_name="检索耗时")),
            ],
            options={
                "verbose_name": "检索历史",
                "verbose_name_plural": "检索历史",
            },
        ),
        migrations.AlterUniqueTogether(
            name="alertexperience",
            unique_together={("bk_biz_id", "metric", "alert_name")},
        ),
    ]
