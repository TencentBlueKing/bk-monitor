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

    strategy = strategy_model.objects.filter(name="Gse进程托管事件告警(业务侧)").first()
    if not strategy:
        return
    query_config = query_config_model.objects.filter(strategy_id=strategy.id).first()
    if not query_config:
        return

    config = query_config.config
    agg_conditions = config.get("agg_condition", [])
    for agg_condition in agg_conditions:
        if agg_condition["key"] == "process_name" and agg_condition["method"] == "neq":
            old_value_set = set(agg_condition["value"])
            new_value_set = set(DISCARD_PLUGINS)
            if new_value_set.issubset(old_value_set):
                print("New agg_condition set is already a subset of old agg_condition set, no need to update.")
                break
            agg_condition["value"] = list(old_value_set.union(new_value_set))
            query_config.config = config
            query_config.save()
            print("Query config updated and saved.")
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
        query_config.config = config
        query_config.save()
        print("New agg_condition added and query config saved.")


class Migration(migrations.Migration):
    dependencies = [
        ('bkmonitor', '0163_auto_20240619_1130'),
    ]

    operations = [
        migrations.RunPython(update_strategy_config),
    ]
