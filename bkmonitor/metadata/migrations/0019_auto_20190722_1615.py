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
        ("metadata", "0018_auto_20190716_1749"),
    ]

    operations = [
        migrations.AddField(
            model_name="redisstorage",
            name="is_sentinel",
            field=models.BooleanField(default=False, verbose_name="\u662f\u5426\u54e8\u5175\u6a21\u5f0f"),
        ),
        migrations.AddField(
            model_name="redisstorage",
            name="master_name",
            field=models.CharField(
                default="", max_length=128, verbose_name="\u54e8\u5175\u6a21\u5f0fmaster\u540d\u5b57"
            ),
        ),
        migrations.AlterField(
            model_name="resulttablefield",
            name="tag",
            field=models.CharField(
                max_length=16,
                verbose_name="\u5b57\u6bb5\u6807\u7b7e",
                choices=[
                    ("unknown", "\u672a\u77e5\u7c7b\u578b\u5b57\u6bb5"),
                    ("dimension", "\u7ef4\u5ea6\u5b57\u6bb5"),
                    ("metric", "\u6307\u6807\u5b57\u6bb5"),
                    ("timestamp", "\u65f6\u95f4\u6233\u5b57\u6bb5"),
                    ("group", "\u6807\u7b7e\u5b57\u6bb5"),
                    ("const", "\u5e38\u91cf"),
                ],
            ),
        ),
    ]
