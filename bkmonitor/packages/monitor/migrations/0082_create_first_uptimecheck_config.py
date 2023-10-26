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


from django.db import migrations


def add_config_placeholder(apps, schema_editor):
    """
    新增 ID 为 10000 的拨测配置，扩大自增ID起始值，防止与老配置冲突
    """
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")
    UptimeCheckGroup = apps.get_model("monitor", "UptimeCheckGroup")
    UptimeCheckNode = apps.get_model("monitor", "UptimeCheckNode")

    UptimeCheckTask.objects.create(
        id=10000,
        bk_biz_id=-1,
        name="__placeholder__",
        protocol="HTTP",
        is_deleted=True,
    )
    UptimeCheckGroup.objects.create(
        id=10000,
        name="__placeholder__",
        is_deleted=True,
    )
    UptimeCheckNode.objects.create(
        id=10000,
        name="__placeholder__",
        bk_biz_id=-1,
        is_common=False,
        ip="0.0.0.0",
        plat_id=0,
        is_deleted=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0081_delete_shield"),
    ]

    operations = [migrations.RunPython(add_config_placeholder)]
