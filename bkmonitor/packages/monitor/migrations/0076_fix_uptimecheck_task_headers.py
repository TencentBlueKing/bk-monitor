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


def fix_headers(apps, schema_editor):
    """
    修复旧拨测HTTP任务headers分别被前端和后台json.dumps导致单次json.loads无法直接读出对象的问题
    """
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")

    for task in UptimeCheckTask.objects.filter(is_deleted=False, protocol="HTTP"):
        try:
            headers = json.loads(task.config["headers"])
        except TypeError:
            continue
        task.config["headers"] = headers
        task.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0075_fix_uptime_check_config_and_location"),
    ]

    operations = [migrations.RunPython(fix_headers)]
