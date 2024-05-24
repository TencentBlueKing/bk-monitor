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
import re
from typing import Dict, List

from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("metadata")


def generate_table_id(space_type: str, space_id: str, record_name: str) -> str:
    """生成项目下的结果表"""
    # 处理预计算的名称
    # 替换`.`|`-`|`/`为`_`, 符合标准
    # 限制长度为110，因为限制的结果表长度为128
    record_name = record_name.replace(".", "_").replace("-", "_").replace("/", "_").strip("_")[:110]
    return f"bkmonitor_{space_type}_{space_id}_{record_name}.__default__"


def transform_record_to_metric_name(record: str) -> str:
    """转换预计算的record到指标名称
    record: "level:src_metric:operation"
    metric_name: "level_src_metric_operation"
    """
    return "_".join(record.strip(":").split(":")).strip("_")


def refine_bk_sql_and_metrics(promql: str, all_rule_record: List[str]) -> Dict:
    """转换promql为sql语句，并且提取指标"""
    # 去掉注释
    promql_without_comment = re.sub(r"#.*", "", promql)
    # 去掉换行符
    _promql = promql_without_comment.replace("\n", "")
    # 查找替换为新的指标
    for record in all_rule_record:
        if record not in _promql:
            continue
        _promql = _promql.replace(record, transform_record_to_metric_name(record))
    # 转换为结构体
    try:
        rule_dict = api.unify_query.promql_to_struct({"promql": _promql})
    except BKAPIError as e:
        logger.error("transform promql to struct failed, promql: %s, error: %s", _promql, e)
        raise

    # 获取已有的指标，
    metrics = set()
    rule_data = rule_dict["data"]
    for item in rule_data["query_list"]:
        metrics.add(item["field_name"])
    # 在转换为promql
    try:
        sql = api.unify_query.struct_to_promql(rule_data)
    except BKAPIError as e:
        logger.error("transform struct to promql failed, struct: %s, error: %s", rule_data, e)
        raise
    # 去掉`bkmonitor:`
    return {"promql": sql["promql"].replace("bkmonitor:", ""), "metrics": metrics}


def compose_rule_table_id(table_id: str) -> str:
    """生成规则表的名称"""
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    name = f"{table_id.replace('-', '_').replace('.', '_').replace('__', '_')[-40:]}"
    # NOTE: 清洗结果表不能出现双下划线
    return f"vm_{name.strip('_')}"
