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

import metadata.models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunSQL("drop table if exists metadata_clusterinfo "),
        migrations.RunSQL("drop table if exists metadata_datasource "),
        migrations.RunSQL("drop table if exists metadata_datasourceresulttable "),
        migrations.RunSQL("drop table if exists metadata_influxdbstorage "),
        migrations.RunSQL("drop table if exists metadata_kafkatopicinfo "),
        migrations.RunSQL("drop table if exists metadata_resulttable "),
        migrations.RunSQL("drop table if exists metadata_resulttablefield "),
        migrations.RunSQL("drop table if exists metadata_resulttablerecordformat "),
        migrations.CreateModel(
            name="ClusterInfo",
            fields=[
                ("cluster_id", models.AutoField(serialize=False, verbose_name="\u96c6\u7fa4ID", primary_key=True)),
                (
                    "cluster_name",
                    models.CharField(unique=True, max_length=128, verbose_name="\u96c6\u7fa4\u540d\u79f0"),
                ),
                (
                    "cluster_type",
                    models.CharField(max_length=32, verbose_name="\u96c6\u7fa4\u7c7b\u578b", db_index=True),
                ),
                ("domain_name", models.CharField(max_length=128, verbose_name="\u96c6\u7fa4\u57df\u540d")),
                ("port", models.IntegerField(verbose_name="\u7aef\u53e3")),
                (
                    "description",
                    models.CharField(max_length=256, verbose_name="\u96c6\u7fa4\u5907\u6ce8\u8bf4\u660e\u4fe1\u606f"),
                ),
                ("is_default_cluster", models.BooleanField(verbose_name="\u662f\u5426\u9ed8\u8ba4\u96c6\u7fa4")),
            ],
            options={
                "verbose_name": "\u96c6\u7fa4\u914d\u7f6e\u4fe1\u606f",
                "verbose_name_plural": "\u96c6\u7fa4\u914d\u7f6e\u4fe1\u606f",
            },
        ),
        migrations.CreateModel(
            name="DataSource",
            fields=[
                (
                    "bk_data_id",
                    models.AutoField(serialize=False, verbose_name="\u6570\u636e\u6e90ID", primary_key=True),
                ),
                (
                    "data_name",
                    models.CharField(
                        unique=True, max_length=128, verbose_name="\u6570\u636e\u6e90\u540d\u79f0", db_index=True
                    ),
                ),
                ("data_description", models.TextField(verbose_name="\u6570\u636e\u6e90\u63cf\u8ff0")),
                ("mq_cluster_id", models.IntegerField(verbose_name="\u6d88\u606f\u961f\u5217\u96c6\u7fa4ID")),
                ("mq_config_id", models.IntegerField(verbose_name="\u6d88\u606f\u961f\u5217\u914d\u7f6eID")),
                ("etl_config", models.TextField(verbose_name="ETL\u914d\u7f6e")),
                (
                    "is_custom_source",
                    models.BooleanField(verbose_name="\u662f\u5426\u81ea\u5b9a\u4e49\u6570\u636e\u6e90"),
                ),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("last_modify_user", models.CharField(max_length=32, verbose_name="\u6700\u540e\u66f4\u65b0\u8005")),
                (
                    "last_modify_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
            options={
                "verbose_name": "\u6570\u636e\u6e90\u7ba1\u7406",
                "verbose_name_plural": "\u6570\u636e\u6e90\u7ba1\u7406\u8868",
            },
        ),
        migrations.CreateModel(
            name="DataSourceResultTable",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("bk_data_id", models.IntegerField(verbose_name="\u6570\u636e\u6e90ID")),
                ("table_id", models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868\u540d")),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
            ],
            options={
                "verbose_name": "\u6570\u636e\u6e90-\u7ed3\u679c\u8868\u5173\u7cfb\u914d\u7f6e",
                "verbose_name_plural": "\u6570\u636e\u6e90-\u7ed3\u679c\u8868\u5173\u7cfb\u914d\u7f6e\u8868",
            },
        ),
        migrations.CreateModel(
            name="InfluxDBStorage",
            fields=[
                (
                    "table_id",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u7ed3\u679c\u8868\u540d", primary_key=True
                    ),
                ),
                ("storage_cluster_id", models.IntegerField(verbose_name="\u5b58\u50a8\u96c6\u7fa4")),
                (
                    "real_table_name",
                    models.CharField(max_length=128, verbose_name="\u5b9e\u9645\u5b58\u50a8\u8868\u540d"),
                ),
                ("database", models.CharField(max_length=128, verbose_name="\u6570\u636e\u5e93\u540d")),
                (
                    "source_duration_time",
                    models.CharField(max_length=32, verbose_name="\u539f\u59cb\u6570\u636e\u4fdd\u7559\u65f6\u95f4"),
                ),
                (
                    "down_sample_table",
                    models.CharField(max_length=128, verbose_name="\u964d\u6837\u7ed3\u679c\u8868\u540d"),
                ),
                (
                    "down_sample_gap",
                    models.CharField(max_length=32, verbose_name="\u964d\u6837\u805a\u5408\u533a\u95f4"),
                ),
                (
                    "down_sample_duration_time",
                    models.CharField(
                        max_length=32, verbose_name="\u964d\u6837\u6570\u636e\u7684\u4fdd\u5b58\u65f6\u95f4"
                    ),
                ),
            ],
            options={
                "verbose_name": "TSDB\u7269\u7406\u8868\u914d\u7f6e",
                "verbose_name_plural": "TSDB\u7269\u7406\u8868\u914d\u7f6e",
            },
            bases=(models.Model, metadata.models.StorageResultTable),
        ),
        migrations.CreateModel(
            name="KafkaTopicInfo",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("bk_data_id", models.IntegerField(unique=True, verbose_name="\u6570\u636e\u6e90ID")),
                ("topic", models.CharField(max_length=128, verbose_name="kafka topic")),
                ("partition", models.IntegerField(verbose_name="\u5206\u533a\u6570\u91cf")),
            ],
            options={
                "verbose_name": "Kafka\u6d88\u606f\u961f\u5217\u914d\u7f6e",
                "verbose_name_plural": "Kafka\u6d88\u606f\u961f\u5217\u914d\u7f6e\u8868",
            },
        ),
        migrations.CreateModel(
            name="ResultTable",
            fields=[
                (
                    "table_id",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u7ed3\u679c\u8868\u540d", primary_key=True
                    ),
                ),
                (
                    "table_name_zh",
                    models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868\u4e2d\u6587\u540d"),
                ),
                (
                    "is_custom_table",
                    models.BooleanField(verbose_name="\u662f\u5426\u81ea\u5b9a\u4e49\u7ed3\u679c\u8868"),
                ),
                (
                    "schema_type",
                    models.CharField(
                        max_length=64,
                        verbose_name="schema\u914d\u7f6e\u65b9\u6848",
                        choices=[
                            ("free", "\u65e0\u56fa\u5b9a\u5b57\u6bb5"),
                            ("dynamic", "\u52a8\u6001\u5b57\u6bb5"),
                            ("fixed", "\u56fa\u5b9a\u5b57\u6bb5"),
                        ],
                    ),
                ),
                (
                    "default_storage",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u9ed8\u8ba4\u5b58\u50a8\u65b9\u6848",
                        choices=[("influxdb", "influxDB"), ("kafka", "kafka")],
                    ),
                ),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("last_modify_user", models.CharField(max_length=32, verbose_name="\u6700\u540e\u66f4\u65b0\u8005")),
                (
                    "last_modify_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
            options={
                "verbose_name": "\u903b\u8f91\u7ed3\u679c\u8868",
                "verbose_name_plural": "\u903b\u8f91\u7ed3\u679c\u8868",
            },
        ),
        migrations.CreateModel(
            name="ResultTableField",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("table_id", models.CharField(max_length=128, verbose_name="\u7ed3\u679c\u8868\u540d")),
                ("field_name", models.CharField(max_length=32, verbose_name="\u5b57\u6bb5\u540d")),
                (
                    "field_type",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u5b57\u6bb5\u7c7b\u578b",
                        choices=[
                            ("int", "\u6574\u578b"),
                            ("float", "\u6d6e\u70b9\u578b"),
                            ("string", "\u5b57\u7b26\u578b"),
                            ("string", "\u5e03\u5c14\u578b"),
                            ("timestamp", "\u65f6\u95f4\u5b57\u6bb5"),
                        ],
                    ),
                ),
                ("unit", models.CharField(default="", max_length=16, verbose_name="\u5b57\u6bb5\u5355\u4f4d")),
                (
                    "tag",
                    models.CharField(
                        max_length=16,
                        verbose_name="\u5b57\u6bb5\u6807\u7b7e",
                        choices=[
                            ("unknown", "\u672a\u77e5\u7c7b\u578b\u5b57\u6bb5"),
                            ("dimension", "\u7ef4\u5ea6\u5b57\u6bb5"),
                            ("value", "\u6307\u6807\u5b57\u6bb5"),
                            ("const", "\u5e38\u91cf"),
                        ],
                    ),
                ),
                (
                    "is_config_by_user",
                    models.BooleanField(verbose_name="\u662f\u5426\u7528\u6237\u786e\u8ba4\u5b57\u6bb5"),
                ),
                (
                    "default_value",
                    models.CharField(
                        default=None, max_length=128, null=True, verbose_name="\u5b57\u6bb5\u9ed8\u8ba4\u503c"
                    ),
                ),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("last_modify_user", models.CharField(max_length=32, verbose_name="\u6700\u540e\u66f4\u65b0\u8005")),
                (
                    "last_modify_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
            options={
                "verbose_name": "\u7ed3\u679c\u8868\u5b57\u6bb5",
                "verbose_name_plural": "\u7ed3\u679c\u8868\u5b57\u6bb5\u8868",
            },
        ),
        migrations.AlterUniqueTogether(
            name="resulttablefield",
            unique_together={("table_id", "field_name")},
        ),
        migrations.AlterUniqueTogether(
            name="influxdbstorage",
            unique_together={("real_table_name", "database")},
        ),
        migrations.AlterUniqueTogether(
            name="datasourceresulttable",
            unique_together={("bk_data_id", "table_id")},
        ),
    ]
