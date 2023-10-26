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
        ("metadata", "0021_resulttable_is_deleted"),
    ]

    operations = [
        migrations.CreateModel(
            name="CMDBLevelRecord",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("source_table_id", models.CharField(max_length=128, verbose_name="\u6765\u6e90\u7ed3\u679c\u8868")),
                ("target_table_id", models.CharField(max_length=128, verbose_name="\u843d\u5730\u7ed3\u679c\u8868")),
                ("bk_data_id", models.IntegerField(verbose_name="\u6570\u636e\u6e90\u914d\u7f6eID")),
                (
                    "cmdb_level",
                    models.CharField(max_length=255, verbose_name="\u62c6\u89e3CMDB\u7684\u5c42\u7ea7\u540d"),
                ),
                (
                    "is_disable",
                    models.BooleanField(default=False, verbose_name="\u8bb0\u5f55\u662f\u5426\u5df2\u7ecf\u5e9f\u5f03"),
                ),
            ],
            options={
                "verbose_name": "CMDB\u5c42\u7ea7\u62c6\u5206\u8bb0\u5f55",
                "verbose_name_plural": "CMDB\u5c42\u7ea7\u62c6\u5206\u8bb0\u5f55\u8868",
            },
        ),
        migrations.CreateModel(
            name="ResultTableOption",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("table_id", models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868ID")),
                (
                    "name",
                    models.CharField(
                        max_length=128,
                        verbose_name="option\u540d\u79f0",
                        choices=[("cmdb_level_config", "cmdb_level_config")],
                    ),
                ),
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
            ],
        ),
        migrations.AlterModelOptions(
            name="kafkastorage",
            options={
                "verbose_name": "Kafka\u5b58\u50a8\u914d\u7f6e",
                "verbose_name_plural": "Kafka\u5b58\u50a8\u914d\u7f6e",
            },
        ),
        migrations.AlterUniqueTogether(
            name="cmdblevelrecord",
            unique_together={("source_table_id", "cmdb_level")},
        ),
    ]
