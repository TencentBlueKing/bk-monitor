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
        ("monitor", "0066_merge"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scriptcollectorconfig",
            name="script_ext",
            field=models.CharField(
                default=b"shell",
                max_length=20,
                verbose_name="\u811a\u672c\u683c\u5f0f",
                choices=[
                    (b"shell", b"shell"),
                    (b"bat", b"bat"),
                    (b"python", b"python"),
                    (b"perl", b"perl"),
                    (b"powershell", b"powershell"),
                    (b"vbs", b"vbs"),
                    (b"custom", "\u81ea\u5b9a\u4e49"),
                ],
            ),
        ),
    ]
