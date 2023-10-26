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
        ("monitor", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="data_id",
            field=models.CharField(default=b"", max_length=100, verbose_name="\u540e\u53f0\u4fa7\u6570\u636e\u6e90id"),
        ),
        migrations.AddField(
            model_name="datasource",
            name="result_table_id",
            field=models.CharField(default=b"", max_length=100, verbose_name="\u540e\u53f0\u4fa7\u8868id"),
        ),
        migrations.AddField(
            model_name="datasource",
            name="update_user",
            field=models.CharField(default=b"", max_length=50, verbose_name="\u6700\u65b0\u4fee\u6539\u4eba"),
        ),
    ]
