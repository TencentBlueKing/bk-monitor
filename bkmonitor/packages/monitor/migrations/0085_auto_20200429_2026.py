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
        ("monitor", "0084_uptimechecktaskcollectorlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="uptimechecktaskcollectorlog",
            name="is_deleted",
            field=models.BooleanField(default=False, verbose_name="\u5df2\u5220\u9664"),
        ),
        migrations.AlterField(
            model_name="uptimechecktaskcollectorlog",
            name="task_id",
            field=models.IntegerField(verbose_name="\u62e8\u6d4b\u4efb\u52a1ID"),
        ),
    ]
