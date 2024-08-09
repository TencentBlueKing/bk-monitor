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
from django.db.models import Q

# 废弃的插件
DISCARD_PLUGINS = [
    "basereport",
    "processbeat",
    "exceptionbeat",
    "bkmonitorbeat",
    "bkmonitorproxy",
    "bkunifylogbeat",
    "unifyTlogc",
    "unifytlogc",
    "gseAgent",
    "bk-collector",
    "gse_agent",
    "dbcheck",
    "dbbeat",
    "httpbeat",
    "bkmetricbeat",
    "logbeat",
    "uptimecheckbeat",
    "bkfilebeat",
]


def update_strategy_config(apps, schema_editor):
    """
    更新策略配置
    """
    strategy_model = apps.get_model("bkmonitor", "StrategyModel")
    query_config_model = apps.get_model("bkmonitor", "QueryConfigModel")

    strategy_ids = strategy_model.objects.filter(
        Q(name="Gse进程托管事件告警(业务侧)") | Q(name="GSE process hosting event alarm (business side)")
    ).values_list("id", flat=True)
    if not strategy_ids:
        return
    query_configs = query_config_model.objects.filter(strategy_id__in=strategy_ids)
    if not query_configs:
        return

    updated_query_configs = []
    for qc in query_configs:
        try:
            config = qc.config
            agg_conditions = config.get("agg_condition", [])
            for agg_condition in agg_conditions:
                if agg_condition["key"] == "process_name" and agg_condition["method"] == "neq":
                    agg_condition["value"] = list(set(agg_condition["value"]) | set(DISCARD_PLUGINS))
                    qc.config = config
                    updated_query_configs.append(qc)
                    break
            else:
                agg_condition = {
                    "key": "process_name",
                    "value": DISCARD_PLUGINS,
                    "method": "neq",
                    "condition": "and",
                    "dimension_name": "进程名称",
                }
                agg_conditions.append(agg_condition)
                qc.config = config
                updated_query_configs.append(qc)
            print(f"[done] process strategy config {qc.strategy_id}")
        except Exception as exec:  # pylint: disable=broad-except
            print(f"[X] process strategy config {qc.strategy_id} error: {exec}")
            continue
    print("准备执行批量更新QueryConfigModel操作")
    query_config_model.objects.bulk_update(updated_query_configs, ["config"])
    print(f"批量更新完成，共更新QueryConfigModel记录{len(updated_query_configs)}条.")


class Migration(migrations.Migration):
    dependencies = [
        ('bkmonitor', '0163_auto_20240619_1130'),
    ]

    operations = [
        migrations.RunPython(update_strategy_config),
    ]
