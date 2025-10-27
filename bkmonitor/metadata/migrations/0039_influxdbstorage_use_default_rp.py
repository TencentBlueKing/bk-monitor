# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0038_auto_20191009_1543"),
    ]

    operations = [
        migrations.AddField(
            model_name="influxdbstorage",
            name="use_default_rp",
            field=models.BooleanField(default=True, verbose_name="\u662f\u5426\u4f7f\u7528\u9ed8\u8ba4RP\u914d\u7f6e"),
        ),
    ]
