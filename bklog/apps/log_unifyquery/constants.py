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
from enum import Enum

from apps.log_search.constants import OperatorEnum
from apps.log_unifyquery.utils import (
    transform_bool_addition,
    transform_contains_addition,
    transform_exists_addition,
)


class AggTypeEnum(Enum):
    """
    聚合类型枚举
    """

    MAX = "max"
    MIN = "min"
    AVG = "avg"
    MEDIAN = "median"


REFERENCE_ALIAS = "abcdefghijklmnopqrstuvwx"

# 字段类型映射表
FIELD_TYPE_MAP = {
    "keyword": "string",
    "text": "string",
    "integer": "int",
    "long": "int",
    "double": "int",
    "bool": "string",
    "conflict": "string",
}

FLOATING_NUMERIC_FIELD_TYPES = ["double", "float"]

BASE_OP_MAP = {
    "=": "eq",
    "!=": "ne",
    "=~": "contains",
    "!=~": "ncontains",
    "contains": "contains",
    "not contains": "ncontains",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "is one of": "eq",
    "is": "eq",
    "is not one of": "ne",
    "is not": "ne",
}

OP_TRANSFORMER = {
    OperatorEnum.CONTAINS_MATCH_PHRASE["operator"]: transform_contains_addition,
    OperatorEnum.NOT_CONTAINS_MATCH_PHRASE["operator"]: transform_contains_addition,
    OperatorEnum.ALL_CONTAINS_MATCH_PHRASE["operator"]: transform_contains_addition,
    OperatorEnum.ALL_NOT_CONTAINS_MATCH_PHRASE["operator"]: transform_contains_addition,
    OperatorEnum.EXISTS["operator"]: transform_exists_addition,
    OperatorEnum.NOT_EXISTS["operator"]: transform_exists_addition,
    OperatorEnum.IS_TRUE["operator"]: transform_bool_addition,
    OperatorEnum.IS_FALSE["operator"]: transform_bool_addition,
}

# 检索选项历史记录API返回数据数量大小
SEARCH_OPTION_HISTORY_NUM = 10
