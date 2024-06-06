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
from apps.log_search.constants import OperatorEnum


def transform_contains_addition(contains_addition: dict):
    contain_op_mapping = {
        OperatorEnum.CONTAINS_MATCH_PHRASE["operator"]: ("contains",),
        OperatorEnum.NOT_CONTAINS_MATCH_PHRASE["operator"]: ("ncontains",),
        OperatorEnum.ALL_CONTAINS_MATCH_PHRASE["operator"]: ("contains", "and"),
        OperatorEnum.ALL_NOT_CONTAINS_MATCH_PHRASE["operator"]: ("ncontains", "and"),
    }

    operator = contains_addition["operator"]
    op, condition = contain_op_mapping.get(operator, (None, None))

    field_list = []
    condition_list = []

    if op:
        for index, value in enumerate(contains_addition["value"]):
            field_list.append({"field_name": contains_addition["field"], "op": op, "value": value})
            if index > 0 and condition:
                condition_list.append(condition)

    return field_list, condition_list


def transform_exists_addition(exists_addition: dict):
    if exists_addition["operator"] == OperatorEnum.EXISTS["operator"]:
        return [{"field_name": exists_addition["field"], "op": "ne", "value": ""}], []
    return [{"field_name": exists_addition["field"], "op": "eq", "value": ""}], []


def transform_bool_addition(bool_addition: dict):
    if bool_addition["operator"] == OperatorEnum.IS_TRUE["operator"]:
        return [{"field_name": bool_addition["field"], "op": "eq", "value": "true"}], []
    return [{"field_name": bool_addition["field"], "op": "eq", "value": "false"}], []
