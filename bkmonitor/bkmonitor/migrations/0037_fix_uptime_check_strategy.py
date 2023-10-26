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

from constants.data_source import DataSourceLabel, DataTypeLabel


def fix_uptimecheck_strategy(apps, *args, **kwargs):
    """
    修复异常的拨测策略
    1. 处理不服未转换为阈值的部分节点数算法
    2. 响应码和响应内容策略不能使用node_id作为指标，因为influxdb不支持聚合维度，哪怕是COUNT
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    AlgorithmModel = apps.get_model("bkmonitor", "AlgorithmModel")

    query_configs = QueryConfigModel.objects.filter(
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        config__result_table_id="uptimecheck.http",
        config__metric_field="node_id",
    )
    for query_config in query_configs:
        query_config.metric_id = "bk_monitor.uptimecheck.http.available"
        query_config.config["metric_field"] = "available"
        conditions = query_config.config["agg_condition"]
        for condition in conditions:
            if not isinstance(condition["value"], list):
                condition["value"] = [condition["value"]]
            condition["value"] = [str(v) for v in condition["value"]]
        query_config.save()

    algorithms = AlgorithmModel.objects.filter(type="PartialNodes")
    for algorithm in algorithms:
        algorithm.type = "Threshold"
        algorithm.config = [[{"method": "gte", "threshold": int(algorithm.config.get("count", 0))}]]
        algorithm.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0036_fix_metric_changed_from_v2_5"),
    ]

    operations = [
        migrations.RunPython(fix_uptimecheck_strategy),
    ]
