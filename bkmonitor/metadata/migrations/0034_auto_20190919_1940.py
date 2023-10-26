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
        ("metadata", "0033_auto_20190917_2122"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResultTableFieldOption",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "value_type",
                    models.CharField(
                        max_length=64,
                        verbose_name="option\u5bf9\u5e94\u7c7b\u578b",
                        choices=[("bool", "bool"), ("string", "string")],
                    ),
                ),
                ("value", models.CharField(max_length=256, verbose_name="option\u914d\u7f6e\u5185\u5bb9")),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("table_id", models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868ID")),
                ("field_name", models.CharField(max_length=255, verbose_name="\u5b57\u6bb5\u540d")),
                (
                    "name",
                    models.CharField(
                        max_length=128,
                        verbose_name="option\u540d\u79f0",
                        choices=[
                            ("es_field_type", "es_field_type"),
                            ("es_include_in_all", "es_include_in_all"),
                            ("es_time_format", "es_time_format"),
                            ("es_doc_values", "es_doc_values"),
                            ("es_index", "es_index"),
                        ],
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        )
    ]
