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

from monitor.models import HostProperty

host_property_data = [
    {
        "property": "InnerIP",
        "property_display": "主机名/IP",
        "required": True,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "status",
        "property_display": "采集状态",
        "required": True,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "alarm",
        "property_display": "告警事件（今日）",
        "required": False,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "cpu_usage",
        "property_display": "CPU使用率",
        "required": False,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "io_util",
        "property_display": "磁盘IO使用率",
        "required": False,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "cpu_load",
        "property_display": "CPU5分钟负载",
        "required": False,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "component",
        "property_display": "组件服务",
        "required": True,
        "selected": True,
        "is_deleted": False,
    },
    {
        "property": "SetName",
        "property_display": "集群名",
        "required": False,
        "selected": False,
        "is_deleted": False,
    },
    {
        "property": "ModuleName",
        "property_display": "模块名",
        "required": False,
        "selected": False,
        "is_deleted": False,
    },
]


def init_host_property_data(*args):
    for item in host_property_data:
        if not HostProperty.objects.filter(property=item["property"], is_deleted=False).exists():
            h = HostProperty(**item)
            h.save()


new_prop = {
    "property": "HostName",
    "property_display": "主机名",
    "required": False,
    "selected": False,
    "is_deleted": False,
    "index": 1.5,
}


def run_repair(*args):
    if not HostProperty.objects.filter(property="HostName", is_deleted=False).exists():
        HostProperty(**new_prop).save()
    HostProperty.objects.filter(property="InnerIP").update(property_display="IP")


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0031_auto_20171030_2154"),
    ]

    operations = [migrations.RunPython(init_host_property_data), migrations.RunPython(run_repair)]
