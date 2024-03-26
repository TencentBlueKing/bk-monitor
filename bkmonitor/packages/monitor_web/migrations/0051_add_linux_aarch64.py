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


import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger("monitor_web")

operate_system = [
    {"os_type_id": 4, "os_type": "linux_aarch64"},
]


def add_initial_obj(apps, schema_editor):
    OperatorSystem = apps.get_model("monitor_web", "OperatorSystem")
    GlobalConfig = apps.get_model("bkmonitor", "GlobalConfig")

    for obj in operate_system:
        OperatorSystem.objects.create(**obj)

    config = GlobalConfig.objects.filter(key="OS_GLOBAL_SWITCH").first()
    if config and "linux_aarch64" not in config.value:
        config.value.append("linux_aarch64")
        config.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor_web", "0050_merge_20210428_1352"),
        ("bkmonitor", "0014_auto_20200616_1143"),
    ]

    operations = [migrations.RunPython(add_initial_obj)]
