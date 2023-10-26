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
        ("monitor", "0012_shield"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentStatus",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("ds_id", models.IntegerField(verbose_name="\u6570\u636e\u6e90ID")),
                ("ip", models.CharField(max_length=20, verbose_name="\u91c7\u96c6\u5bf9\u8c61IP")),
                (
                    "status",
                    models.CharField(
                        default=b"",
                        max_length=20,
                        verbose_name="agent\u72b6\u6001",
                        choices=[
                            (b"create", "\u63a5\u5165\u4e2d"),
                            (b"stop", "\u505c\u7528\u4e2d"),
                            (b"normal", "\u6b63\u5e38"),
                            (b"stopped", "\u505c\u7528"),
                            (b"exception", "\u5f02\u5e38"),
                            (b"delete", "\u5254\u9664\u4e2d"),
                        ],
                    ),
                ),
                ("creator", models.CharField(max_length=50, verbose_name="\u521b\u5efa\u4eba")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_time",
                    models.DateTimeField(
                        null=True, verbose_name="\u6700\u8fd1\u4e00\u6b21\u4e0a\u62a5\u65f6\u95f4", blank=True
                    ),
                ),
            ],
            options={
                "verbose_name": "IP\u72b6\u6001",
                "verbose_name_plural": "IP\u72b6\u6001",
            },
        ),
        migrations.AddField(
            model_name="datasource",
            name="has_exception",
            field=models.BooleanField(default=False, verbose_name="\u662f\u5426\u6709\u5f02\u5e38IP"),
        ),
        migrations.AlterField(
            model_name="datasource",
            name="status",
            field=models.CharField(
                default=b"create",
                max_length=20,
                verbose_name="\u6570\u636e\u6e90\u72b6\u6001",
                choices=[
                    (b"create", "\u63a5\u5165\u4e2d"),
                    (b"stop", "\u505c\u7528\u4e2d"),
                    (b"normal", "\u6b63\u5e38"),
                    (b"stopped", "\u505c\u7528"),
                ],
            ),
        ),
        migrations.AlterUniqueTogether(
            name="agentstatus",
            unique_together={("ds_id", "ip")},
        ),
    ]
