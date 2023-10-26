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


import json

from django.db import migrations

fix_config = """
UPDATE monitor_uptimechecktask SET config = TRIM(BOTH '"' FROM config) WHERE is_deleted = FALSE;
"""


def fix_location(apps, schema_editor):
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")
    UptimeCheckNode = apps.get_model("monitor", "UptimeCheckNode")

    for task in UptimeCheckTask.objects.filter(is_deleted=False):
        task.location = json.loads(task.location)
        task.save()

    for node in UptimeCheckNode.objects.filter(is_deleted=False):
        node.location = json.loads(node.location)
        node.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0074_auto_20190527_1537"),
    ]

    operations = [migrations.RunSQL(fix_config), migrations.RunPython(fix_location)]
