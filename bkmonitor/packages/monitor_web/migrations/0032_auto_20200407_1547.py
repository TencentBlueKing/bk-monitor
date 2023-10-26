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
        ("monitor_web", "0031_customeventgroup_table_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeventgroup",
            name="type",
            field=models.CharField(
                default="custom_event",
                max_length=128,
                verbose_name="\u4e8b\u4ef6\u7ec4\u7c7b\u578b",
                choices=[("custom_event", "custom_event"), ("keywords", "keywords")],
            ),
        ),
        migrations.AlterField(
            model_name="collectconfigmeta",
            name="collect_type",
            field=models.CharField(
                db_index=True,
                max_length=32,
                verbose_name="\u91c7\u96c6\u65b9\u5f0f",
                choices=[
                    ("Exporter", "Exporter"),
                    ("Script", "Script"),
                    ("JMX", "JMX"),
                    ("DataDog", "DataDog"),
                    ("Pushgateway", "BK-Pull"),
                    ("Built-In", "BK-Monitor"),
                    ("Log", "Log"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="collectorpluginmeta",
            name="plugin_type",
            field=models.CharField(
                db_index=True,
                max_length=32,
                verbose_name="\u63d2\u4ef6\u7c7b\u578b",
                choices=[
                    ("Exporter", "Exporter"),
                    ("Script", "Script"),
                    ("JMX", "JMX"),
                    ("DataDog", "DataDog"),
                    ("Pushgateway", "BK-Pull"),
                    ("Built-In", "BK-Monitor"),
                    ("Log", "Log"),
                ],
            ),
        ),
    ]
