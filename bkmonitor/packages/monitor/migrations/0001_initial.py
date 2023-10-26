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

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Datasource",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("cc_biz_id", models.CharField(max_length=30, verbose_name="cc\u4e1a\u52a1id")),
                ("data_set", models.CharField(max_length=100, verbose_name="\u6570\u636e\u6e90\u8868\u540d")),
                ("data_desc", models.CharField(max_length=100, verbose_name="\u6570\u636e\u6e90\u4e2d\u6587\u540d")),
                ("data_json", models.TextField(verbose_name="\u6570\u636e\u6e90json\u6570\u636e")),
                (
                    "status",
                    models.CharField(
                        default=b"normal",
                        max_length=20,
                        verbose_name="\u6570\u636e\u6e90\u72b6\u6001",
                        choices=[(b"normal", "\u6b63\u5e38"), (b"stopped", "\u505c\u7528")],
                    ),
                ),
                ("creator", models.CharField(max_length=50, verbose_name="\u521b\u5efa\u4eba")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u8fd1\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
            options={
                "verbose_name": "\u6570\u636e\u6e90",
                "verbose_name_plural": "\u6570\u636e\u6e90",
            },
        ),
        migrations.AlterUniqueTogether(
            name="datasource",
            unique_together={("cc_biz_id", "data_set")},
        ),
    ]
