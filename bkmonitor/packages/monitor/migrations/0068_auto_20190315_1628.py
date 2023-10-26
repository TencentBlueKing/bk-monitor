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

import monitor.models


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0067_auto_20190304_2343"),
    ]

    operations = [
        migrations.CreateModel(
            name="UploadedFile",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("original_filename", models.CharField(max_length=255, verbose_name="\u539f\u59cb\u6587\u4ef6\u540d")),
                ("actual_filename", models.CharField(max_length=255, verbose_name="\u6587\u4ef6\u540d")),
                ("relative_path", models.TextField(verbose_name="\u6587\u4ef6\u76f8\u5bf9\u8def\u5f84")),
                (
                    "file_data",
                    models.FileField(
                        upload_to=monitor.models.generate_upload_path, verbose_name="\u6587\u4ef6\u5185\u5bb9"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterModelOptions(
            name="scriptcollectorconfig",
            options={"verbose_name": "\u811a\u672c\u91c7\u96c6\u914d\u7f6e"},
        ),
        migrations.AlterModelOptions(
            name="scriptcollectorinstance",
            options={"verbose_name": "\u811a\u672c\u91c7\u96c6\u5b9e\u4f8b"},
        ),
    ]
