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

from django.db import migrations


def add_default_trap_pligin(apps, schema_editor):
    """追加内置的SNMP trap虚拟插件信息"""

    # 获取APP models
    plugin = apps.get_model("monitor_web", "CollectorPluginMeta")

    plugin.objects.create(plugin_id="snmp_v1", plugin_type="SNMP_Trap", is_internal=True)
    plugin.objects.create(plugin_id="snmp_v2c", plugin_type="SNMP_Trap", is_internal=True)
    plugin.objects.create(plugin_id="snmp_v3", plugin_type="SNMP_Trap", is_internal=True)


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0040_auto_20201214_2008"),
    ]

    operations = [
        migrations.RunPython(add_default_trap_pligin),
    ]
