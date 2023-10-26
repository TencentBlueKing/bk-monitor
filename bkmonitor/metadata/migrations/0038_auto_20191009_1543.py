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
        ("metadata", "0037_update_system_zh_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="esstorage",
            name="retention",
            field=models.IntegerField(default=30, verbose_name="index\u4fdd\u5b58\u65f6\u95f4"),
        ),
        migrations.AlterField(
            model_name="esstorage",
            name="date_format",
            field=models.CharField(
                default="%Y%m%d%H", max_length=64, verbose_name="\u65e5\u671f\u683c\u5f0f\u5316\u914d\u7f6e"
            ),
        ),
    ]
