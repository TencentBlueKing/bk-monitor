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
        ("monitor", "0042_auto_20180709_1756"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="alarmstrategy",
            name="condition_config_id",
        ),
        migrations.RemoveField(
            model_name="alarmstrategy",
            name="strategy_id",
        ),
        migrations.RemoveField(
            model_name="alarmstrategy",
            name="strategy_option",
        ),
        migrations.AddField(
            model_name="alarmstrategy",
            name="detect_algorithm",
            field=bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u68c0\u6d4b\u7b97\u6cd5\u914d\u7f6e"),
        ),
        migrations.AlterField(
            model_name="shellcollectorconfig",
            name="status",
            field=models.CharField(
                default=b"new draft",
                max_length=20,
                verbose_name="\u5f53\u524d\u72b6\u6001",
                choices=[
                    (b"new draft", "\u65b0\u5efa\u672a\u4fdd\u5b58"),
                    (b"edit draft", "\u7f16\u8f91\u672a\u4fdd\u5b58"),
                    (b"saved", "\u5df2\u4fdd\u5b58"),
                    (b"delete failed", "\u5220\u9664\u5931\u8d25"),
                ],
            ),
        ),
    ]
