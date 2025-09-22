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
        ("monitor", "0010_auto_20161220_1716"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataCollector",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("source_type", models.CharField(max_length=32, verbose_name="\u6570\u636e\u6e90\u7c7b\u578b")),
                ("collector_config", models.TextField(verbose_name="\u6570\u636e\u63a5\u5165\u914d\u7f6e\u4fe1\u606f")),
                ("data_id", models.IntegerField(verbose_name="\u4e0b\u53d1data id")),
                ("data_type", models.CharField(max_length=32, verbose_name="\u6570\u636e\u7c7b\u578b")),
                ("data_set", models.CharField(max_length=32, verbose_name="db_name+table_name")),
                ("data_description", models.TextField(null=True, verbose_name="\u6570\u636e\u63cf\u8ff0")),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
