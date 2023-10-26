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

import metadata.models.storage


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0034_auto_20190919_1940"),
    ]

    operations = [
        migrations.CreateModel(
            name="ESStorage",
            fields=[
                (
                    "table_id",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u7ed3\u679c\u8868\u540d", primary_key=True
                    ),
                ),
                (
                    "date_format",
                    models.CharField(
                        default="%Y%m%d%H%M%S", max_length=64, verbose_name="\u65e5\u671f\u683c\u5f0f\u5316\u914d\u7f6e"
                    ),
                ),
                (
                    "slice_size",
                    models.IntegerField(default=500, verbose_name="index\u5927\u5c0f\u5207\u5206\u9608\u503c"),
                ),
                (
                    "slice_gap",
                    models.IntegerField(default=120, verbose_name="index\u5206\u7247\u65f6\u95f4\u95f4\u9694"),
                ),
                ("index_settings", models.TextField(verbose_name="\u7d22\u5f15\u914d\u7f6e\u4fe1\u606f")),
                ("mapping_settings", models.TextField(verbose_name="\u522b\u540d\u914d\u7f6e\u4fe1\u606f")),
                ("storage_cluster_id", models.IntegerField(verbose_name="\u5b58\u50a8\u96c6\u7fa4")),
            ],
            bases=(models.Model, metadata.models.storage.StorageResultTable),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="custom_label",
            field=models.CharField(
                default=None, max_length=256, null=True, verbose_name="\u81ea\u5b9a\u4e49\u6807\u7b7e"
            ),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="is_ssl_verify",
            field=models.BooleanField(default=False, verbose_name="SSL\u9a8c\u8bc1\u662f\u5426\u5f3a\u9a8c\u8bc1"),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="schema",
            field=models.CharField(default=None, max_length=32, null=True, verbose_name="\u8bbf\u95ee\u534f\u8bae"),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="version",
            field=models.CharField(
                default=None, max_length=64, null=True, verbose_name="\u5b58\u50a8\u96c6\u7fa4\u7248\u672c"
            ),
        ),
        migrations.AlterField(
            model_name="resulttable",
            name="default_storage",
            field=models.CharField(
                max_length=32,
                verbose_name="\u9ed8\u8ba4\u5b58\u50a8\u65b9\u6848",
                choices=[
                    ("influxdb", "influxDB"),
                    ("kafka", "kafka"),
                    ("redis", "redis"),
                    ("elasticsearch", "elasticsearch"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="resulttablefieldoption",
            name="name",
            field=models.CharField(
                max_length=128,
                verbose_name="option\u540d\u79f0",
                choices=[
                    ("es_type", "es_type"),
                    ("es_include_in_all", "es_include_in_all"),
                    ("es_format", "es_format"),
                    ("es_doc_values", "es_doc_values"),
                    ("es_index", "es_index"),
                ],
            ),
        ),
    ]
