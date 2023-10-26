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
        ("monitor_web", "0011_auto_20190812_2159"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataTargetMapping",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "data_source_label",
                    models.CharField(max_length=255, verbose_name="\u6570\u636e\u6765\u6e90\u6807\u7b7e"),
                ),
                (
                    "data_type_label",
                    models.CharField(max_length=255, verbose_name="\u6570\u636e\u7c7b\u578b\u6807\u7b7e"),
                ),
                ("result_table_label", models.CharField(max_length=255, verbose_name="\u7ed3\u679c\u8868\u6807\u7b7e")),
                ("data_target", models.CharField(max_length=255, verbose_name="\u6570\u636e\u76ee\u6807")),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="datatargetmapping",
            unique_together={("data_source_label", "data_type_label", "result_table_label")},
        ),
    ]
