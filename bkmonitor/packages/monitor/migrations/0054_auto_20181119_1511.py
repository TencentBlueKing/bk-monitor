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
        ("monitor", "0053_merge"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scenariomenu",
            name="system_menu",
            field=models.CharField(
                default=b"",
                max_length=32,
                verbose_name="\u7cfb\u7edf\u83dc\u5355\u680f",
                blank=True,
                choices=[
                    ("", "\u7528\u6237\u81ea\u5b9a\u4e49"),
                    ("favorite", "\u5173\u6ce8"),
                    ("default", "\u9ed8\u8ba4\u5206\u7ec4"),
                    ("online", "\u5728\u7ebf"),
                    ("login", "\u767b\u5f55"),
                    ("register", "\u6ce8\u518c"),
                ],
            ),
        ),
    ]
