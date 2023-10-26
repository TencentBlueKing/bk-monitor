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

    dependencies = [
        ("metadata", "0016_auto_20190708_1740"),
    ]

    operations = [
        migrations.CreateModel(
            name="RedisStorage",
            fields=[
                (
                    "table_id",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u7ed3\u679c\u8868\u540d", primary_key=True
                    ),
                ),
                (
                    "command",
                    models.CharField(
                        default="PUBLISH", max_length=32, verbose_name="\u5199\u5165\u6d88\u606f\u7684\u547d\u4ee4"
                    ),
                ),
                ("key", models.CharField(max_length=64, verbose_name="\u5b58\u50a8\u952e\u503c")),
                ("db", models.IntegerField(default=0, verbose_name="redis DB\u914d\u7f6e")),
                ("storage_cluster_id", models.IntegerField(verbose_name="\u5b58\u50a8\u96c6\u7fa4")),
            ],
            bases=(models.Model, metadata.models.StorageResultTable),
        ),
        migrations.AlterModelOptions(
            name="influxdbclusterinfo",
            options={
                "verbose_name": "influxDB\u96c6\u7fa4\u4fe1\u606f",
                "verbose_name_plural": "influxDB\u96c6\u7fa4\u4fe1\u606f\u8868",
            },
        ),
        migrations.AlterModelOptions(
            name="influxdbhostinfo",
            options={
                "verbose_name": "influxDB\u4e3b\u673a\u4fe1\u606f",
                "verbose_name_plural": "influxDB\u4e3b\u673a\u4fe1\u606f\u8868",
            },
        ),
        migrations.AlterField(
            model_name="resulttable",
            name="default_storage",
            field=models.CharField(
                max_length=32,
                verbose_name="\u9ed8\u8ba4\u5b58\u50a8\u65b9\u6848",
                choices=[("influxdb", "influxDB"), ("kafka", "kafka"), ("redis", "redis")],
            ),
        ),
    ]
