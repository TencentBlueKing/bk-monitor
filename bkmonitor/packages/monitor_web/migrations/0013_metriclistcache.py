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
        ("monitor_web", "0012_auto_20190824_1728"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetricListCache",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("result_table_id", models.CharField(default="", max_length=256, verbose_name="sql\u67e5\u8be2\u8868")),
                ("result_table_name", models.CharField(default="", max_length=256, verbose_name="\u8868\u522b\u540d")),
                ("metric_field", models.CharField(default="", max_length=256, verbose_name="\u6307\u6807\u540d")),
                (
                    "metric_field_name",
                    models.CharField(default="", max_length=256, verbose_name="\u6307\u6807\u522b\u540d"),
                ),
                ("unit", models.CharField(default="", max_length=256, verbose_name="\u5355\u4f4d")),
                ("unit_conversion", models.FloatField(default=1.0, verbose_name="\u5355\u4f4d\u6362\u7b97")),
                ("dimensions", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u7ef4\u5ea6\u540d")),
                ("plugin_type", models.CharField(default="", max_length=256, verbose_name="\u63d2\u4ef6\u7c7b\u578b")),
                (
                    "related_name",
                    models.CharField(
                        default="",
                        max_length=256,
                        verbose_name="\u63d2\u4ef6\u540d\u3001\u62e8\u6d4b\u4efb\u52a1\u540d",
                    ),
                ),
                (
                    "related_id",
                    models.CharField(
                        default="", max_length=256, verbose_name="\u63d2\u4ef6id\u3001\u62e8\u6d4b\u4efb\u52a1id"
                    ),
                ),
                (
                    "collect_config",
                    models.TextField(
                        default="", verbose_name="\u63d2\u4ef6\u91c7\u96c6\u5173\u8054\u91c7\u96c6\u914d\u7f6e"
                    ),
                ),
                (
                    "collect_config_ids",
                    bkmonitor.utils.db.fields.JsonField(
                        verbose_name="\u63d2\u4ef6\u91c7\u96c6\u5173\u8054\u91c7\u96c6\u914d\u7f6eid"
                    ),
                ),
                ("result_table_label", models.CharField(max_length=128, verbose_name="\u8868\u6807\u7b7e")),
                ("data_source_label", models.CharField(max_length=128, verbose_name="\u6570\u636e\u6e90\u6807\u7b7e")),
                (
                    "data_type_label",
                    models.CharField(max_length=128, verbose_name="\u6570\u636e\u7c7b\u578b\u6807\u7b7e"),
                ),
                ("data_target", models.CharField(max_length=128, verbose_name="\u6570\u636e\u76ee\u6807\u6807\u7b7e")),
                (
                    "default_dimensions",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u9ed8\u8ba4\u7ef4\u5ea6\u5217\u8868"),
                ),
                (
                    "default_condition",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u9ed8\u8ba4\u76d1\u63a7\u6761\u4ef6"),
                ),
            ],
        ),
    ]
