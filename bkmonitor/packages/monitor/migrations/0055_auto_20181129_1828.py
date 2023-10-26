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
        ("monitor", "0054_auto_20181119_1511"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComponentCategory",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("display_name", models.CharField(max_length=50, verbose_name="\u5206\u7c7b\u663e\u793a\u540d\u79f0")),
            ],
            options={
                "verbose_name": "\u7ec4\u4ef6\u5206\u7c7b",
                "verbose_name_plural": "\u7ec4\u4ef6\u5206\u7c7b",
            },
        ),
        migrations.CreateModel(
            name="ComponentCategoryRelationship",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "is_internal",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u4e3a\u5185\u7f6e\u7ec4\u4ef6"),
                ),
                (
                    "component_name",
                    models.CharField(
                        max_length=32,
                        null=True,
                        verbose_name="\u7ec4\u4ef6\u540d\u79f0\uff08\u5185\u7f6e\u7ec4\u4ef6\u4e13\u7528\uff09",
                        blank=True,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        related_name="components",
                        verbose_name="\u6240\u5c5e\u5206\u7c7b",
                        to="monitor.ComponentCategory",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "exporter_component",
                    models.OneToOneField(
                        related_name="relative_category",
                        null=True,
                        verbose_name="\u81ea\u5b9a\u4e49\u7ec4\u4ef6\uff08\u975e\u5185\u7f6e\u7ec4\u4ef6\u4e13\u7528\uff09",
                        to="monitor.ExporterComponent",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "verbose_name": "\u7ec4\u4ef6\u5206\u7c7b\u5173\u7cfb",
                "verbose_name_plural": "\u7ec4\u4ef6\u5206\u7c7b\u5173\u7cfb",
            },
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
    ]
