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

from bkmonitor.utils.text import camel_to_underscore

changed_metric_names = ["speedRecv", "speedSent", "speedPacketsSent", "speedPacketsRecv"]

to_be_update_unit_metric = [
    ("bk_monitor.system.net.speed_recv", 1024, "k", "Bps"),
    ("bk_monitor.system.net.speed_sent", 1024, "k", "Bps"),
    ("bk_monitor.system.mem.free", 1048576, "M", "decbytes"),
    ("bk_monitor.system.swap.used", 1048576, "M", "decbytes"),
    ("bk_monitor.system.mem.psc_used", 1048576, "M", "decbytes"),
    ("bk_monitor.system.mem.used", 1048576, "M", "decbytes"),
    ("bk_monitor.system.proc.mem_res", 1048576, "M", "decbytes"),
    ("bk_monitor.system.proc.mem_virt", 1048576, "M", "decbytes"),
    ("bk_monitor.system.io.util", 0.01, "%", "percentunit"),
    ("bk_monitor.system.proc.cpu_usage_pct", 0.01, "%", "percentunit"),
    ("bk_monitor.system.proc.mem_usage_pct", 0.01, "%", "percentunit"),
]


def fix_metrics(apps, *args, **kwargs):
    """
    修复2.5版本升级上来遗留的指标名（2.5对应指标名已变更需要修复）
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    AlgorithmModel = apps.get_model("bkmonitor", "AlgorithmModel")
    # 1. 找到原2.5留下来的指标名对应的指标
    for metric_name in changed_metric_names:

        for query_conf in QueryConfigModel.objects.filter(metric_id=f"bk_monitor.system.net.{metric_name}"):
            target_metric_name = camel_to_underscore(metric_name)
            print(
                f"strategy{query_conf.strategy_id}.query_config{query_conf.id}:"
                f"{query_conf.config['metric_field']} -> {target_metric_name}"
            )
            query_conf.config["metric_field"] = target_metric_name
            query_conf.metric_id = f"bk_monitor.system.net.{target_metric_name}"

            query_conf.save()
    # 2. 更新指标对应基础单位
    for unit_info in to_be_update_unit_metric:
        metric_name, conversion, prefix, new_unit = unit_info
        s_ids = []
        for query_conf in QueryConfigModel.objects.filter(metric_id=metric_name):
            s_ids.append(query_conf.strategy_id)
            if query_conf.config["unit"] == new_unit:
                continue

            print(
                f"strategy{query_conf.strategy_id}.query_config{query_conf.id}.{metric_name}.config.unit:"
                f"{query_conf.config['unit']} -> {new_unit}"
            )
            query_conf.config["unit"] = new_unit
            query_conf.save()
        # 3. 指标配置的检测算法，保留原意义(KB/s -> kBps)
        for algorithm in AlgorithmModel.objects.filter(strategy_id__in=s_ids):
            if algorithm.unit_prefix:
                continue
            print(
                f"strategy{algorithm.strategy_id}.query_config{algorithm.id}.{metric_name}.unit_prefix:"
                f"{algorithm.unit_prefix} -> {prefix}"
            )
            algorithm.unit_prefix = prefix
            algorithm.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0035_fix_duplicate_detects_20210613"),
    ]

    operations = [
        migrations.RunPython(fix_metrics),
    ]
