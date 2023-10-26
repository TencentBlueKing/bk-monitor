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
        ("metadata", "0015_auto_20190706_1505"),
    ]

    operations = [
        migrations.CreateModel(
            name="InfluxDBClusterInfo",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("host_name", models.CharField(max_length=128, verbose_name="\u4e3b\u673a\u540d")),
                ("cluster_name", models.CharField(max_length=128, verbose_name="\u5f52\u5c5e\u96c6\u7fa4\u540d")),
            ],
        ),
        migrations.CreateModel(
            name="InfluxDBHostInfo",
            fields=[
                (
                    "host_name",
                    models.CharField(
                        max_length=128, serialize=False, verbose_name="\u4e3b\u673a\u540d", primary_key=True
                    ),
                ),
                ("domain_name", models.CharField(max_length=128, verbose_name="\u96c6\u7fa4\u57df\u540d")),
                ("port", models.IntegerField(verbose_name="\u7aef\u53e3")),
                ("username", models.CharField(default="", max_length=64, verbose_name="\u7528\u6237\u540d")),
                ("password", models.CharField(default="", max_length=128, verbose_name="\u5bc6\u7801")),
                (
                    "description",
                    models.CharField(
                        default="", max_length=256, verbose_name="\u96c6\u7fa4\u5907\u6ce8\u8bf4\u660e\u4fe1\u606f"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="password",
            field=models.CharField(default="", max_length=128, verbose_name="\u5bc6\u7801"),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="username",
            field=models.CharField(default="", max_length=64, verbose_name="\u7528\u6237\u540d"),
        ),
        migrations.AddField(
            model_name="influxdbstorage",
            name="proxy_cluster_name",
            field=models.CharField(
                default="default", max_length=128, verbose_name="\u5b9e\u9645\u5b58\u50a8\u96c6\u7fa4\u540d\u5b57"
            ),
        ),
    ]
