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
        ("metadata", "0045_auto_20191123_1148"),
    ]

    operations = [
        migrations.AddField(
            model_name="resulttable",
            name="is_enable",
            field=models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528"),
        ),
        migrations.AlterField(
            model_name="datasourceoption",
            name="value_type",
            field=models.CharField(
                max_length=64,
                verbose_name="option\u5bf9\u5e94\u7c7b\u578b",
                choices=[("bool", "bool"), ("string", "string"), ("list", "list"), ("int", "int")],
            ),
        ),
        migrations.AlterField(
            model_name="resulttablefieldoption",
            name="value_type",
            field=models.CharField(
                max_length=64,
                verbose_name="option\u5bf9\u5e94\u7c7b\u578b",
                choices=[("bool", "bool"), ("string", "string"), ("list", "list"), ("int", "int")],
            ),
        ),
        migrations.AlterField(
            model_name="resulttableoption",
            name="value_type",
            field=models.CharField(
                max_length=64,
                verbose_name="option\u5bf9\u5e94\u7c7b\u578b",
                choices=[("bool", "bool"), ("string", "string"), ("list", "list"), ("int", "int")],
            ),
        ),
    ]
