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
from dateutil import parser

from apps.log_search.constants import OperatorEnum
from apps.log_unifyquery.constants import ADVANCED_OP_MAP


def transform_advanced_addition(addition: dict):
    origin_operator = addition["operator"]
    field = addition["field"]
    value = addition["value"]

    op = ADVANCED_OP_MAP.get(origin_operator, {}).get("operator", "eq")
    condition = ADVANCED_OP_MAP.get(origin_operator, {}).get("condition", "or")
    is_wildcard = ADVANCED_OP_MAP.get(origin_operator, {}).get("is_wildcard", False)

    if origin_operator in [OperatorEnum.IS_TRUE["operator"], OperatorEnum.IS_FALSE["operator"]]:
        value = ["true" if origin_operator == OperatorEnum.IS_TRUE["operator"] else "false"]
    elif origin_operator in [OperatorEnum.EXISTS["operator"], OperatorEnum.NOT_EXISTS["operator"]]:
        value = [""]
    else:
        value = value if isinstance(value, list) else value.split(",")

    if condition == "or":
        field_list = [{"field_name": field, "op": op, "value": value, "is_wildcard": is_wildcard}]
        condition_list = []
    else:
        field_list = [{"field_name": field, "op": op, "value": [v], "is_wildcard": is_wildcard} for v in value]
        condition_list = [condition] * (len(value) - 1)

    return field_list, condition_list


def deal_time_format(start_time, end_time):
    """
    处理时间戳信息
    """
    if isinstance(start_time, int) and isinstance(end_time, int):
        return start_time, end_time

    dt1 = parser.parse(start_time)
    dt2 = parser.parse(end_time)
    start_time = int(dt1.timestamp() * 1000)
    end_time = int(dt2.timestamp() * 1000)
    return start_time, end_time
