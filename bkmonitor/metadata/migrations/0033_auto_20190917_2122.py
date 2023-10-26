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
        ("metadata", "0032_init_influxdb_backend_info"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="custom_label",
            field=models.CharField(
                default=None, max_length=256, null=True, verbose_name="\u81ea\u5b9a\u4e49\u6807\u7b7e\u4fe1\u606f"
            ),
        ),
        migrations.AlterField(
            model_name="datasourceoption",
            name="name",
            field=models.CharField(
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
                    ("group_info_alias", "group_info_alias"),
                ],
            ),
        ),
    ]
