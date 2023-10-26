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
        ("monitor", "0078_remove_uptimecheckgroup_default_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="rolepermission",
            name="create_time",
            field=models.DateTimeField(
                default=datetime.datetime(2019, 11, 18, 12, 52, 10, 841898, tzinfo=utc),
                verbose_name="\u521b\u5efa\u65f6\u95f4",
                auto_now_add=True,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rolepermission",
            name="create_user",
            field=models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
        ),
        migrations.AddField(
            model_name="rolepermission",
            name="is_deleted",
            field=models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664"),
        ),
        migrations.AddField(
            model_name="rolepermission",
            name="update_time",
            field=models.DateTimeField(
                default=datetime.datetime(2019, 11, 18, 12, 52, 19, 135053, tzinfo=utc),
                verbose_name="\u4fee\u6539\u65f6\u95f4",
                auto_now=True,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rolepermission",
            name="update_user",
            field=models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True),
        ),
    ]
