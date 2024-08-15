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
    operator = contains_addition["operator"]
    field = contains_addition["field"]
    value = contains_addition["value"]
    value = value if isinstance(value, list) else value.split(",")

    op = (
        "contains"
        if operator
        in [OperatorEnum.CONTAINS_MATCH_PHRASE["operator"], OperatorEnum.ALL_CONTAINS_MATCH_PHRASE["operator"]]
        else "ncontains"
    )
    field_list = [{"field_name": field, "op": op, "value": [v]} for v in value]
    condition_list = ["and"] * (len(value) - 1)

    return field_list, condition_list


def transform_exists_addition(exists_addition: dict):
    if exists_addition["operator"] == OperatorEnum.EXISTS["operator"]:
        return [{"field_name": exists_addition["field"], "op": "ne", "value": [""]}], []
    return [{"field_name": exists_addition["field"], "op": "eq", "value": [""]}], []


def transform_bool_addition(bool_addition: dict):
    if bool_addition["operator"] == OperatorEnum.IS_TRUE["operator"]:
        return [{"field_name": bool_addition["field"], "op": "eq", "value": ["true"]}], []
    return [{"field_name": bool_addition["field"], "op": "eq", "value": ["false"]}], []
