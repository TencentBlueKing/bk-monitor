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
        ("metadata", "0044_auto_20191119_1752"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomEvent",
            fields=[
                ("custom_event_id", models.AutoField(serialize=False, verbose_name="\u4e8b\u4ef6ID", primary_key=True)),
                ("bk_event_group_id", models.IntegerField(verbose_name="\u4e8b\u4ef6\u6240\u5c5e\u5206\u7ec4ID")),
                ("custom_event_name", models.CharField(max_length=255, verbose_name="\u4e8b\u4ef6\u540d\u79f0")),
            ],
            options={
                "verbose_name": "\u4e8b\u4ef6\u63cf\u8ff0\u8bb0\u5f55",
                "verbose_name_plural": "\u4e8b\u4ef6\u63cf\u8ff0\u8bb0\u5f55\u8868",
            },
        ),
        migrations.CreateModel(
            name="CustomEventDimension",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("custom_event_id", models.IntegerField(verbose_name="\u4e8b\u4ef6ID")),
                ("dimension_name", models.CharField(max_length=255, verbose_name="\u7ef4\u5ea6\u540d\u79f0")),
                ("dimension_ch_name", models.CharField(max_length=255, verbose_name="\u7ef4\u5ea6\u4e2d\u6587\u540d")),
            ],
            options={
                "verbose_name": "\u4e8b\u4ef6\u7ef4\u5ea6\u8bb0\u5f55",
                "verbose_name_plural": "\u4e8b\u4ef6\u7ef4\u5ea6\u8bb0\u5f55\u8868",
            },
        ),
        migrations.CreateModel(
            name="EventGroup",
            fields=[
                (
                    "bk_event_group_id",
                    models.AutoField(serialize=False, verbose_name="\u5206\u7ec4ID", primary_key=True),
                ),
                ("event_group_name", models.CharField(max_length=255, verbose_name="\u4e8b\u4ef6\u5206\u7ec4\u540d")),
                ("bk_data_id", models.IntegerField(verbose_name="\u6570\u636e\u6e90ID", db_index=True)),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID", db_index=True)),
                ("label", models.CharField(default="others", max_length=128, verbose_name="\u4e8b\u4ef6\u6807\u7b7e")),
                ("is_enable", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_delete", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("creator", models.CharField(max_length=255, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("last_modify_user", models.CharField(max_length=32, verbose_name="\u6700\u540e\u66f4\u65b0\u8005")),
                (
                    "last_modify_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="customeventdimension",
            unique_together={("custom_event_id", "dimension_name")},
        ),
        migrations.AlterUniqueTogether(
            name="customevent",
            unique_together={("bk_event_group_id", "custom_event_name")},
        ),
    ]
