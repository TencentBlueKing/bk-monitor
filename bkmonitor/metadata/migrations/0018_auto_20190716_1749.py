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
        ("metadata", "0017_auto_20190716_1721"),
    ]

    operations = [
        migrations.CreateModel(
            name="KafkaStorage",
            fields=[
                (
                    "table_id",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u7ed3\u679c\u8868\u540d", primary_key=True
                    ),
                ),
                ("topic", models.CharField(max_length=256, verbose_name="topic")),
                ("partition", models.IntegerField(default=1, verbose_name="topic\u5206\u533a\u6570\u91cf")),
                ("storage_cluster_id", models.IntegerField(verbose_name="\u5b58\u50a8\u96c6\u7fa4")),
            ],
            bases=(models.Model, metadata.models.StorageResultTable),
        ),
        migrations.AlterField(
            model_name="redisstorage",
            name="key",
            field=models.CharField(max_length=256, verbose_name="\u5b58\u50a8\u952e\u503c"),
        ),
    ]
