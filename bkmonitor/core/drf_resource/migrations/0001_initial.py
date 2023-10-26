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

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ResourceData",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("name", models.CharField(max_length=128, verbose_name="\u540d\u79f0", db_index=True)),
                ("start_time", models.DateTimeField(verbose_name="\u5f00\u59cb\u65f6\u95f4")),
                ("end_time", models.DateTimeField(verbose_name="\u7ed3\u675f\u4e8b\u4ef6")),
                ("request_data", models.TextField(verbose_name="\u8bf7\u6c42\u53c2\u6570")),
                ("response_data", models.TextField(verbose_name="\u54cd\u5e94\u53c2\u6570")),
            ],
            options={
                "db_table": "resource_data",
            },
        ),
    ]
