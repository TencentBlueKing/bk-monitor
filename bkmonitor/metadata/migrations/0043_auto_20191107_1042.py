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
        ("metadata", "0042_add_bk_target_ip_field"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="clusterinfo",
            name="custom_label",
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="custom_option",
            field=models.TextField(default="", verbose_name="\u81ea\u5b9a\u4e49\u6807\u7b7e"),
        ),
        migrations.AlterField(
            model_name="resulttablefieldoption",
            name="name",
            field=models.CharField(
                max_length=128,
                verbose_name="option\u540d\u79f0",
                choices=[
                    ("es_type", "es_type"),
                    ("es_include_in_all", "es_include_in_all"),
                    ("es_format", "es_format"),
                    ("es_doc_values", "es_doc_values"),
                    ("es_index", "es_index"),
                    ("influxdb_disabled", "influxdb_disabled"),
                ],
            ),
        ),
    ]
