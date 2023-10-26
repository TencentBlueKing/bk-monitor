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


import datetime

from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0043_auto_20191107_1042"),
    ]

    operations = [
        migrations.AddField(
            model_name="clusterinfo",
            name="create_time",
            field=models.DateTimeField(
                default=datetime.datetime(2019, 11, 19, 9, 52, 8, 752323, tzinfo=utc),
                verbose_name="\u521b\u5efa\u65f6\u95f4",
                auto_now_add=True,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="creator",
            field=models.CharField(default="system", max_length=255, verbose_name="\u521b\u5efa\u8005"),
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="last_modify_time",
            field=models.DateTimeField(
                default=datetime.datetime(2019, 11, 19, 9, 52, 15, 300044, tzinfo=utc),
                verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4",
                auto_now=True,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="clusterinfo",
            name="last_modify_user",
            field=models.CharField(default="system", max_length=32, verbose_name="\u6700\u540e\u66f4\u65b0\u8005"),
        ),
    ]
