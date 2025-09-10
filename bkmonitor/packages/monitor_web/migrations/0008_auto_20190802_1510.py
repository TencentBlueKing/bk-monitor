# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0007_auto_20190801_1545"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collectconfigmeta",
            name="last_operation",
            field=models.CharField(
                max_length=32,
                verbose_name="\u6700\u8fd1\u4e00\u6b21\u64cd\u4f5c",
                choices=[
                    ("UPGRADE", "\u5347\u7ea7"),
                    ("ROLLBACK", "\u56de\u6eda"),
                    ("START", "\u542f\u7528"),
                    ("STOP", "\u505c\u7528"),
                    ("CREATE", "\u521b\u5efa"),
                    ("EDIT", "\u7f16\u8f91"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="collectconfigmeta",
            name="operation_result",
            field=models.CharField(
                max_length=32,
                verbose_name="\u6700\u8fd1\u4e00\u6b21\u4efb\u52a1\u7ed3\u679c",
                choices=[
                    ("SUCCESS", "\u5168\u90e8\u6210\u529f"),
                    ("WARNING", "\u90e8\u5206\u6210\u529f"),
                    ("FAILED", "\u5168\u90e8\u5931\u8d25"),
                    ("DEPLOYING", "\u4e0b\u53d1\u4e2d"),
                    ("COMPLETED", "\u5df2\u5b8c\u6210"),
                ],
            ),
        ),
    ]
