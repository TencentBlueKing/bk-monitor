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
import re
from collections import defaultdict
from typing import Dict, List

from django.core.management.base import BaseCommand

from bkmonitor.models import AlgorithmModel, ItemModel, QueryConfigModel
from constants.data_source import DataSourceLabel
from constants.strategy import AGG_METHOD_REAL_TIME

target_biz_list = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        migrate_real_time_strategy()


OPERATOR_DESC = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "=",
    "neq": "!=",
}


def config_to_expression(var: str, config: list) -> str:
    """
    将静态阈值算法配置转换为对应的逻辑表达式字符串
    """
    expression_parts = []

    for sub_config in config:
        sub_expressions = []

        for condition in sub_config:
            method = condition['method']
            threshold = condition['threshold']
            operator = OPERATOR_DESC[method]
            sub_expressions.append(f"{var} {operator} {threshold}")

        sub_expression = " and ".join(sub_expressions)
        if len(sub_expressions) > 1:
            sub_expression = f"({sub_expression})"
        expression_parts.append(sub_expression)

    full_expression = " or ".join(expression_parts)
    return full_expression


def conditions_to_promql(promql: str, agg_condition: list) -> str:
    """将agg_condition转换为对应的PromQL查询字符串"""

    base_part = promql
    query_configs = []
    for agg_condition in agg_condition:
        key = agg_condition["key"]
        values = agg_condition["value"]
        method = agg_condition["method"]
        condition_type = agg_condition.get("condition", "and")

        # 根据方法类型构建正则表达式
        regex = ""
        regex_part = "|".join([f"({value})" for value in values])
        if method in ["eq", "include", "reg"]:
            regex = f'=~"^{regex_part}$"' if method == "eq" else f'=~"{regex_part}"'
        elif method in ["neq", "exclude", "nreg"]:
            regex = f'!~"^{regex_part}$"' if method == "neq" else f'!~"{regex_part}"'

        # 将配置添加到列表
        if key and regex:
            query_configs.append((f"{key}{regex}", condition_type))

    # 使用正确的连接类型构建PromQL查询
    agg_conditions_or_part = []
    for index, (query, condition_type) in enumerate(query_configs):
        if index == 0:
            promql += f"{{{query}}}"
            continue
        if condition_type == "and":
            end_index = promql.rfind('}')
            promql = f"{promql[:end_index]}, {query}}}"
        elif condition_type == "or":
            agg_conditions_or_part.append(promql)
            promql = f"{base_part}{{{query}}}"
            if index == len(query_configs) - 1:
                agg_conditions_or_part.append(promql)
    if agg_conditions_or_part:
        promql = " or ".join(agg_conditions_or_part)

    return promql


def migrate_real_time_strategy():
    """
    迁移存量实时监控策略
    """
    # 迁移至命令 migrate_real_time_strategy
    print("开始迁移存量实时监控策略")
    query_configs = QueryConfigModel.objects.filter(config__agg_method=AGG_METHOD_REAL_TIME)
    strategy_ids = query_configs.values_list('strategy_id', flat=True).distinct()

    if len(strategy_ids) > 500:
        algorithm_query = AlgorithmModel.objects.all()
        item_query = ItemModel.objects.all()
    else:
        algorithm_query = AlgorithmModel.objects.filter(strategy_id__in=strategy_ids)
        item_query = ItemModel.objects.filter(strategy_id__in=strategy_ids)

    algorithms_mapping: Dict[int, List[AlgorithmModel]] = defaultdict(list)
    for algorithm in algorithm_query:
        algorithms_mapping[algorithm.strategy_id].append(algorithm)

    items_mapping: Dict[int, List[ItemModel]] = defaultdict(list)
    for item in item_query:
        items_mapping[item.strategy_id].append(item)

    migrated_query_configs = []
    migrated_items = []
    for qc in query_configs:
        try:
            data_label = qc.config.get("data_label")
            metric_field = qc.config.get("metric_field")
            result_table_id = qc.config.get("result_table_id").split(".")[0]
            metric_id = qc.metric_id.replace(".", ":")
            data_source_label = qc.data_source_label
            # 自定义指标结果表ID带data_id时，将metric_id替换为data_label:metric_field
            if (
                data_source_label in [DataSourceLabel.CUSTOM]
                and bool(re.search(r'_\d+$', result_table_id))
                and data_label
            ):
                metric_id = f"{data_label}:{metric_field}"

            promql = metric_id
            # 处理agg_condition转换为对应的PromQL查询字符串
            agg_condition: list = qc.config.get("agg_condition", [])
            if agg_condition:
                promql = conditions_to_promql(promql, agg_condition)

            # 将静态阈值算法拼接到promql中
            algorithms = algorithms_mapping[qc.strategy_id]
            if len(algorithms) == 1 and algorithms[0].type == "Threshold" and algorithms[0].config:
                config = algorithms[0].config
                promql = config_to_expression(promql, config)

            # 更新QueryConfigModel
            qc.data_source_label = "prometheus"
            qc.metric_id = metric_id  # 值为promql时会有内容超过字段长度的情况
            qc.config = {
                "promql": promql,
                "agg_interval": qc.config.get("agg_interval", ""),
                "functions": qc.config.get("functions", []),
            }
            migrated_query_configs.append(qc)

            # 更新ItemModel
            items = items_mapping[qc.strategy_id]
            if items:
                for item in items:
                    item.origin_sql = promql
                    migrated_items.append(item)
            print(f"[done] process strategy {qc.strategy_id}")
        except Exception as exec:  # pylint: disable=broad-except
            print(f"[X] process strategy {qc.strategy_id} error: {exec}")
            continue

    print("准备执行批量更新操作")
    QueryConfigModel.objects.bulk_update(migrated_query_configs, ['data_source_label', 'metric_id', 'config'])
    ItemModel.objects.bulk_update(migrated_items, ['origin_sql'])
    print(f"批量更新完成，共更新QueryConfigModel记录{len(migrated_query_configs)}条，ItemModel记录{len(migrated_items)}条.")
