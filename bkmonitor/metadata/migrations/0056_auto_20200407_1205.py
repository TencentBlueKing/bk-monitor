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
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0055_merge"),
    ]

    operations = [
        migrations.AlterField(
            model_name="influxdbhostinfo",
            name="password",
            field=SymmetricTextField(default="", verbose_name="\u5bc6\u7801", blank=True),
        ),
        migrations.AlterField(
            model_name="influxdbhostinfo",
            name="username",
            field=models.CharField(default="", max_length=64, verbose_name="\u7528\u6237\u540d", blank=True),
        ),
    ]
