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

import abc
from datetime import datetime
from typing import Dict, List

import six
from django.utils.translation import gettext as _

from bkmonitor.models import StrategyModel
from bkmonitor.utils.time_tools import str2datetime, utc2biz_str
from constants.shield import (
    SCOPE_TYPE_NAME_MAPPING,
    SHIELD_CATEGORY_NAME_MAPPING,
    ScopeType,
    ShieldCategory,
)

STRATEGY_NAME_TEMPLATE = _("策略名称：{}")
STRATEGY_ALREADY_DELETED_MESSAGE = _("该策略已经被删除")
CYCLE_ONCE = _("次")
CYCLE_DAILY = _("天")
CYCLE_WEEKLY = _("周")
CYCLE_MONTHLY = _("月")
LESS_THAN_AN_HOUR_TEMPLATE = _("<1小时/{}")
HOURS_TEMPLATE = _("{}小时/{}")


class BaseShieldDisplayManager(six.with_metaclass(abc.ABCMeta, object)):
    def get_shield_content(self, shield, strategy_id_to_name=None):
        """
        获取屏蔽的内容
        """
        bk_biz_id = shield["bk_biz_id"]
        category = shield["category"]
        dimension_config = shield["dimension_config"]
        scope_type = shield["scope_type"]

        if category in [ShieldCategory.EVENT, ShieldCategory.ALERT]:
            return dimension_config["_dimensions"]

        content = ""
        if category == ShieldCategory.DIMENSION:
            method_dict = {"eq": "=", "gte": "≥", "gt": ">", "lt": "<", "lte": "≤", "neq": "!="}
            for index, condition in enumerate(dimension_config.get("dimension_conditions", [])):
                method = condition.get("method", "eq")
                condition_content = "{name} {method} {value}".format(
                    name=condition.get("name") or condition.get("key"),
                    method=method_dict.get(method) or method,
                    value=",".join(condition.get("value", [])),
                )
                if index == 0:
                    content += condition_content
                    continue
                content += " {} {}".format(condition.get("condition", "and"), condition_content)
            return content

        if category == ShieldCategory.STRATEGY:
            strategy_ids = self.get_strategy_ids(shield)
            # 目前仅在前端屏蔽列表会传入 strategy_id_to_name
            if strategy_id_to_name:
                strategy_names = [strategy_id_to_name.get(strategy_id, "") for strategy_id in strategy_ids]
            else:
                strategy_names = StrategyModel.objects.filter(id__in=strategy_ids).values_list("name", flat=True)

            if strategy_names:
                names = " ".join(strategy_names)
                content = STRATEGY_NAME_TEMPLATE.format(names.strip()) + " - "
            else:
                return STRATEGY_ALREADY_DELETED_MESSAGE

        if scope_type == ScopeType.INSTANCE:
            service_list = self.get_service_name_list(bk_biz_id, dimension_config.get("service_instance_id"))
            content += ",".join(service_list)
        elif scope_type == ScopeType.IP:
            content += ",".join([ip["bk_target_ip"] for ip in dimension_config.get("bk_target_ip", [])])
        elif scope_type == ScopeType.NODE:
            node_path_list = self.get_node_path_list(bk_biz_id, dimension_config.get("bk_topo_node"))
            content += ",".join(["/".join(item) for item in node_path_list])
        elif scope_type == ScopeType.DYNAMIC_GROUP:
            dynamic_group_names = self.get_dynamic_group_name_list(
                bk_biz_id, dimension_config.get("dynamic_group") or []
            )
            content += ",".join(dynamic_group_names)
        else:
            content += self.get_business_name(bk_biz_id)

        return content

    @staticmethod
    def get_strategy_ids(shield):
        if shield["category"] != ShieldCategory.STRATEGY:
            return []

        strategy_ids = shield["dimension_config"]["strategy_id"]
        return strategy_ids if isinstance(strategy_ids, list) else [strategy_ids]

    @abc.abstractmethod
    def get_service_name_list(self, bk_biz_id, service_instance_id_list):
        """
        根据实例id列表返回实例名称列表，需要子类实现
        example：
        输入：bk_biz_id=2, service_instance_id_list=[1,2,3]
        输出：['mysql', 'gse_ops']
        """
        return []

    @abc.abstractmethod
    def get_node_path_list(self, bk_biz_id, bk_topo_node_list):
        """
        根据节点列表返回节点的路径列表，需要子类实现
        example:
        输入：bk_biz_id=2, bk_topo_node_list=[{"bk_obj_id":"set","bk_inst_id":6},{"bk_obj_id":"module","bk_inst_id":60}]
        输出：[['蓝鲸', 'test1', '计算平台'], ['蓝鲸', 'test1', '作业平台', 'consul']]
        """
        return []

    @abc.abstractmethod
    def get_dynamic_group_name_list(self, bk_biz_id: int, dynamic_group_list: List[Dict]) -> List:
        """
        根据动态分组id列表返回动态分组名称列表，需要子类实现
        """
        return []

    @abc.abstractmethod
    def get_business_name(self, bk_biz_id):
        """
        根据业务id获得业务名称，需要子类实现
        example:
        输入：bk_biz_id=2
        输出：'蓝鲸'
        """
        return ""

    def get_cycle_duration(self, shield):
        """
        获取屏蔽的持续周期及市场
        """
        cycle_mapping = {1: CYCLE_ONCE, 2: CYCLE_DAILY, 3: CYCLE_WEEKLY, 4: CYCLE_MONTHLY}
        cycle_config = shield["cycle_config"]
        begin_time = shield["begin_time"]
        begin_time = utc2biz_str(begin_time) if isinstance(begin_time, datetime) else begin_time
        end_time = shield["end_time"]
        end_time = utc2biz_str(end_time) if isinstance(end_time, datetime) else end_time
        # 如果是单次，计算起止时间的时间差，再转换成小时
        if cycle_config.get("type", 1) == 1:
            time_delta = str2datetime(end_time) - str2datetime(begin_time)
            hours = time_delta.days * 24 + time_delta.seconds // 60 // 60
        # 如果是每天/周/月，计算每天的的时间差，乘以天数，再转换成小时
        else:
            begin_list = cycle_config.get("begin_time").split(":")
            end_list = cycle_config.get("end_time").split(":")

            end_seconds = int(end_list[0]) * 3600 + int(end_list[1]) * 60 + int(end_list[2])
            begin_seconds = int(begin_list[0]) * 3600 + int(begin_list[1]) * 60 + int(begin_list[2])

            if begin_seconds <= end_seconds:
                seconds = end_seconds - begin_seconds + 1
            else:
                seconds = end_seconds + 24 * 3600 - begin_seconds + 1

            day_count = len(cycle_config.get("week_list", [])) or len(cycle_config.get("day_list", [])) or 1
            hours = seconds * day_count // 60 // 60

        # 补充单位
        unit = cycle_mapping[cycle_config.get("type", 1)]
        cycle_duration = LESS_THAN_AN_HOUR_TEMPLATE.format(unit) if hours == 0 else HOURS_TEMPLATE.format(hours, unit)

        return cycle_duration

    def get_category_name(self, shield):
        """
        获取屏蔽的分类
        """
        category = shield["category"]
        category_name = SHIELD_CATEGORY_NAME_MAPPING.get(category)
        scope_type_name = SCOPE_TYPE_NAME_MAPPING.get(shield["scope_type"])

        if category == ShieldCategory.SCOPE:
            return f"{category_name}（ {scope_type_name} ）"

        return category_name
