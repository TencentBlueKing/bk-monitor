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
        ("monitor", "0038_uptimechecktask_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="uptimechecknode",
            name="carrieroperator",
            field=models.CharField(default="", max_length=50, verbose_name="\u5916\u7f51\u8fd0\u8425\u5546"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="uptimechecknode",
            name="location",
            field=bkmonitor.utils.db.fields.JsonField(default="", verbose_name="\u5730\u533a"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="uptimechecktask",
            name="status",
            field=models.CharField(
                default=b"new draft",
                max_length=20,
                verbose_name="\u5f53\u524d\u72b6\u6001",
                choices=[
                    (b"new draft", "\u672a\u4fdd\u5b58"),
                    (b"running", "\u8fd0\u884c\u4e2d"),
                    (b"stoped", "\u672a\u6267\u884c"),
                    (b"starting", "\u542f\u52a8\u4e2d"),
                    (b"stoping", "\u505c\u6b62\u4e2d"),
                    (b"start_failed", "\u542f\u52a8\u5931\u8d25"),
                    (b"stop_failed", "\u505c\u6b62\u5931\u8d25"),
                ],
            ),
        ),
    ]
