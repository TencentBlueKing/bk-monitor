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


import django.utils.timezone
import monitor.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0006_require_contenttypes_0002"),
        ("monitor", "0023_dashboardmenu_dashboardmenulocation_dashboardview"),
    ]

    operations = [
        migrations.CreateModel(
            name="Application",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("cc_biz_id", models.IntegerField(unique=True)),
                ("name", models.CharField(max_length=128)),
            ],
            options={
                "permissions": (
                    ("view_application", "Can view application"),
                    ("manage_application", "Can manage application"),
                ),
            },
        ),
        migrations.CreateModel(
            name="ApplicationConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("cc_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1id")),
                ("key", models.CharField(max_length=255, verbose_name="key")),
                ("value", monitor.models.ConfigDataField(verbose_name="\u914d\u7f6e\u4fe1\u606f")),
                ("data_created", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("data_updated", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
            ],
            options={
                "verbose_name": "\u4e1a\u52a1\u914d\u7f6e\u4fe1\u606f",
            },
        ),
        migrations.CreateModel(
            name="ApplicationGroupMembership",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("application", models.ForeignKey(to="monitor.Application", on_delete=models.CASCADE)),
                ("group", models.ForeignKey(to="auth.Group", on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name="GlobalConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("key", models.CharField(unique=True, max_length=255, verbose_name="key")),
                ("value", monitor.models.ConfigDataField(verbose_name="\u914d\u7f6e\u4fe1\u606f")),
                ("data_created", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("data_updated", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
            ],
            options={
                "verbose_name": "\u5168\u5c40\u914d\u7f6e\u4fe1\u606f",
            },
        ),
        migrations.CreateModel(
            name="IndexColorConf",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("range", models.CharField(max_length=20, verbose_name="\u53d6\u503c\u533a\u95f4")),
                ("color", models.CharField(max_length=10, verbose_name="\u989c\u8272")),
                ("slug", models.CharField(max_length=32, verbose_name="\u65b9\u6848\u6807\u7b7e")),
            ],
        ),
        migrations.CreateModel(
            name="UserConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("username", models.CharField(max_length=30, verbose_name="\u7528\u6237\u540d")),
                ("key", models.CharField(max_length=255, verbose_name="key")),
                ("value", monitor.models.ConfigDataField(verbose_name="\u914d\u7f6e\u4fe1\u606f")),
                ("data_created", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("data_updated", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
            ],
            options={
                "verbose_name": "\u7528\u6237\u914d\u7f6e\u4fe1\u606f",
            },
        ),
        migrations.AlterUniqueTogether(
            name="userconfig",
            unique_together={("username", "key")},
        ),
        migrations.AlterUniqueTogether(
            name="applicationconfig",
            unique_together={("cc_biz_id", "key")},
        ),
        migrations.AddField(
            model_name="application",
            name="groups",
            field=models.ManyToManyField(to="auth.Group", through="monitor.ApplicationGroupMembership"),
        ),
        migrations.AlterUniqueTogether(
            name="applicationgroupmembership",
            unique_together={("application", "group")},
        ),
    ]
