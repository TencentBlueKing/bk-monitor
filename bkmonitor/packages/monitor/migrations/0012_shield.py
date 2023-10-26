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
        ("monitor", "0011_datacollector"),
    ]

    operations = [
        migrations.CreateModel(
            name="Shield",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.CharField(max_length=256, verbose_name="\u4e1a\u52a1ID")),
                (
                    "begin_time",
                    models.DateTimeField(verbose_name="\u5c4f\u853d\u5f00\u59cb\u65f6\u95f4", db_index=True),
                ),
                ("end_time", models.DateTimeField(verbose_name="\u5c4f\u853d\u7ed3\u675f\u65f6\u95f4", db_index=True)),
                ("dimension", models.TextField(verbose_name="\u5c4f\u853d\u7ef4\u5ea6(JSON)")),
                ("description", models.TextField(default=b"", verbose_name="\u5c4f\u853d\u63cf\u8ff0")),
                ("event_raw_id", models.CharField(max_length=256, verbose_name="\u5c4f\u853dID")),
                (
                    "hours_delay",
                    models.IntegerField(default=0, verbose_name="\u5c4f\u853d\u65f6\u95f4\uff08\u5c0f\u65f6\uff09"),
                ),
                (
                    "backend_id",
                    models.IntegerField(
                        default=0, verbose_name="\u5173\u8054\u76d1\u63a7\u544a\u8b66\u540e\u53f0\u7b56\u7565ID"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
