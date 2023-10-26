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
        ("metadata", "0005_clean_timestamp_field"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resulttablefield",
            name="description",
            field=models.TextField(verbose_name="\u5b57\u6bb5\u63cf\u8ff0"),
        ),
        migrations.AlterField(
            model_name="resulttablefield",
            name="field_name",
            field=models.CharField(max_length=64, verbose_name="\u5b57\u6bb5\u540d"),
        ),
    ]
