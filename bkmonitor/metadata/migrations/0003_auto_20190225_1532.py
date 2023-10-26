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
        ("metadata", "0002_create_initial_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResultTableRecordFormat",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("table_id", models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868\u540d")),
                ("metric", models.CharField(max_length=32, verbose_name="\u6307\u6807\u5b57\u6bb5")),
                (
                    "dimension_list",
                    models.CharField(max_length=32, verbose_name="\u7ef4\u5ea6\u5b57\u6bb5\u5217\u8868", db_index=True),
                ),
                ("is_available", models.BooleanField(verbose_name="\u662f\u5426\u751f\u6548")),
            ],
            options={
                "verbose_name": "\u7ed3\u679c\u8868\u5b57\u6bb5",
                "verbose_name_plural": "\u7ed3\u679c\u8868\u5b57\u6bb5\u8868",
            },
        ),
        migrations.AlterField(
            model_name="resulttablefield",
            name="tag",
            field=models.CharField(
                max_length=16,
                verbose_name="\u5b57\u6bb5\u6807\u7b7e",
                choices=[
                    ("unknown", "\u672a\u77e5\u7c7b\u578b\u5b57\u6bb5"),
                    ("dimension", "\u7ef4\u5ea6\u5b57\u6bb5"),
                    ("metric", "\u6307\u6807\u5b57\u6bb5"),
                    ("timestamp", "\u65f6\u95f4\u6233\u5b57\u6bb5"),
                    ("const", "\u5e38\u91cf"),
                ],
            ),
        ),
        migrations.AlterUniqueTogether(
            name="resulttablerecordformat",
            unique_together={("table_id", "metric", "dimension_list")},
        ),
    ]
