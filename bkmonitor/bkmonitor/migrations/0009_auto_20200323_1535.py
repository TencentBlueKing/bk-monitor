# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0008_merge"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeventqueryconfig",
            name="result_table_id",
            field=models.CharField(default="", max_length=256, verbose_name="\u7ed3\u679c\u8868"),
        ),
        migrations.AlterField(
            model_name="customeventqueryconfig",
            name="agg_method",
            field=models.CharField(default="count", max_length=64, verbose_name="\u805a\u5408\u65b9\u6cd5"),
        ),
    ]
