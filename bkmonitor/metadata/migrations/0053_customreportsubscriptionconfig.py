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

from bkmonitor.utils.db.fields import JsonField


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0052_auto_20200315_1719"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomReportSubscriptionConfig",
            fields=[
                ("bk_biz_id", models.IntegerField(serialize=False, verbose_name="\u4e1a\u52a1ID", primary_key=True)),
                (
                    "subscription_id",
                    models.IntegerField(default=0, verbose_name="\u8282\u70b9\u7ba1\u7406\u8ba2\u9605ID"),
                ),
                ("config", JsonField(verbose_name="\u8ba2\u9605\u914d\u7f6e")),
            ],
            options={
                "verbose_name": "\u81ea\u5b9a\u4e49\u4e0a\u62a5\u8ba2\u9605\u914d\u7f6e",
                "verbose_name_plural": "\u81ea\u5b9a\u4e49\u4e0a\u62a5\u8ba2\u9605\u914d\u7f6e",
            },
        ),
    ]
