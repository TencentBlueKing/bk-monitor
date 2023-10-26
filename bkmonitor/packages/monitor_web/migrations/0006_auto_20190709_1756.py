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

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0005_collectconfigmeta_cache_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="deploymentconfigversion",
            name="task_ids",
            field=bkmonitor.utils.db.fields.JsonField(default=None, verbose_name="\u4efb\u52a1id\u5217\u8868"),
        ),
        migrations.AlterField(
            model_name="collectconfigmeta",
            name="status",
            field=models.CharField(
                max_length=32,
                verbose_name="\u91c7\u96c6\u72b6\u6001",
                choices=[
                    (b"STARTING", "\u542f\u7528\u4e2d"),
                    (b"STARTED", "\u5df2\u542f\u7528"),
                    (b"STOPPING", "\u505c\u7528\u4e2d"),
                    (b"STOPPED", "\u5df2\u505c\u7528"),
                    (b"DEPLOYING", "\u6267\u884c\u4e2d"),
                ],
            ),
        ),
    ]
