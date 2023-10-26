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
        ("monitor", "0063_auto_20190225_2006"),
    ]

    operations = [
        migrations.AlterField(
            model_name="uptimechecknode",
            name="carrieroperator",
            field=models.CharField(
                default=b"", max_length=50, null=True, verbose_name="\u5916\u7f51\u8fd0\u8425\u5546", blank=True
            ),
        ),
        migrations.AlterField(
            model_name="uptimechecknode",
            name="location",
            field=bkmonitor.utils.db.fields.JsonField(default=b"{}", verbose_name="\u5730\u533a"),
        ),
        migrations.AlterField(
            model_name="uptimechecktask",
            name="location",
            field=bkmonitor.utils.db.fields.JsonField(default=b"{}", verbose_name="\u5730\u533a"),
        ),
    ]
