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
        ("metadata", "0023_add_cmdb_level_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="Label",
            fields=[
                (
                    "label_id",
                    models.CharField(max_length=128, serialize=False, verbose_name="\u6807\u7b7eID", primary_key=True),
                ),
                ("label_name", models.CharField(max_length=128, verbose_name="\u6807\u7b7e\u540d")),
                (
                    "label_type",
                    models.CharField(
                        max_length=64,
                        verbose_name="\u6807\u7b7e\u7c7b\u578b",
                        choices=[
                            ("source_label", "\u6570\u636e\u6e90\u6807\u7b7e"),
                            ("result_table_label", "\u7ed3\u679c\u8868\u6807\u7b7e"),
                            ("type_label", "\u6570\u636e\u7c7b\u578b\u6807\u7b7e"),
                        ],
                    ),
                ),
                (
                    "is_admin_only",
                    models.BooleanField(
                        default=False,
                        verbose_name="\u662f\u5426\u53ea\u5141\u8bb8\u7ba1\u7406\u5458\u914d\u7f6e\u4f7f\u7528",
                    ),
                ),
                (
                    "parent_label",
                    models.CharField(max_length=128, null=True, verbose_name="\u7236\u7ea7\u6807\u7b7eID"),
                ),
                ("level", models.IntegerField(null=True, verbose_name="\u6807\u7b7e\u5c42\u7ea7")),
                ("index", models.IntegerField(null=True, verbose_name="\u6807\u7b7e\u6392\u5e8f")),
            ],
        ),
        migrations.AddField(
            model_name="datasource",
            name="source_label",
            field=models.CharField(default="other", max_length=128, verbose_name="\u6570\u636e\u6e90\u6807\u7b7e"),
        ),
        migrations.AddField(
            model_name="datasource",
            name="type_label",
            field=models.CharField(
                default="other", max_length=128, verbose_name="\u6570\u636e\u7c7b\u578b\u6807\u7b7e"
            ),
        ),
        migrations.AddField(
            model_name="resulttable",
            name="label",
            field=models.CharField(default="other", max_length=128, verbose_name="\u7ed3\u679c\u8868\u6807\u7b7e"),
        ),
    ]
