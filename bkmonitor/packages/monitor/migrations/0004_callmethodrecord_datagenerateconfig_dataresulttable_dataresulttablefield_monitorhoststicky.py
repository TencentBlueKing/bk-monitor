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
        ("monitor", "0003_auto_20161212_1106"),
    ]

    operations = [
        migrations.CreateModel(
            name="CallMethodRecord",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("action", models.CharField(max_length=512, verbose_name="\u8c03\u7528\u63a5\u53e3\u540d")),
                ("url", models.CharField(max_length=256, verbose_name="url")),
                ("param", models.TextField(verbose_name="\u53c2\u6570")),
                ("result", models.TextField(verbose_name="\u8fd4\u56de\u7ed3\u679c")),
                ("operate_time", models.DateTimeField(auto_now_add=True, verbose_name="\u64cd\u4f5c\u65f6\u95f4")),
            ],
        ),
        migrations.CreateModel(
            name="DataGenerateConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("collector_id", models.IntegerField(verbose_name="\u5173\u8054\u6570\u636e\u63a5\u5165\u914d\u7f6e")),
                ("template_id", models.IntegerField(verbose_name="\u6a21\u7248ID")),
                ("template_args", models.TextField(verbose_name="\u6a21\u7248\u53c2\u6570")),
                ("project_id", models.IntegerField(verbose_name="\u5b50\u9879\u76eeID")),
                ("job_id", models.CharField(max_length=32, verbose_name="\u5bf9\u5e94\u7684\u4f5c\u4e1aID")),
                ("bksql", models.TextField(default=b"", verbose_name="bksql\u63cf\u8ff0")),
                (
                    "status",
                    models.CharField(
                        default=b"starting",
                        max_length=16,
                        verbose_name="\u4f5c\u4e1a\u72b6\u6001",
                        choices=[
                            (b"starting", "\u542f\u52a8\u4e2d"),
                            (b"running", "\u6b63\u5728\u8fd0\u884c"),
                            (b"stopping", "\u505c\u6b62\u4e2d"),
                            (b"not running", "\u672a\u542f\u52a8"),
                        ],
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DataResultTable",
            fields=[
                (
                    "result_table_id",
                    models.CharField(max_length=64, serialize=False, verbose_name="result table id", primary_key=True),
                ),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("table_name", models.TextField(verbose_name="\u8868\u540d\u79f0")),
                ("generate_config_id", models.IntegerField(verbose_name="\u5173\u8054\u7684data etl config id")),
                ("count_freq", models.IntegerField(verbose_name="\u7edf\u8ba1\u9891\u7387")),
                ("parents", models.CharField(max_length=128, null=True, verbose_name="\u7236\u8868id list")),
            ],
        ),
        migrations.CreateModel(
            name="DataResultTableField",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("result_table_id", models.CharField(max_length=64, verbose_name="result table id")),
                ("field", models.CharField(max_length=32, verbose_name="field name")),
                (
                    "desc",
                    models.CharField(max_length=32, null=True, verbose_name="\u4e2d\u6587\u540d\u79f0", blank=True),
                ),
                ("field_type", models.CharField(max_length=16, verbose_name="field type")),
                ("processor", models.CharField(max_length=32, null=True, verbose_name="processor")),
                ("processor_args", models.TextField(null=True)),
                (
                    "is_dimension",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u7ef4\u5ea6\u5b57\u6bb5"),
                ),
                ("origins", models.CharField(max_length=64, null=True, verbose_name="origins list")),
                ("field_index", models.IntegerField(verbose_name="index")),
                ("value_dict", models.TextField(null=True, verbose_name="\u503c\u6620\u5c04(JSON)", blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="MonitorHostSticky",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("plat_id", models.IntegerField(null=True, verbose_name="\u5e73\u53f0ID")),
                ("host", models.CharField(max_length=128, null=True, verbose_name="\u4e3b\u673aIP", db_index=True)),
                ("cc_biz_id", models.CharField(max_length=30, verbose_name="cc\u4e1a\u52a1id")),
            ],
        ),
    ]
