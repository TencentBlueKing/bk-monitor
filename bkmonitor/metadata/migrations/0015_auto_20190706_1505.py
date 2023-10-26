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
        ("metadata", "0014_add_heartbeat_monitor_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataSourceOption",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("bk_data_id", models.IntegerField(verbose_name="\u6570\u636e\u6e90ID")),
                (
                    "name",
                    models.CharField(
                        max_length=128,
                        verbose_name="option\u540d\u79f0",
                        choices=[
                            ("allow_dimensions_missing", "allow_dimensions_missing"),
                            ("allow_metrics_missing", "allow_metrics_missing"),
                            ("disable_metric_cutter", "disable_metric_cutter"),
                            ("inject_local_time", "inject_local_time"),
                            ("time_precision", "time_precision"),
                            ("use_source_time", "use_source_time"),
                            ("allow_use_alias_name", "allow_use_alias_name"),
                        ],
                    ),
                ),
                (
                    "value_type",
                    models.CharField(
                        max_length=64,
                        verbose_name="option\u5bf9\u5e94\u7c7b\u578b",
                        choices=[("bool", "bool"), ("string", "string")],
                    ),
                ),
                ("value", models.CharField(max_length=256, verbose_name="option\u914d\u7f6e\u5185\u5bb9")),
                ("creator", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u8005")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
            ],
        ),
        migrations.AddField(
            model_name="resulttablefield",
            name="alias_name",
            field=models.CharField(
                default="",
                max_length=64,
                verbose_name="\u5b57\u6bb5\u6620\u5c04\u524d\uff08\u4e0a\u4f20\u65f6\uff09\u540d",
            ),
        ),
    ]
