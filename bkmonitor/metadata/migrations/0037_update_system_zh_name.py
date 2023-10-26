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

logger = logging.getLogger("metadata")

models = {"ResultTable": None}

rt_config = {
    "system.env": "系统环境",
    "system.inode": "inode",
    "system.proc_port": "进程端口",
    "system.cpu_detail": "处理器",
    "system.swap": "交换分区",
    "system.net": "网络",
    "system.load": "负载",
    "system.disk": "磁盘",
    "system.io": "输入输出",
    "system.proc": "进程",
    "system.mem": "内存",
    "system.netstat": "连接状态",
    "system.cpu_summary": "处理器",
}


def update_system_table_zh(apps, *args, **kwargs):
    """更新system下的结果表中文名"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTable = models["ResultTable"]
    for table_id in rt_config:

        try:
            rt = ResultTable.objects.get(table_id=table_id)
            rt.table_name_zh = rt_config[table_id]
            rt.save()
        except ResultTable.DoesNotExist:
            # 由于各个环境可能有不同的调整，所以需要兼容当RT丢失的情况
            continue


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0036_init_es_storage_info"),
    ]

    operations = [migrations.RunPython(update_system_table_zh)]
