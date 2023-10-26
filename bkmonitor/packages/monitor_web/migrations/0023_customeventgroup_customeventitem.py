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

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0022_delete_rolepermission"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomEventGroup",
            fields=[
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "bk_event_group_id",
                    models.IntegerField(serialize=False, verbose_name="\u4e8b\u4ef6\u5206\u7ec4ID", primary_key=True),
                ),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="\u4e1a\u52a1ID", db_index=True)),
                ("name", models.CharField(max_length=128, verbose_name="\u540d\u79f0")),
                ("scenario", models.CharField(max_length=128, verbose_name="\u76d1\u63a7\u573a\u666f", db_index=True)),
                ("is_enable", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CustomEventItem",
            fields=[
                ("bk_event_id", models.IntegerField(serialize=False, verbose_name="\u4e8b\u4ef6ID", primary_key=True)),
                ("event_name", models.CharField(max_length=128, verbose_name="\u540d\u79f0")),
                ("dimension_list", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u7ef4\u5ea6")),
                (
                    "bk_event_group",
                    models.ForeignKey(
                        related_name="event_info_list",
                        verbose_name="\u4e8b\u4ef6\u5206\u7ec4ID",
                        to="monitor_web.CustomEventGroup",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
    ]
