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
        ("monitor", "0083_uptimechecktask_subscription_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="UptimeCheckTaskCollectorLog",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "error_log",
                    bkmonitor.utils.db.fields.JsonField(default="{}", verbose_name="\u9519\u8bef\u65e5\u5fd7"),
                ),
                (
                    "task_id",
                    models.ForeignKey(
                        verbose_name="\u62e8\u6d4b\u4efb\u52a1ID",
                        to="monitor.UptimeCheckTask",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
    ]
