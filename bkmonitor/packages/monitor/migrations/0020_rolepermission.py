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
        ("monitor", "0019_repair_host_property"),
    ]

    operations = [
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("role", models.CharField(max_length=128, verbose_name="\u89d2\u8272")),
                ("permission", models.CharField(default=b"", max_length=32, verbose_name="\u6743\u9650")),
            ],
        ),
    ]
