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


def add_fieldlist(ResultTableField, table_id, fieldlist):
    for field in fieldlist:
        defaults = {
            "field_type": field["field_type"],
            "description": field["description"],
            "unit": field["unit"],
            "tag": field["tag"],
            "is_config_by_user": True,
            "creator": "system",
            "last_modify_user": "system",
        }
        ResultTableField.objects.update_or_create(table_id=table_id, field_name=field["field_name"], defaults=defaults)


def add_basereport_metrics(apps, *args, **kwargs):
    # 获取APP models
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    cpu_summary_detail_metrics = [
        {
            "field_name": "nice",
            "field_type": "double",
            "description": "低优先级程序在用户态执行的CPU占比",
            "tag": "metric",
            "unit": "percentunit",
        },
        {
            "field_name": "interrupt",
            "field_type": "double",
            "description": "硬件中断数的CPU占比",
            "tag": "metric",
            "unit": "percentunit",
        },
        {
            "field_name": "softirq",
            "field_type": "double",
            "description": "软件中断数的CPU占比",
            "tag": "metric",
            "unit": "percentunit",
        },
        {
            "field_name": "guest",
            "field_type": "double",
            "description": "内核在虚拟机上运行的CPU占比",
            "tag": "metric",
            "unit": "percentunit",
        },
    ]

    env_metrics = [
        {"field_name": "maxfiles", "field_type": "int", "description": "最大文件描述符", "tag": "metric", "unit": "short"},
        {"field_name": "login_user", "field_type": "int", "description": "登录的用户数", "tag": "metric", "unit": "short"},
        {
            "field_name": "proc_running_current",
            "field_type": "int",
            "description": "正在运行的进程总个数",
            "tag": "metric",
            "unit": "short",
        },
        {
            "field_name": "procs_blocked_current",
            "field_type": "int",
            "description": "处于等待I/O完成的进程个数",
            "tag": "metric",
            "unit": "short",
        },
        {
            "field_name": "procs_processes_total",
            "field_type": "int",
            "description": "系统启动后所创建过的进程数量",
            "tag": "metric",
            "unit": "short",
        },
        {
            "field_name": "procs_ctxt_total",
            "field_type": "int",
            "description": "系统上下文切换次数",
            "tag": "metric",
            "unit": "short",
        },
    ]

    load_metrics = [
        {
            "field_name": "per_cpu_load",
            "field_type": "float",
            "description": "单核CPU的load",
            "tag": "metric",
            "unit": "none",
        },
    ]

    net_metrics = [
        {"field_name": "errors", "field_type": "int", "description": "网卡错误包", "tag": "metric", "unit": "short"},
        {"field_name": "dropped", "field_type": "int", "description": "网卡丢弃包", "tag": "metric", "unit": "short"},
        {"field_name": "overruns", "field_type": "int", "description": "网卡物理层丢弃", "tag": "metric", "unit": "short"},
        {
            "field_name": "carrier",
            "field_type": "int",
            "description": "设备驱动程序检测到的载波丢失数",
            "tag": "metric",
            "unit": "short",
        },
        {"field_name": "collisions", "field_type": "int", "description": "网卡冲突包", "tag": "metric", "unit": "short"},
    ]

    swap_metrics = [
        {"field_name": "swap_in", "field_type": "float", "description": "swap从硬盘到内存", "tag": "metric", "unit": "KBs"},
        {"field_name": "swap_out", "field_type": "float", "description": "swap从内存到硬盘", "tag": "metric", "unit": "KBs"},
    ]

    add_fieldlist(ResultTableField, "system.cpu_summary", cpu_summary_detail_metrics)
    add_fieldlist(ResultTableField, "system.cpu_detail", cpu_summary_detail_metrics)
    add_fieldlist(ResultTableField, "system.env", env_metrics)
    add_fieldlist(ResultTableField, "system.load", load_metrics)
    add_fieldlist(ResultTableField, "system.net", net_metrics)
    add_fieldlist(ResultTableField, "system.swap", swap_metrics)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0067_datasource_consul_prefix"),
    ]

    operations = [migrations.RunPython(add_basereport_metrics)]
