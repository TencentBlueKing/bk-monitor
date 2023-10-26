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


def fix_metric_id(apps, *args, **kwargs):
    """
    修复异常的拨测策略
    1. 处理不服未转换为阈值的部分节点数算法
    2. 响应码和响应内容策略不能使用node_id作为指标，因为influxdb不支持聚合维度，哪怕是COUNT
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    AlgorithmModel = apps.get_model("bkmonitor", "AlgorithmModel")

    os_restart_strategy_ids = AlgorithmModel.objects.filter(type="OsRestart").values("strategy_id").distinct()
    proc_port_strategy_ids = AlgorithmModel.objects.filter(type="ProcPort").values("strategy_id").distinct()
    ping_strategy_ids = AlgorithmModel.objects.filter(type="PingUnreachable").values("strategy_id").distinct()

    QueryConfigModel.objects.filter(strategy_id__in=os_restart_strategy_ids).update(metric_id="bk_monitor.os_restart")

    QueryConfigModel.objects.filter(strategy_id__in=proc_port_strategy_ids).update(metric_id="bk_monitor.proc_port")

    QueryConfigModel.objects.filter(strategy_id__in=ping_strategy_ids).update(metric_id="bk_monitor.ping-gse")


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0039_auto_20210708_1117"),
    ]

    operations = [
        migrations.RunPython(fix_metric_id),
    ]
