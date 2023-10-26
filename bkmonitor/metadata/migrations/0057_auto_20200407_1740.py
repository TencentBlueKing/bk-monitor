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
        ("metadata", "0056_auto_20200407_1205"),
    ]

    operations = [
        migrations.AlterField(
            model_name="influxdbstorage",
            name="down_sample_duration_time",
            field=models.CharField(
                max_length=32, verbose_name="\u964d\u6837\u6570\u636e\u7684\u4fdd\u5b58\u65f6\u95f4", blank=True
            ),
        ),
        migrations.AlterField(
            model_name="influxdbstorage",
            name="down_sample_gap",
            field=models.CharField(max_length=32, verbose_name="\u964d\u6837\u805a\u5408\u533a\u95f4", blank=True),
        ),
        migrations.AlterField(
            model_name="influxdbstorage",
            name="down_sample_table",
            field=models.CharField(max_length=128, verbose_name="\u964d\u6837\u7ed3\u679c\u8868\u540d", blank=True),
        ),
    ]
