# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from constants.common import DutyType

from . import conditions, fields, period

__all__ = [
    "load_condition_instance",
    "TIME_MATCH_CLASS_MAP",
    "load_field_instance",
    "load_agg_condition_instance",
    "DUTY_TIME_MATCH_CLASS_MAP",
    "CONDITION_CLASS_MAP",
]

SUPPORT_SIMPLE_METHODS = ("include", "exclude", "gt", "gte", "lt", "lte", "eq", "neq", "reg", "nreg")
SUPPORT_COMPOSITE_METHODS = ("or", "and")

CONDITION_CLASS_MAP = {
    "eq": conditions.EqualCondition,
    "neq": conditions.NotEqualCondition,
    "lt": conditions.LesserCondition,
    "lte": conditions.LesserOrEqualCondition,
    "gt": conditions.GreaterCondition,
    "gte": conditions.GreaterOrEqualCondition,
    "reg": conditions.RegularCondition,
    "nreg": conditions.NotRegularCondition,
    "include": conditions.IncludeCondition,
    "exclude": conditions.ExcludeCondition,
    "issuperset": conditions.IsSuperSetCondition,
}

DEFAULT_DIMENSION_FIELD_CLASS = fields.DimensionField
DIMENSION_FIELD_CLASS_MAP = {
    "ip": fields.IpDimensionField,
    "bk_target_ip": fields.BkTargetIpDimensionField,
    "cc_topo_set": fields.TopoSetDimensionField,
    "cc_topo_module": fields.TopoModuleDimensionField,
    "cc_app_module": fields.AppModuleDimensionField,
    "bk_topo_node": fields.TopoNodeDimensionField,
    "host_topo_node": fields.HostTopoNodeDimensionField,
    "service_topo_node": fields.ServiceTopoNodeDimensionField,
}

TIME_MATCH_CLASS_MAP = {
    -1: period.TimeMatchBySingle,
    2: period.TimeMatchByDay,
    3: period.TimeMatchByWeek,
    4: period.TimeMatchByMonth,
}

DUTY_TIME_MATCH_CLASS_MAP = {
    DutyType.WEEKLY: period.TimeMatchByWeek,
    DutyType.MONTHLY: period.TimeMatchByMonth,
    DutyType.DAILY: period.TimeMatchByDay,
    DutyType.SINGLE: period.TimeMatchBySingle,
}


def load_field_instance(field_name, field_value):
    cond_field_class = DIMENSION_FIELD_CLASS_MAP.get(field_name, DEFAULT_DIMENSION_FIELD_CLASS)
    return cond_field_class(field_name, field_value)


def load_agg_condition_instance(agg_condition):
    """
    Load Condition instance by condition model
    :param agg_condition:
            [{"field":"ip", "method":"eq", "value":"111"}, {"field":"ip", "method":"eq", "value":"111", "method": "eq"}]
    :return: condition object
    """
    conditions_config = []

    condition = []
    for c in agg_condition:
        if c.get("condition") == "or" and condition:
            conditions_config.append(condition)
            condition = []

        condition.append({"field": c["key"], "method": c["method"], "value": c["value"]})

    if condition:
        conditions_config.append(condition)
    return load_condition_instance(conditions_config)


def load_condition_instance(conditions_config, default_value_if_not_exists=True):
    """
    Load Condition instance by condition model
    :param conditions_config:
            [[{"field":"ip", "method":"eq", "value":"111"}, {}], []]
    :return: condition object
    """
    if not isinstance(conditions_config, (list, tuple)):
        raise Exception("Config Incorrect, Check your settings.")

    or_cond_obj = conditions.OrCondition()
    for cond_item_list in conditions_config:
        and_cond_obj = conditions.AndCondition()
        for cond_item in cond_item_list:
            field_name = cond_item.get("field")
            method = cond_item.get("method", "eq")
            # 日志对eq/neq 进行了转换(is one of/is not one of)
            if method not in CONDITION_CLASS_MAP:
                method = cond_item.get("_origin_method", "eq")

            field_value = cond_item.get("value")
            if not all([field_name, method, field_value]):
                continue

            cond_field = load_field_instance(field_name, field_value)
            cond_obj = CONDITION_CLASS_MAP.get(method)(cond_field, default_value_if_not_exists)
            and_cond_obj.add(cond_obj)

        or_cond_obj.add(and_cond_obj)
    return or_cond_obj
