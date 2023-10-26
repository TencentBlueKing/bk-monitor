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
        ("monitor", "0037_uptimechecknode_uptimechecktask"),
    ]

    operations = [
        migrations.AddField(
            model_name="uptimechecktask",
            name="status",
            field=models.CharField(
                default=b"new draft",
                max_length=20,
                verbose_name="\u5f53\u524d\u72b6\u6001",
                choices=[(b"new draft", "\u672a\u4fdd\u5b58"), (b"saved", "\u5df2\u4fdd\u5b58")],
            ),
        ),
    ]
