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
        ("monitor", "0002_auto_20161123_1717"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datasource",
            name="status",
            field=models.CharField(
                default=b"normal",
                max_length=20,
                verbose_name="\u6570\u636e\u6e90\u72b6\u6001",
                choices=[
                    (b"normal", "\u6b63\u5e38"),
                    (b"stopped", "\u505c\u7528"),
                    (b"process", "\u63a5\u5165\u4e2d"),
                    (b"failed", "\u63a5\u5165\u5931\u8d25"),
                ],
            ),
        ),
    ]
