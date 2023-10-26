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


def move_target(apps, schema_editor):
    """
    将Strategy中的目标迁移Item
    """
    Strategy = apps.get_model("bkmonitor", "Strategy")
    Item = apps.get_model("bkmonitor", "Item")

    strategies = Strategy.objects.all()
    for strategy in strategies:
        if strategy.target:
            Item.objects.filter(strategy_id=strategy.id).update(target=strategy.target)

    # TODO: 迁移event中的origin_config


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0004_noticegroup_webhook_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="target",
            field=bkmonitor.utils.db.fields.JsonField(default=[[]], verbose_name="\u76d1\u63a7\u76ee\u6807"),
        ),
        migrations.RunPython(move_target),
    ]
